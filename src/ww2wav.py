import os
import asyncio
from util import Parallel
import lib.ww2ogg as ww2ogg
import lib.ffmpeg as ffmpeg

SOURCE = ".cache\\archive"
TARGET = ".cache\\raw"


async def ww2wav_all_cache():
    """Converts all cached .wem files to .wav files"""
    parallel = Parallel()
    processes = []
    done = []

    async def process(root: str, name: str):
        print(f"Converting {name} to .ogg...")

        output = output = os.path.join(
            TARGET + root[len(SOURCE):], name[:-4])

        await ww2ogg.ww2ogg(os.path.join(root, name), output+".ogg")

        print(f"Converting {name} from .ogg to .wav...")

        await ffmpeg.convert(output+".ogg", output+".wav")

        os.unlink(output+".ogg")

        done.append(object)

        print(f"Done converting {name}!")
        print(f"{len(done)}/{len(processes)} files converted")

    for root, _dirs, files in os.walk(SOURCE):
        for name in files:
            if name.endswith(".wem"):
                os.makedirs(TARGET + root[len(SOURCE):], exist_ok=True)

                processes.append(
                    asyncio.create_task(
                        parallel.run(process, root, name)
                    )
                )

    await asyncio.gather(*processes)
    print("Converting done!")
