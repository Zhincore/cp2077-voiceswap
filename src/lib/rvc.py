import os
import asyncio
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


async def get_executable():
    rvc_path = os.getenv("RVC_PATH")
    venv = os.getenv("RVC_VENV")
    if venv is None or venv == "":
        venv = await poetry_get_venv(rvc_path)
    return os.path.join(venv, "Scripts\\python.exe")


async def uvr(model: str, input_path: str, output_path: str):
    cwd = os.getcwd()

    # find paths that contain files
    for root, _dirs, files in os.walk(input_path):
        if len(files) == 0:
            continue

        path = root[len(input_path)+1:]
        print(f"Running UVR for {path}...")

        process = await asyncio.create_subprocess_exec(
            await get_executable(),
            os.path.join(cwd, "libs\\rvc_uvr.py"),
            model,
            os.path.join(cwd, input_path, path),
            os.path.join(cwd, output_path, path),
            cwd=os.getenv("RVC_PATH"),
        )
        result = await process.wait()

        if result != 0:
            raise SubprocessException(
                f"Converting files failed with exit code {result}")
