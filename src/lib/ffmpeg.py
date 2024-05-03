import os
import string
from itertools import chain
from dataclasses import dataclass
from util import Parallel, SubprocessException, spawn

FFMPEG_ARGS = (
    "-nostdin",
    "-hide_banner",
    "-nostats",
    *("-loglevel", "error"),
    *("-hwaccel", "auto"),
)


async def spawn_ffmpeg(*args, **kwargs):
    return await spawn(
        "FFmpeg",
        os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg"),
        *FFMPEG_ARGS,
        *args,
        **kwargs,
    )


async def convert(source: str, output: str, *args):
    """Converts a file to a file"""

    process = await spawn_ffmpeg(
        *("-i", source),
        *args,
        output,
        "-y",
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Converting file {source} failed with exit code {result}"
        )


async def to_wav(source: str, output: str, *args):
    """Converts source to WAV format for RVC/game."""
    return await convert(
        source,
        output,
        "-vn",
        *("-c:a", "pcm_s16le"),
        *("-ac", "2"),
        *("-ar", "44100"),
        *args,
    )


@dataclass
class InputItem:
    """Class for passing input settings for merging."""

    path: str
    volume: float = 1
    suffix: str = ".wav"
    optional: bool = False


async def merge(
    inputs: list[InputItem],
    output_path: str,
    output_suffix=".wav",
    filter_complex: str = "anull",
):
    """Merges vocals with effects."""

    items = len(inputs)
    volumes = ";".join(
        map(
            lambda v: f"[{v[0]}]volume={v[1].volume}[{string.ascii_lowercase[v[0]]}]",
            enumerate(inputs),
        )
    )
    input_map = "".join(map(lambda i: f"[{string.ascii_lowercase[i]}]", range(items)))
    primary_item = inputs[0]

    async def process(name: str, path: str):
        base_name = name.replace(primary_item.suffix, "")
        output = os.path.join(output_path, path, base_name + output_suffix)

        process = await spawn_ffmpeg(
            *chain(
                *(
                    (
                        "-i",
                        os.path.join(
                            item.path,
                            path,
                            base_name + item.suffix,
                        ),
                    )
                    for item in inputs
                )
            ),
            "-filter_complex",
            f"{volumes};{input_map}amix=inputs={items}:duration=longest,{filter_complex}",
            output,
            "-y",
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Merging file {base_name} failed with exit code {result}"
            )

    parallel = Parallel("Merging vocals")
    for root, _dirs, files in os.walk(primary_item.path + "/"):
        path = root[len(primary_item.path) + 1 :]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            if name.endswith(primary_item.suffix):
                parallel.run(process, name, path)

    await parallel.wait()
    print("Merging done!")
