import asyncio
import os
import re
import json
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


def get_wwise_project(folder: str):
    basename = os.path.basename(folder.replace(r"\\$", ""))
    return os.path.join(folder, basename+".wproj")


async def create_project(project_dir: str):
    """Creates a new Wwise project at the given path if it doesnt exist"""

    project_path = get_wwise_project(project_dir)

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
    with open(os.path.join(project_dir, "Conversion Settings\\Factory Conversion Settings.wwu"), "r", encoding="utf-8") as f:
        settings = f.read()
        findings = re.search(
            r"<Conversion Name=\"Vorbis Quality High\" ID=\"{([\w\-]+)}\">", settings)
        conv_id = findings.group(1)

    # Patch project settings
    data = ""
    with open(project_path, "r", encoding="utf-8") as f:
        data = f.read()

    data = re.sub(r"<DefaultConversion(.*)ID=\"\{([\w\-]+)\}\"\/>\n",
                  r'<DefaultConversion\g<1>ID="{'+conv_id+"}\"/>\n", data)
    data = data.replace("Default Conversion Settings", "Vorbis Quality High")

    with open(project_path, "w", encoding="utf-8") as f:
        f.write(data)


async def spawn_wwise(project_dir: str):
    """Starts Wwise for the given project."""

    process = await asyncio.create_subprocess_exec(
        get_wwise_path()+"Wwise.exe",
        get_wwise_project(project_dir),
        "--quiet",
    )
    yield process

    result = await process.wait()
    if result != 0:
        raise SubprocessException(
            f"Wwise server failed with exit code {result}")


async def create_waapi(server):
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

    tqdm.write("Waiting for Wwise to load...")
    # The 'loaded' event was unreliable
    while not waapi.call("ak.wwise.core.getInfo"):
        await asyncio.sleep(0.5)


def move_wwise_files(converted_objects: list[dict], output_path: str):
    """Moves all converted Wwise files to the given output folder and renames them correctly."""

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


def move_wwise_files_auto(project_dir: str, output_path: str):
    """Tries to find the correct output path for all converted files without the index of converted files."""

    cache_dir = os.path.join(project_dir, ".cache\\Windows\\SFX")

    found_files = []

    for root, _dirs, files in os.walk(cache_dir):
        path = root[len(cache_dir) + 1:]
        for file in files:
            if not file.endswith(".wem"):
                continue

            found_files.append(os.path.join(path, file))

    for file in tqdm(found_files, desc="Moving files", unit="file"):
        new_path = os.path.join(output_path, file.replace("_3F75BDB9", ""))
        new_dir = os.path.dirname(new_path)

        try:
            os.makedirs(new_dir)
        except OSError:
            # Overwrite existing files
            if os.path.exists(new_path):
                os.unlink(new_path)

        os.rename(os.path.join(cache_dir, file), new_path)


async def _convert_files(input_path: str, project_dir: str, output_path: str, waapi):
    # Wait for load
    await wait_waapi_load(waapi)

    tqdm.write("Starting automation mode...")

    # Setup
    waapi.call("ak.wwise.debug.enableAutomationMode", {"enable": True})

    # List all files
    tqdm.write("Starting import...")
    to_import = []

    for root, _dirs, files in os.walk(input_path):
        path = "\\".join(
            "<Folder>"+s for s in root[len(input_path):].split('\\') if s)

        for file in files:
            if file.endswith(".wav"):
                to_import.append({
                    "audioFile": os.path.join(os.getcwd(), root, file),
                    "originalsSubFolder": root[len(input_path):],
                    "objectPath": os.path.join(WWISE_OBJECT_PATH, path, "<Sound>"+file),
                })

    # Listen for imports
    pbar = tqdm(total=len(to_import),
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
        "imports": to_import,
    })["objects"]
    imported = [obj["id"] for obj in imported if obj["name"].endswith("_wav")]

    # Done
    pbar.close()
    handler.unsubscribe()

    # Create convert thread
    tqdm.write("Starting conversion...")
    convert_thread = Thread(
        target=waapi.call,
        args=("ak.wwise.ui.commands.execute", {
            "command": "ConvertAllPlatform",
            "objects": imported,
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

    cache_dir = os.path.join(project_dir, ".cache")

    os.makedirs(cache_dir, exist_ok=True)
    event_queue, observer = watch_async(cache_dir, recursive=True)

    pbar = tqdm(desc="Converting files", total=len(imported), unit="file")

    # Start converting
    convert_thread.start()
    # Print progress while converting
    while convert_thread.is_alive():
        try:
            event = event_queue.get_nowait()
            if event.src_path.endswith(".wem"):
                pbar.update(1)
        except asyncio.QueueEmpty:
            pbar.update(0)
            convert_thread.join(0.5)
        # Jobs seems finished, wait at most 60 seconds before moving on
        if pbar.n >= pbar.total:
            convert_thread.join(60)
            break

    # Done
    observer.stop()
    pbar.close()
    handler.unsubscribe()

    # Move and rename files
    tqdm.write("Starting moving files...")
    move_wwise_files(converted_objects, output_path)

    tqdm.write("Conversion done!")


async def convert_files(input_path: str, project_dir: str, output_path: str):
    """Converts all files in the given folder to Wwise format."""
    await create_project(project_dir)

    tqdm.write("##############################################################")
    tqdm.write("# Opening Wwise in a few seconds, get ready for a jumpscare! #")
    tqdm.write("#  The Wwise window will be fully automated, don't touch it! #")
    tqdm.write("##############################################################")
    await asyncio.sleep(5)

    #  Start the WAAPI server
    server_spawn = spawn_wwise(project_dir)
    server = await anext(server_spawn)

    # Try to estabilish connection
    tqdm.write("Trying to connect to Wwise...")
    waapi = await create_waapi(server)
    tqdm.write("Connected!")

    # Run the script
    try:
        await _convert_files(input_path, project_dir, output_path, waapi)
    finally:
        # Close the WAAPI server
        tqdm.write("Closing Wwise...")
        waapi.disconnect()
        if server.returncode is None:
            server.terminate()
            await server.wait()
