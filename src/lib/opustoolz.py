import os
import asyncio
import re
from tqdm import tqdm
from util import SubprocessException


async def export_all_sfx(opusinfo_path: str, output_dir: str):
    """Exports all sfx sounds from the given opusinfo and opuspaks."""

    tqdm.write("Reading SFX containers...")
    pbar = tqdm(desc="Exporting SFX sounds")

    os.makedirs(output_dir, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        ".\\libs\\OpusToolZ\\OpusToolZ.exe",
        opusinfo_path,
        output_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    while not process.stdout.at_eof():
        line = b""
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 5)
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

    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Exporting SFX failed with exit code "+str(result))

    tqdm.write("Exported all SFX!")
