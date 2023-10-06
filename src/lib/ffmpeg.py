import os
import asyncio
from util import Parallel, SubprocessException
import re


def get_ffmpeg():
    return os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg.exe")


async def convert(source: str, output: str):
    """Converts a file to a file"""

    process = await asyncio.create_subprocess_exec(
        get_ffmpeg(),
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


async def merge_vocals(vocals_path: str, others_path: str, output_path: str):
    """Merges vocals with effects."""
    parallel = Parallel("Merging vocals")

    async def process(name: str, path: str):
        other_name = re.sub(r"_main_vocal\.wav$", "_others.wav", name)
        base_name = re.sub(r"\.\w+(\.reformatted.wav)?_main_vocal", "", name)
        output = os.path.join(output_path, path, base_name)

        process = await asyncio.create_subprocess_exec(
            get_ffmpeg(),
            "-hwaccel", "auto",
            "-i", os.path.join(vocals_path, path, name),
            "-i", os.path.join(others_path, path, other_name),
            "-filter_complex", "amix=inputs=2:duration=longest",
            output,
            "-y",
            stderr=asyncio.subprocess.DEVNULL,
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Merging file {base_name} failed with exit code {result}")

    for root, _dirs, files in os.walk(vocals_path):
        path = root[len(vocals_path) + 1:]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            parallel.run(process, name, path)

    await parallel.wait()
    print("Merging done!")
