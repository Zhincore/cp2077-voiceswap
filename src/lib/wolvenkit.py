import os
from itertools import chain
import asyncio
from util import SubprocessException


async def extract_files(pattern: str, output_path: str):
    """Extracts files from the game matching the given pattern."""
    game_path = os.getenv("CYBERPUNK_PATH")

    folders = []
    for folder in os.listdir(game_path + "\\archive\\pc"):
        if folder != "mod":
            folders.append(("-p", f"{game_path}\\archive\\pc\\{folder}"))

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

async def pack_files(path: str):
    """Pack given folder into a .archive"""
    process = await asyncio.create_subprocess_exec(
        ".\\libs\\WolvenKit\\WolvenKit.CLI.exe",
        "pack",
        "-p", path
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Packing failed with exit code " + str(result))
    print("Packing done!")
