import asyncio
import os
import re
from tqdm import tqdm
from threading import Thread
from watchdog.events import FileCreatedEvent, FileModifiedEvent
from waapi import WaapiClient, CannotConnectToWaapiException, AsyncioLoopExecutor
from util import SubprocessException, watch_async
import nest_asyncio
nest_asyncio.apply()  # needed for waapi

WWISE_OBJECT_PATH = "\\Actor-Mixer Hierarchy\\Default Work Unit\\"


def get_wwise_path():
    """Returns the path to the Wwise executable."""

    path = os.getenv("WWISEROOT") or os.getenv("WWWISE_PATH")
    if not path:
        raise RuntimeError(
            "Neither 'WWISEROOT' nor 'WWWISE_PATH' environment variable is set")

    return os.path.join(path, "Authoring\\x64\\Release\\bin\\")


async def create_project(project_path: str):
    """Creates a new Wwise project at the given path if it doesnt exist"""

    # Check existence
    if os.path.exists(project_path):
        return

    # Otherwise, create the project
    process = await asyncio.create_subprocess_exec(
        get_wwise_path()+"WwiseConsole.exe",
        "create-new-project",
        project_path,
        "--quiet"
    )
    result = await process.wait()

    if result != 0 and result != 2:  # 2 means warnings in wwise
        raise SubprocessException(
            f"Creating project failed with exit code {result}")

    # Find desired quality settings
    conv_id = ""
    with open(os.path.join(os.path.dirname(project_path), "Conversion Settings\\Factory Conversion Settings.wwu"), "r") as f:
        settings = f.read()
        findings = re.search(
            r"<Conversion Name=\"Vorbis Quality High\" ID=\"{([\w\-]+)}\">", settings)
        conv_id = findings.group(1)

    # Patch project settings
    data = ""
    with open(project_path, "r") as f:
        data = f.read()

    data = re.sub(r"<DefaultConversion(.*)ID=\"\{([\w\-]+)\}\"\/>\n",
                  "<DefaultConversion\g<1>ID=\"{"+conv_id+"}\"/>\n", data)
    data = data.replace("Default Conversion Settings", "Vorbis Quality High")

    with open(project_path, "w") as f:
        f.write(data)


async def spawn_wwise(project: str):
    """Starts Wwise for the given project."""

    process = await asyncio.create_subprocess_exec(
        get_wwise_path()+"Wwise.exe",
        project,
        "--quiet",
    )
    yield process

    result = await process.wait()
    if result != 0:
        raise SubprocessException(
            f"Wwise server failed with exit code {result}")


async def create_waapi(server: asyncio.subprocess.Process):
    waapi = None
    while server.returncode is None:
        try:
            waapi = WaapiClient()
            break
        except CannotConnectToWaapiException as err:
            if server.returncode is not None:
                raise err

    if waapi is None:
        raise CannotConnectToWaapiException()

    return waapi


async def wait_waapi_load(waapi: WaapiClient):
    """Wait until the WAAPI server is loaded."""

    print("Waiting for Wwise to load...")
    # The 'loaded' event was unreliable
    while not waapi.call("ak.wwise.core.getInfo"):
        await asyncio.sleep(0.5)


def move_wwise_files(converted_objects: list[dict], output_path: str):
    """Moves all convertedWwise files to the given output folder and renames them correctly."""

    for obj in tqdm([x for x in converted_objects if x["type"] == "Sound"], desc="Renaming files", unit="file"):

        original_path = obj["sound:originalWavFilePath"]
        filename = os.path.basename(original_path)[:-len(".wav")]

        path = obj["path"][len(WWISE_OBJECT_PATH):-len(obj["name"])]
        output_dir = os.path.join(output_path, path)
        output = os.path.join(output_dir, filename+".wem")

        try:
            os.makedirs(output_dir)
        except OSError:
            # Overwrite existing files
            if os.path.exists(output):
                os.unlink(output)

        os.rename(obj["sound:convertedWemFilePath"], output)


