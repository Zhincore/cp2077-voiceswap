import os
import re

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
    """Converts source to WAV fromat for RVC/game."""
    return await convert(
        source,
        output,
        "-vn",
        *("-c:a", "pcm_s16le"),
        *("-ac", "2"),
        *("-ar", "44100"),
        *args,
    )


async def merge_vocals(
    vocals_path: str,
    others_path: str,
    output_path: str,
    voice_vol: float = 1.5,
    effect_vol: float = 1,
    filter_complex: str = "anull",
):
    """Merges vocals with effects."""
    parallel = Parallel("Merging vocals")

    async def process(name: str, path: str):
        other_name = re.sub(r"_main_vocal(\.wav)+$", "_others.wav", name)
        base_name = re.sub(
            r"\.\w+(\.reformatted.wav)?_main_vocal(\.wav)+", ".wav", name
        )
        output = os.path.join(output_path, path, base_name)

        process = await spawn_ffmpeg(
            *("-i", os.path.join(vocals_path, path, name)),
            *("-i", os.path.join(others_path, path, other_name)),
            "-filter_complex",
            f"[0]volume={voice_vol}[a];[1]volume={effect_vol}[b];[a][b]amix=inputs=2:duration=longest,{filter_complex}",
            output,
            "-y",
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Merging file {base_name} failed with exit code {result}"
            )

    for root, _dirs, files in os.walk(vocals_path):
        path = root[len(vocals_path) + 1 :]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            parallel.run(process, name, path)

    await parallel.wait()
    print("Merging done!")
