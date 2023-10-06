import asyncio
import os
import re
from tqdm import tqdm
from waapi import WaapiClient, CannotConnectToWaapiException, AsyncioLoopExecutor
from util import SubprocessException
import nest_asyncio
nest_asyncio.apply()  # needed for waapi


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


async def convert_files(input_path: str, project_path: str, output_path: str):
    """Converts all files in the given folder to Wwise format."""
    await create_project(project_path)

    print("##############################################################")
    print("# Opening Wwise in a few seconds, get ready for a jumpscare! #")
    print("#  The Wwise window will be fully automated, don't touch it! #")
    print("##############################################################")
    await asyncio.sleep(5)

    #  Start the WAAPI server and wait a few seconds
    server_spawn = spawn_wwise(project_path)
    server = await anext(server_spawn)

    # Try to estabilish connection
    waapi = None

    print("Trying to connect to Wwise...")
    while server.returncode is None:
        try:
            waapi = WaapiClient()
            print("Connected!")
            break
        except CannotConnectToWaapiException as err:
            if server.returncode is not None:
                raise err

    if waapi is None:
        raise CannotConnectToWaapiException()

    info = waapi.call("ak.wwise.core.getInfo")

    if not info:
        # Wait for load
        loaded = False

        def on_loaded(*args, **kwargs):
            nonlocal loaded
            loaded = True

        handler = waapi.subscribe("ak.wwise.core.project.loaded", on_loaded)
        print("Waiting for Wwise to load...")
        while not loaded:
            await asyncio.sleep(0.5)
        handler.unsubscribe()

    # Setup
    waapi.call("ak.wwise.debug.enableAutomationMode", {"enable": True})

    # List all files
    imports = []

    for root, _dirs, files in os.walk(input_path):
        for file in files:
            if file.endswith(".wav"):
                imports.append({
                    "audioFile": os.path.join(os.getcwd(), root, file),
                    "objectPath": "\\Actor-Mixer Hierarchy\\Default Work Unit\\<Sound>"+file
                })
                break

    # Listen for imports
    pbar = tqdm(total=len(imports), desc="Importing files to Wwise")

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
    })

    # Done
    pbar.close()
    handler.unsubscribe()

    #  Listen to converting
    converted_objects = []

    def on_converted(command: str, objects, *args, **kwargs):
        nonlocal converted_objects
        if command == "ConvertAllPlatform":
            converted_objects = objects

    handler = waapi.subscribe(
        "ak.wwise.ui.commands.executed",
        on_converted,
        {"return": ["type", "id", "name", "sound:originalWavFilePath",
                    "sound:convertedWemFilePath"]}
    )

    # Start converting
    print("Beginning conversion, progress can be watched in the Wwise window...")
    waapi.call("ak.wwise.ui.commands.execute", {
        "command": "ConvertAllPlatform",
        "objects": [obj["id"] for obj in imported["objects"]],
    })

    # Done
    print("Conversion done.")
    handler.unsubscribe()

    # Close the WAAPI server
    print("Closing Wwise...")
    waapi.disconnect()
    server.terminate()
    await server.wait()

    # Move and rename files
    for obj in tqdm(converted_objects, desc="Renaming files", unit="file"):
        if obj["type"] != "Sound":
            continue

        original_path = obj["sound:originalWavFilePath"]
        path = os.path.join(output_path, original_path[len(input_path):])
        filename = os.path.basename(original_path)[:-len(".wav")]

        os.makedirs(path, exist_ok=True)
        os.rename(obj["sound:convertedWemFilePath"],
                  os.path.join(path, filename+".wem"))
