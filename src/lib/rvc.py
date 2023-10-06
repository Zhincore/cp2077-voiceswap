import os
import asyncio
from itertools import chain
from util import SubprocessException


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
    return os.path.join(venv, "Scripts\\python.exe")


async def uvr(model: str, input_path: str, output_vocals_path: str, output_rest_path: str):
    cwd = os.getcwd()

    # find paths that contain files
    for root, _dirs, files in os.walk(input_path):
        if len(files) == 0:
            continue

        path = root[len(input_path)+1:]
        print(f"Starting UVR for {path}...")

        process = await asyncio.create_subprocess_exec(
            await get_rvc_executable(),
            os.path.join(cwd, "libs\\rvc_uvr.py"),
            model,
            os.path.join(cwd, input_path, path),
            os.path.join(cwd, output_vocals_path, path),
            os.path.join(cwd, output_rest_path, path),
            str(len(files)),
            cwd=os.getenv("RVC_PATH"),
            stderr=asyncio.subprocess.DEVNULL,  # it's primarily ffmpeg spam
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting files failed with exit code {result}")


async def batch_rvc(input_path: str, output_path: str, **kwargs):
    cwd = os.getcwd()

    # find paths that contain files
    for root, _dirs, files in os.walk(input_path):
        if len(files) == 0:
            continue

        path = root[len(input_path)+1:]
        print(f"Starting RVC for {path}...")

        process = await asyncio.create_subprocess_exec(
            await get_rvc_executable(),
            "tools\\infer_batch_rvc.py",
            "--input_path", os.path.join(cwd, input_path, path),
            "--output_path", os.path.join(cwd, output_path, path),
            *chain(*(("--"+k, v) for k, v in kwargs.items())),
            cwd=os.getenv("RVC_PATH"),
            # stderr=asyncio.subprocess.DEVNULL,  # it's primarily ffmpeg spam
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting files failed with exit code {result}")
