import asyncio
import os

from tqdm import tqdm

from util import Parallel, SubprocessException, spawn


async def decode(source: str, output: str):
    """Converts game audio file to a .wav file"""

    process = await spawn(
        "vgmstream",
        "./libs/vgmstream/vgmstream-cli",
        "-i",
        *("-o", os.path.abspath(output)),
        os.path.abspath(source),
        stdout=asyncio.subprocess.DEVNULL,
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}"
        )


async def decode_all(input_path: str, output_path: str):
    """Converts all .wem files to .wav files"""
    parallel = Parallel("Exporting .wem files")

    async def process(path: str, name: str):
        input_file = os.path.join(input_path, path, name)
        output_file = os.path.join(output_path, path, name[: -len(".wem")])

        try:
            await decode(input_file, output_file + ".wav")
        except SubprocessException:
            tqdm.write(f"Converting {name} failed, continuing...")

    for root, _dirs, files in os.walk(input_path):
        path = root[len(input_path) + 1 :]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            if name.endswith(".wem"):
                parallel.run(process, path, name)

    await parallel.wait()
    tqdm.write("Exporting done!")


async def export_embedded(source: str, output_path: str):
    """Exports embedded audio files to given folder."""

    process = await spawn(
        "vgmstream",
        "./libs/vgmstream/vgmstream-cli",
        "-i",
        *("-S", "0"),
        *("-o", os.path.abspath(os.path.join(output_path, "?n.wav"))),
        os.path.abspath(source),
        stdout=asyncio.subprocess.DEVNULL,
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Exporting embedded files from {source} failed with exit code {result}"
        )
