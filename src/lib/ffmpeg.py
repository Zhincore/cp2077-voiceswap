import os
import re
import json
import asyncio
import string
from dataclasses import dataclass
from tqdm import tqdm
from util import Parallel, SubprocessException, spawn
import config

FFMPEG_ARGS = (
    "-nostdin",
    "-hide_banner",
    "-nostats",
    *("-loglevel", "error"),
    *("-hwaccel", "auto"),
)

WAV_ARGS = (
    "-vn",
    *("-c:a", "pcm_s16le"),
    *("-ac", "2"),
    *("-ar", "44100"),
)


async def _spawn_ffmpeg(*args, **kwargs):
    return await spawn(
        "FFmpeg",
        os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg"),
        *FFMPEG_ARGS,
        *args,
        **kwargs,
    )


async def probe_volume(path: str):
    """Probes volume"""
    probe = await spawn(
        "FFmpeg",
        os.path.join(os.getenv("FFMPEG_PATH"), "ffmpeg"),
        "-nostdin",
        "-hide_banner",
        "-nostats",
        *("-i", path),
        *("-af", "volumedetect"),
        "-vn",
        "-sn",
        "-dn",
        *("-f", "null"),
        "NUL" if os.name == "nt" else "/dev/null",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _out, err = await probe.communicate()
    mean_volume = float(
        re.findall(
            r"\[Parsed_volumedetect_0 @ [^\]]+\] mean_volume: ([+-]?\d+.\d+) dB",
            err.decode(),
        )[0].strip()
    )
    max_volume = float(
        re.findall(
            r"\[Parsed_volumedetect_0 @ [^\]]+\] max_volume: ([+-]?\d+.\d+) dB",
            err.decode(),
        )[0].strip()
    )
    return {"mean": mean_volume, "max": max_volume}


async def convert(source: str, output: str, *args):
    """Converts a file to a file"""

    process = await _spawn_ffmpeg(
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
        *WAV_ARGS,
        output,
        *args,
    )


@dataclass
class InputItem:
    """Class for passing input settings for merging."""

    path: str
    volume: float = 1
    suffix: str = ".wav"
    normalize: bool = False
    optional: bool = False


def letter(i: int):
    """Returns letter"""
    return string.ascii_lowercase[i]


async def merge(
    inputs: list[InputItem],
    output_path: str,
    output_suffix=".wav",
    overwrite: bool = True,
    filter_complex: str = "anull",
):
    """Merges vocals with effects."""

    primary_item = inputs[0]
    silent = []

    async def process(base_name: str, path: str, output: str):
        input_count = 0
        filters = []
        parsed_inputs = []
        letters = ""

        for item in inputs:
            item_path = os.path.join(
                item.path,
                path,
                base_name + item.suffix,
            )
            if item.optional and not os.path.exists(item_path):
                continue  # skip it

            i = input_count
            input_count += 1

            # Add input
            parsed_inputs.extend(("-i", item_path))

            # Get letters
            l = f"[{letter(i)}]"
            letters += l

            target_volume = item.volume

            # Add filters
            if item.normalize:
                volumes = await probe_volume(item_path)

                if volumes["max"] <= -30:
                    # dont normalize this wtf
                    silent.append(os.path.join(path, base_name))
                    return

                target_volume -= volumes["max"]

            item_filters = ",".join(
                ("aresample=80000", f"alimiter=level_in={target_volume}:level=enabled")
            )
            filters.append(f"[{i}]{item_filters}{l}")

        filters.append(
            f"{letters}amix=inputs={input_count}:duration=longest,{filter_complex}"
        )
        filters = ";".join(filters)

        process = await _spawn_ffmpeg(
            *parsed_inputs,
            *("-filter_complex", filters),
            *WAV_ARGS,
            output,
            "-y",
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Merging file {base_name} failed with exit code {result}"
            )

    parallel = Parallel("Merging vocals")
    skipped = 0

    for root, _dirs, files in os.walk(primary_item.path + "/"):
        path = root[len(primary_item.path) + 1 :]
        os.makedirs(os.path.join(output_path, path), exist_ok=True)

        for name in files:
            if not name.endswith(primary_item.suffix):
                continue

            base_name = name.replace(primary_item.suffix, "")
            output = os.path.join(output_path, path, base_name + output_suffix)

            if not overwrite and os.path.exists(output):
                skipped += 1
                continue

            parallel.run(process, base_name, path, output)

    if skipped > 0:
        tqdm.write(f"Skipping {skipped} already merged files.")

    await parallel.wait()

    if len(silent) > 0:
        with open(
            os.path.join(output_path, config.MERGED_SILENT_FILENAME),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(silent, f)

        tqdm.write(
            f"Warning: {len(silent)} files are probably silent and were skipped. \n"
            + "Their paths were saved in _silent_files.json in output folder."
        )

    tqdm.write("Merging done!")
