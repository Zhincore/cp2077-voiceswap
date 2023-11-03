import os
import asyncio
from itertools import chain
from util import SubprocessException, find_paths_with_files
from tqdm import tqdm


async def poetry_get_venv(path: str):
    process = await asyncio.create_subprocess_exec(
        "poetry", "env", "list", "--full-path",
        cwd=path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await process.communicate()
    return stdout.splitlines()[0].decode()


async def get_rvc_executable():
    rvc_path = os.getenv("RVC_PATH")
    venv = os.getenv("RVC_VENV")
    if venv is None or venv == "":
        venv = await poetry_get_venv(rvc_path)
    return os.path.join(rvc_path, venv, "python.exe")


async def uvr(model: str, input_path: str, output_vocals_path: str, output_rest_path: str):
    """Splits audio files to vocals and the rest."""

    cwd = os.getcwd()
    paths, total = find_paths_with_files(input_path)
    pbar = tqdm(total=total, desc="Isolating vocals", unit="file")

    for path in paths:
        tqdm.write(f"Starting UVR for folder '{path}'...")

        process = await asyncio.create_subprocess_exec(
            await get_rvc_executable(),
            os.path.join(cwd, "libs\\rvc_uvr.py"),
            model,
            os.path.join(cwd, input_path, path),
            os.path.join(cwd, output_vocals_path, path),
            os.path.join(cwd, output_rest_path, path),
            cwd=os.getenv("RVC_PATH"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,  # usually just ffmpeg spam...
        )

        while not process.stdout.at_eof():
            line = b""
            try:
                line = await asyncio.wait_for(process.stdout.readline(), 5)
            except asyncio.TimeoutError:
                pbar.update(0)

            decoded = line.decode()
            stripped = decoded.strip()

            if stripped.endswith("->Success"):
                pbar.update(1)
            elif stripped != "":
                tqdm.write(decoded)

        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting files failed with exit code {result}")

    pbar.close()


async def batch_rvc(input_path: str, opt_path: str, **kwargs):
    """Run RVC over given folder."""

    cwd = os.getcwd()
    paths, _total = find_paths_with_files(input_path)
    args = [*chain(*(("--" + k, str(v))
                   for k, v in kwargs.items() if v is not None))]

    for path in paths:
        tqdm.write(f"Starting RVC for folder '{path}'...")

        _input_path = os.path.join(cwd, input_path, path)
        _opt_path = os.path.join(cwd, opt_path, path)

        os.makedirs(_opt_path, exist_ok=True)

        process = await asyncio.create_subprocess_exec(
            await get_rvc_executable(),
            "tools\\infer_batch_rvc.py",
            "--input_path", _input_path,
            "--opt_path", _opt_path,
            *args,
            cwd=os.getenv("RVC_PATH"),
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting files failed with exit code {result}")