def move_wwise_files_auto(project_path: str, reference_path: str, output_path: str):
    """Tries to find the correct output path for all converted files without the index of converted files."""

    # Create own index/mapping
    index = {}

    for root, _dirs, files in os.walk(reference_path):
        path = root[len(reference_path) + 1:]
        for file in files:
            base_name = file.split('.')[0]
            if base_name in index:
                print(
                    f"File {file} exists in {index[base_name]} and {path}, using the latter")
            index[base_name] = path

    print(f"Created mapping of {len(index)} files")

    project_dir = os.path.dirname(project_path)
    cache_dir = os.path.join(project_dir, ".cache\\Windows\\SFX")

    for file in tqdm(os.listdir(cache_dir), desc="Moving files", unit="file"):
        if not file.endswith(".wem"):
            continue

        name = file.replace("_3F75BDB9", "")
        base_name = name.split('.')[0]
        if base_name not in index:
            tqdm.write(f"File {file} was not found in the index!")

        new_path = os.path.join(output_path, index[base_name], name)
        if os.path.exists(new_path):
            os.unlink(new_path)

        os.rename(os.path.join(cache_dir, file), new_path)


async def _convert_files(input_path: str, project_path: str, output_path: str, waapi):
    # Wait for load
    await wait_waapi_load(waapi)

    # Setup
    waapi.call("ak.wwise.debug.enableAutomationMode", {"enable": True})

    # List all files
    imports = []

    for root, _dirs, files in os.walk(input_path):
        path = "\\".join(
            "<Folder>"+s for s in root[len(input_path):].split('\\') if s)

        for file in files:
            if file.endswith(".wav"):
                imports.append({
                    "audioFile": os.path.join(os.getcwd(), root, file),
                    "objectPath": os.path.join(WWISE_OBJECT_PATH, path, "<Sound>"+file),
                })

    # Listen for imports
    pbar = tqdm(total=len(imports),
                desc="Importing files to Wwise", unit="file")

    def on_object_created(*args, **kwargs):
        if kwargs["object"]["type"] == "AudioFileSource":
            pbar.update(1)

    handler = waapi.subscribe(
        "ak.wwise.core.object.created",
        on_object_created,
        {"return": ["type"]}
    )

    # Start importing
    imported = waapi.call("ak.wwise.core.audio.import", {
        "importOperation": "replaceExisting",
        "imports": imports,
    })["objects"]

    # Done
    pbar.close()
    handler.unsubscribe()
    waapi.call("ak.wwise.core.project.save")

    # Create convert thread
    convert_thread = Thread(
        target=waapi.call,
        args=("ak.wwise.ui.commands.execute", {
            "command": "ConvertAllPlatform",
            "objects": [obj["id"] for obj in imported],
        })
    )

    #  Listen to converting
    converted_objects = []

    def on_converted(command: str, objects, *args, **kwargs):
        nonlocal converted_objects
        if command == "ConvertAllPlatform":
            converted_objects = objects

    handler = waapi.subscribe(
        "ak.wwise.ui.commands.executed",
        on_converted,
        {"return": ["type", "path", "name", "sound:originalWavFilePath",
                    "sound:convertedWemFilePath"]}
    )

    project_dir = os.path.dirname(project_path)
    cache_dir = os.path.join(project_dir, ".cache")
    event_queue, observer = watch_async(cache_dir, recursive=True)

    pbar = tqdm(desc="Converting files", total=len(imports), unit="file")

    # Start converting
    convert_thread.start()
    # Print progress while converting
    while convert_thread.is_alive():
        try:
            event = event_queue.get_nowait()
            if event.src_path.endswith(".wem"):
                pbar.update(1)
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.1)

    # Done
    observer.stop()
    pbar.close()
    handler.unsubscribe()
    waapi.call("ak.wwise.core.project.save")

    # Move and rename files
    move_wwise_files(converted_objects, output_path)

    print("Conversion done!")


async def convert_files(input_path: str, project_path: str, output_path: str):
    """Converts all files in the given folder to Wwise format."""
    await create_project(project_path)

    print("##############################################################")
    print("# Opening Wwise in a few seconds, get ready for a jumpscare! #")
    print("#  The Wwise window will be fully automated, don't touch it! #")
    print("##############################################################")
    await asyncio.sleep(5)

    #  Start the WAAPI server
    server_spawn = spawn_wwise(project_path)
    server = await anext(server_spawn)

    # Try to estabilish connection
    print("Trying to connect to Wwise...")
    waapi = await create_waapi(server)
    print("Connected!")

    # Run the script
    try:
        await _convert_files(input_path, project_path, output_path, waapi)
    finally:
        # Close the WAAPI server
        print("Closing Wwise...")
        waapi.disconnect()
        if server.returncode is None:
            server.terminate()
            await server.wait()
