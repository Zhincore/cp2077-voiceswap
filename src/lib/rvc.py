import asyncio
import os
import shutil
from itertools import chain

from tqdm import tqdm

import config
import lib.ffmpeg as ffmpeg
from util import Parallel, SubprocessException, find_files, spawn


async def _poetry_get_venv(path: str):
    process = await spawn(
        "Poetry",
        "poetry",
        "env",
        "list",
        "--full-path",
        cwd=path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _stderr = await process.communicate()
    return stdout.splitlines()[0].decode()


async def _get_rvc_executable():
    rvc_path = os.getenv("RVC_PATH")
    venv = os.getenv("RVC_VENV")
    if venv is None or venv == "":
        venv = await _poetry_get_venv(rvc_path)
    return os.path.join(rvc_path, venv, "python.exe")


async def uvr(
    input_path: str,
    output_vocals_path: str,
    output_rest_path: str,
    overwrite: bool = True,
):
    """Splits audio files to vocals and the rest."""

    cwd = os.getcwd()

    parallel = Parallel("Isolating vocals")

    uvr_process = await spawn(
        "RVC's venv python",
        await _get_rvc_executable(),
        os.path.join(cwd, "libs/rvc_uvr.py"),
        os.path.join(cwd, config.TMP_PATH),
        os.path.join(cwd, output_vocals_path),
        os.path.join(cwd, output_rest_path),
        cwd=os.getenv("RVC_PATH"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    callbacks = {}
    loop = asyncio.get_event_loop()

    async def submit(file: str):
        future = loop.create_future()

        def callback():
            future.set_result(None)
            del callbacks[file]

        callbacks[file] = callback
        uvr_process.stdin.write((file + "\n").encode())
        await uvr_process.stdin.drain()

        return await future

    async def checker():
        while uvr_process.returncode is None:
            try:
                line = await asyncio.wait_for(uvr_process.stdout.readline(), 5)
                file = line.strip()
                if file in callbacks:
                    callbacks[file]()
                elif file != "":
                    tqdm.write(file)
            except asyncio.TimeoutError:
                pass

    dontoverwrite = {}

    if not overwrite:
        for root, _dirs, files in os.walk(output_vocals_path):
            dontoverwrite[root] = list(files)

    async def process(path):
        path_dir = os.path.dirname(path)

        if not overwrite:
            basename = os.path.basename(path)
            for file in dontoverwrite[os.path.join(output_vocals_path, path_dir)]:
                if file.startswith(basename):
                    return

        os.makedirs(os.path.join(config.TMP_PATH, path_dir), exist_ok=True)

        tmp_path = path + ".reformatted.wav"
        await ffmpeg.to_wav(
            os.path.join(input_path, path),
            os.path.join(config.TMP_PATH, tmp_path),
        )
        await submit(tmp_path)

    for path in find_files(input_path):
        parallel.run(process, path)

    checker_task = asyncio.create_task(checker())
    await parallel.wait()
    uvr_process.stdin.write_eof()
    await checker_task

    result = await uvr_process.wait()
    if result != 0:
        raise SubprocessException(f"Converting files failed with exit code {result}")

    tqdm.write("Cleaning up...")
    shutil.rmtree(config.TMP_PATH)


async def batch_rvc(input_path: str, opt_path: str, **kwargs):
    """Run RVC over given folder."""

    cwd = os.getcwd()

    tqdm.write("Starting RVC...")

    _input_path = os.path.join(cwd, input_path)
    _opt_path = os.path.join(cwd, opt_path)

    os.makedirs(_opt_path, exist_ok=True)

    process = await spawn(
        "RVC's venv python",
        await _get_rvc_executable(),
        os.path.join(cwd, "libs/infer_batch_rvc.py"),
        *("--input_path", _input_path),
        *("--opt_path", _opt_path),
        *chain(*(("--" + k, str(v)) for k, v in kwargs.items() if v is not None)),
        cwd=os.getenv("RVC_PATH"),
    )
    result = await process.wait()

    if result != 0:
        raise SubprocessException(f"Converting files failed with exit code {result}")
