import os
import asyncio
from util import SubprocessException


async def convert(source: str, output: str):
    """Converts a file to a file"""

    ffpath = os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg.exe")
    process = await asyncio.create_subprocess_exec(
        ffpath,
        "-hwaccel", "auto",
        "-i", source,
        output,
        "-y",
        stderr=asyncio.subprocess.DEVNULL,
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}")
