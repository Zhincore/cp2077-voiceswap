import os
import re
from tqdm import tqdm
from itertools import chain
import asyncio
from util import SubprocessException
from config import WOLVENKIT_EXE


async def extract_files(pattern: str, output_path: str):
    """Extracts files from the game matching the given pattern."""
    game_path = os.getenv("CYBERPUNK_PATH")

    # Find folders that arent mod
    folders = []
    for folder in os.listdir(game_path + "\\archive\\pc"):
        if folder != "mod":
            folders.append(("-p", f"{game_path}\\archive\\pc\\{folder}"))

    tqdm.write("Starting WolvenKit unbundle...")

    process = await asyncio.create_subprocess_exec(
        WOLVENKIT_EXE,
        "unbundle",
        *(chain(*folders)),
        "-o", output_path,
        "-r", pattern
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Extracting failed with exit code " + str(result))
    tqdm.write("Extracting done!")


async def uncook_json(pattern: str, output_path: str):
    """Extract json files from the game matching the given pattern."""
    game_path = os.getenv("CYBERPUNK_PATH")

    tqdm.write("Starting WolvenKit uncook...")

    process = await asyncio.create_subprocess_exec(
        WOLVENKIT_EXE,
        "uncook",
        f"{game_path}\\archive\\pc\\content",
        "-s", "-u",
        "-r", pattern,
        "-o", output_path
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Uncooking failed with exit code " + str(result))
    tqdm.write("Uncooking done!")


async def pack_files(archive: str, input_path: str, output: str):
    """Pack given folder into a .archive"""
    tqdm.write("Starting WolvenKit pack...")

    input_path = re.sub(r"\\$", "", input_path)

    process = await asyncio.create_subprocess_exec(
        WOLVENKIT_EXE,
        "pack",
        "-p", input_path
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Packing failed with exit code " + str(result))

    tqdm.write("Moving file...")

    basename = os.path.basename(input_path)
    dirname = os.path.dirname(input_path)
    result_path = os.path.join(dirname, basename+".archive")
    output_dir = os.path.join(output, "archive\\pc\\mod")
    output_path = os.path.join(output_dir, archive+".archive")

    if os.path.exists(output_path):
        os.unlink(output_path)
    else:
        os.makedirs(output_dir, exist_ok=True)

    os.rename(result_path, output_path)
    tqdm.write(f"File moved to {output_path}")
    tqdm.write("Packing done!")
