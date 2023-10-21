import os
import asyncio
from util import Parallel, SubprocessException
import re

FFMPEG_ARGS = (
    "-nostdin",
    "-hide_banner",
    "-nostats",
    "-loglevel", "error",
    "-hwaccel", "auto",
)


def get_ffmpeg():
    return os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg.exe")


async def convert(source: str, output: str):
    """Converts a file to a file"""

    process = await asyncio.create_subprocess_exec(
        get_ffmpeg(), *FFMPEG_ARGS,
        "-i", source,
        output,
        "-y",
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}")


async def merge_vocals(vocals_path: str, others_path: str, output_path: str, voice_vol: float = 1.5, effect_vol: float = 1):
    """Merges vocals with effects."""
    parallel = Parallel("Merging vocals")

    async def process(name: str, path: str):
        other_name = re.sub(r"_main_vocal(\.wav)+$", "_others.wav", name)
        base_name = re.sub(
            r"\.\w+(\.reformatted.wav)?_main_vocal(\.wav)+", ".wav", name)
        output = os.path.join(output_path, path, base_name)

        process = await asyncio.create_subprocess_exec(
            get_ffmpeg(), *FFMPEG_ARGS,
            "-i", os.path.join(vocals_path, path, name),
            "-i", os.path.join(others_path, path, other_name),
            "-filter_complex",
            f"[0]volume={voice_vol}[a];[1]volume={effect_vol}[b];[a][b]amix=inputs=2:duration=longest",
            output,
            "-y",
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


async def convert_opus(input_path: str, output_path: str):
    """Convert files to opuspak opus."""
    parallel = Parallel("Converting to opus")

    async def process(name: str, path: str):
        output_name = re.sub(r"\..+$", ".opus", name)

        process = await asyncio.create_subprocess_exec(
            get_ffmpeg(), *FFMPEG_ARGS,
            "-i", os.path.join(input_path, path, name),
            "-c:a", "libopus",
            "-sample_fmt", "fltp",
            "-serial_offset", "42",
            "-b:a", "40k",  # TODO: Match the original?
            os.path.join(output_path, path, output_name),
            "-y",
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting file {base_name} to opus failed with exit code {result}")

    for root, _dirs, files in os.walk(input_path):
        path = root[len(input_path) + 1:]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            parallel.run(process, name, path)

    await parallel.wait()
    print("Merging done!")
