import os
import asyncio
from util import Parallel
import lib.ww2ogg as ww2ogg
import lib.ffmpeg as ffmpeg


async def wem2wav_all_cache(input_path: str, output_path: str):
    """Converts all cached .wem files to .wav files"""
    parallel = Parallel()
    processes = []
    done = []

    async def process(root: str, name: str):
        print(f"Converting {name} to .ogg...")

        output_file = os.path.join(
            output_path + root[len(input_path):], name[:-4])

        await ww2ogg.ww2ogg(os.path.join(root, name), output_file+".ogg")

        print(f"Converting {name} from .ogg to .wav...")

        await ffmpeg.convert(output_file+".ogg", output_file+".wav")

        os.unlink(output_file+".ogg")

        done.append(object)

        print(f"Done converting {name}!")
        print(f"{len(done)}/{len(processes)} files converted")

    for root, _dirs, files in os.walk(input_path):
        for name in files:
            if name.endswith(".wem"):
                os.makedirs(
                    output_path + root[len(input_path):], exist_ok=True)

                processes.append(
                    asyncio.create_task(
                        parallel.run(process, root, name)
                    )
                )

    await asyncio.gather(*processes)
    print("Converting done!")
