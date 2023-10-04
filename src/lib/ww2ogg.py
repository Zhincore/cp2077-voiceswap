import os
import asyncio
from util import Parallel, SubprocessExceptio

SOURCE = ".cache\\archive"
TARGET = ".cache\\raw"


async def ww2ogg_all_cache():
    """Converts all cached .wem files to .ogg files"""
    parallel = Parallel()
    processes = []
    done = []

    async def process(name: str, source: str, output: str):
        print(f"Converting {name}...")

        await ww2ogg(source, output)
        done.append(object)

        print(f"Done converting {name}!")
        print(f"{len(done)}/{len(processes)} files converted")

    for root, _dirs, files in os.walk(SOURCE):
        for name in files:
            if name.endswith(".wem"):
                output = os.path.join(
                    TARGET + root[len(SOURCE):], name[:-4] + ".ogg")
                os.makedirs(TARGET + root[len(SOURCE):], exist_ok=True)

                processes.append(asyncio.create_task(parallel.run(
                    process, name, os.path.join(root, name), output)))

    await asyncio.gather(*processes)
    print("Converting done!")


async def ww2ogg(source: str, output: str):
    """Converts a .wem file to an .ogg file"""

    process = await asyncio.create_subprocess_exec(".\\libs\\ww2ogg\\ww2ogg.exe",
                                                   source,
                                                   "-o", output,
                                                   "--pcb", "libs\\ww2ogg\\packed_codebooks_aoTuV_603.bin",
                                                   stdout=asyncio.subprocess.DEVNULL,
                                                   )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}")
