import asyncio
import os

from .async_watchdog import watch_async
from .parallel import Parallel


def find_paths_with_files(input_path: str):
    """Finds all paths that contain files, returns those paths and a total count of all files"""
    paths = []
    total = 0

    # find paths that contain files
    for root, _dirs, files in os.walk(input_path + "/"):
        if len(files) > 0:
            total += len(files)
            paths.append(root[len(input_path) + 1 :])

    return paths, total


def find_files(input_path: str, ext: str = None, subfolder: str = None):
    """Find files with the given extension"""
    for root, _dirs, files in os.walk(input_path + "/"):
        path = root[len(input_path) + 1 :]
        if subfolder and subfolder not in path:
            continue

        for file in files:
            if not ext or file.endswith(ext):
                yield os.path.join(path, file)


async def spawn(name, *args, **kwargs):
    """Spawn a process"""
    if "stdin" not in kwargs:
        kwargs["stdin"] = asyncio.subprocess.DEVNULL

    try:
        return await asyncio.create_subprocess_exec(*args, **kwargs)
    except FileNotFoundError as e:
        raise SubprocessException(f"Could not find {name}!") from e


class SubprocessException(RuntimeError):
    """Exception originating from a subprocess"""
