import asyncio
import os

from util import SubprocessException


async def convert_bnk(bnk_path: str, output_path: str):
    """Converts given bnk file into a json file."""

    process = await asyncio.create_subprocess_exec(
        "./libs/CpBnkReader/CpBnkReader.exe",
        bnk_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise SubprocessException(
            f"Reading bnk failed with exit code {process.returncode}: "
            + stderr.decode()
        )

    if os.path.exists(output_path):
        os.unlink(output_path)
    else:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(stdout)
