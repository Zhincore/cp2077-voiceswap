import asyncio
import os
import re

from tqdm import tqdm

from lib import ffmpeg
from util import Parallel, SubprocessException, find_files


async def export_info(opusinfo_path: str, output_path: str):
    """Export opusinfo as JSON."""

    tqdm.write("Exporting opusinfo...")

    process = await asyncio.create_subprocess_exec(
        "./libs/OpusToolZ/OpusToolZ.exe",
        "info",
        os.path.abspath(opusinfo_path),
        os.path.abspath(output_path),
    )

    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Exporting opusinfo failed with exit code " + str(result)
        )

    tqdm.write("Opusinfo exported!")


async def extract_sfx(opusinfo_path: str, hashes: list[int], output_dir: str):
    """Extracts sfx of given hashes from the given opusinfo and opuspaks."""

    tqdm.write("Reading SFX containers...")
    pbar = tqdm(total=len(hashes), desc="Extracting SFX", unit="file")

    process = await asyncio.create_subprocess_exec(
        "./libs/OpusToolZ/OpusToolZ.exe",
        "extract",
        os.path.abspath(opusinfo_path),
        os.path.abspath(output_dir),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    while not process.stdout.at_eof():
        line = b""
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 1)
        except asyncio.TimeoutError:
            pbar.update(0)

        stripped = line.decode().strip()

        if stripped.startswith("Awaiting"):
            # Give hashes
            process.stdin.write(("\n".join(map(str, hashes)) + "\n\n").encode())
            await process.stdin.drain()
        elif stripped.startswith("Wrote"):
            pbar.update(1)
        elif (
            stripped != ""
            and not stripped.startswith("Found")
            and not stripped.startswith("Loading")
        ):
            tqdm.write(stripped)

    result = await process.wait()
    pbar.close()

    if result != 0:
        raise SubprocessException("Exporting SFX failed with exit code " + str(result))

    parallel = Parallel("Converting SFX to wavs")

    async def convert(file: str):
        await ffmpeg.to_wav(
            os.path.join(output_dir, file),
            os.path.join(output_dir, file.replace(".opus", ".wav")),
        )
        os.unlink(file)

    for file in find_files(output_dir, ".opus"):
        parallel.run(convert, file)

    await parallel.wait()

    tqdm.write("SFX exported!")


async def repack_sfx(opusinfo_path: str, input_dir: str, output_dir: str):
    """Repacks given folder of .wav files into paks and creates opusinfo in output path."""

    tqdm.write("Reading SFX containers...")

    os.makedirs(output_dir, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        "./libs/OpusToolZ/OpusToolZ.exe",
        "repack",
        os.path.abspath(opusinfo_path),
        os.path.abspath(input_dir),
        os.path.abspath(output_dir),
        stdout=asyncio.subprocess.PIPE,
    )

    await _report_repack_progress(process)
    result = await process.wait()

    if result != 0:
        raise SubprocessException(f"Repacking SFX failed with exit code {result}")

    tqdm.write("Repacked SFX!")


async def _report_repack_progress(process):
    pbar = None

    def close_pbar():
        if pbar:
            pbar.close()

    while not process.stdout.at_eof():
        line = b""
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 5)
        except asyncio.TimeoutError:
            pass

        stripped = line.decode().strip()

        if stripped.startswith("Found") and stripped.endswith("files to pack."):
            close_pbar()

            number = re.search(r"\d+", stripped).group()
            pbar = tqdm(total=int(number), desc="Packing SFX", unit="file")
        elif stripped.startswith("Processed file"):
            pbar.update(1)

        elif stripped.startswith("Will write"):
            close_pbar()

            number = re.search(r"\d+", stripped).group()
            pbar = tqdm(total=int(number), desc="Writing paks", unit="pak")
        elif stripped.startswith("Wrote"):
            pbar.update(1)
        elif stripped != "":
            tqdm.write(stripped)
        else:
            pbar.update(0)

    close_pbar()
