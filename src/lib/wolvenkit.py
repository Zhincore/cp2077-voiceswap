import os
from itertools import chain
import asyncio
from util import SubprocessException


async def extract_files(pattern: str, output_path: str):
    """Extracts files from the game matching the given pattern."""
    game_path = os.getenv("CYBERPUNK_PATH")

    # Find folders that arent mod
    folders = []
    for folder in os.listdir(game_path + "\\archive\\pc"):
        if folder != "mod":
            folders.append(("-p", f"{game_path}\\archive\\pc\\{folder}"))

    print("Starting WolvenKit...")

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\WolvenKit\\WolvenKit.CLI.exe",
        "unbundle",
        *(chain(*folders)),
        "-o", output_path,
        "-r", pattern
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Extracting failed with exit code " + str(result))
    print("Extracting done!")


async def pack_files(path: str, output: str):
    """Pack given folder into a .archive"""
    print("Starting WolvenKit...")

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\WolvenKit\\WolvenKit.CLI.exe",
        "pack",
        "-p", path
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Packing failed with exit code " + str(result))

    basename = os.path.basename(path)
    dirname = os.path.dirname(path)
    result_path = os.path.join(dirname, basename+".archive")
    output_path = os.path.join(output, "archive\\pc\\mod\\voiceswap.archive")
    os.makedirs(output_path, exist_ok=True)
    os.rename(result_path, output_path)
    print("Packing done!")
