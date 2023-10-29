import os
import asyncio
import re
from tqdm import tqdm
from util import SubprocessException


async def export_all_sfx(opusinfo_path: str, output_dir: str):
    """Exports all sfx sounds from the given opusinfo and opuspaks."""

    tqdm.write("Reading SFX containers...")
    pbar = tqdm(desc="Exporting SFX", unit="file")

    os.makedirs(output_dir, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\OpusToolZ\\OpusToolZ.exe",
        "extract",
        os.path.abspath(opusinfo_path),
        os.path.abspath(output_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stderr = False

    while not process.stdout.at_eof():
        line = b""
        stderr = not stderr
        try:
            stream = process.stderr if stderr else process.stdout
            line = await asyncio.wait_for(stream.readline(), 1)
        except asyncio.TimeoutError:
            pbar.update(0)

        decoded = line.decode()
        stripped = decoded.strip()

        if stripped.startswith("Found"):
            numbers = re.findall(r"\d+", stripped)
            total = 0
            for number in numbers:
                total += int(number)
            pbar.reset(total)
        elif stripped.startswith("Loading") or stripped.startswith("Wrote"):
            pbar.update(1)
        elif stripped != "":
            tqdm.write(stripped)

    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Exporting SFX failed with exit code "+str(result))

    tqdm.write("Exported all SFX!")


async def repack_sfx(opusinfo_path: str, input_dir: str, output_dir: str):
    """Repacks given folder of .wav files into paks and creates opusinfo in output path."""

    tqdm.write("Reading SFX containers...")

    os.makedirs(output_dir, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\OpusToolZ\\OpusToolZ.exe",
        "repack",
        os.path.abspath(opusinfo_path),
        os.path.abspath(input_dir),
        os.path.abspath(output_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,  # opus-tools spam...
    )

    await report_repack_progress(process)
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            f"Repacking SFX failed with exit code {result}")

    tqdm.write("Repacked SFX!")


async def report_repack_progress(process):
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

        decoded = line.decode()
        stripped = decoded.strip()

        if stripped.startswith("Found") and stripped.endswith("files to pack."):
            close_pbar()

            number = re.search(r"\d+", stripped).group()
            pbar = tqdm(total=int(number), desc="Packing SFX", unit="file")
        elif stripped.startswith("Processed file"):
            pbar.update(1)

        elif stripped.startswith("Found"):
            close_pbar()

            number = re.search(r"\d+", stripped).group()
            pbar = tqdm(total=int(number), desc="Loading paks", unit="pak")
        elif stripped.startswith("Loading pak"):
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
