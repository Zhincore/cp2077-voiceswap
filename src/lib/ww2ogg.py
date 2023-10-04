import os
import asyncio
from util import SubprocessException


async def ww2ogg(source: str, output: str):
    """Converts a .wem file to an .ogg file"""

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\ww2ogg\\ww2ogg.exe",
        source,
        "-o", output,
        "--pcb", "libs\\ww2ogg\\packed_codebooks_aoTuV_603.bin",
        stdout=asyncio.subprocess.DEVNULL,
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}")
