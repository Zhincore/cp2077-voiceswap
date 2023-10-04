import os
import asyncio
from util import SubprocessException


async def extract_files(pattern: str):
    """Extracts files from the game matching the given pattern."""
    game_path = os.getenv("CYBERPUNK_PATH")

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\WolvenKit\\WolvenKit.CLI.exe",
        "unbundle",
        "-p", f"{game_path}\\archive\\pc\\content",
        "-o", ".cache\\archive",
        "-r", pattern
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Extracting failed with exit code " + str(result))
    print("Extracting done!")
