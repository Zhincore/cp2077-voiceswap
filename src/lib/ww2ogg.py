import asyncio
import os

from tqdm import tqdm

from util import Parallel, SubprocessException, spawn


async def ww2ogg(source: str, output: str):
    """Converts a .wem file to an .ogg file"""

    process = await spawn(
        "ww2ogg",
        "./libs/ww2ogg/ww2ogg.exe",
        source,
        *("-o", output),
        *("--pcb", "libs/ww2ogg/packed_codebooks_aoTuV_603.bin"),
        stdout=asyncio.subprocess.DEVNULL,
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}"
        )


async def ww2ogg_all(input_path: str, output_path: str):
    """Converts all .wem files to .wav files"""
    parallel = Parallel("Exporting .wem files")

    async def process(path: str, name: str):
        input_file = os.path.join(input_path, path, name)
        output_file = os.path.join(output_path, path, name[: -len(".wem")])

        await ww2ogg(input_file, output_file + ".ogg")

    for root, _dirs, files in os.walk(input_path):
        path = root[len(input_path) + 1 :]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            if name.endswith(".wem"):
                parallel.run(process, path, name)

    await parallel.wait()
    tqdm.write("Exporting done!")
