import os
import asyncio
from util import Parallel, SubprocessException


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


async def ww2ogg_all(input_path: str, output_path: str):
    """Converts all .wem files to .wav files"""
    parallel = Parallel()
    processes = []
    done = 0

    async def process(root: str, name: str):
        nonlocal done
        print(f"Converting {name}...")

        output_file = os.path.join(
            output_path + root[len(input_path):],
            name[:-4]
        )

        await ww2ogg(os.path.join(root, name), output_file+".ogg")

        done += 1

        print(f"Done converting {name}!")
        print(f"{done}/{len(processes)} files converted")

    for root, _dirs, files in os.walk(input_path):
        os.makedirs(output_path + root[len(input_path):], exist_ok=True)

        for name in files:
            if name.endswith(".wem"):
                processes.append(
                    asyncio.create_task(
                        parallel.run(process, root, name)
                    )
                )

    await asyncio.gather(*processes)
    print("Converting done!")
