import os
from .parallel import Parallel
from .async_watchdog import watch_async


class SubprocessException(Exception):
    """Exception originating from a subprocess"""


def find_paths_with_files(input_path: str):
    """Finds all paths that contain files, returns those paths and a total count of all files"""
    paths = []
    total = 0

    # find paths that contain files
    for root, _dirs, files in os.walk(input_path):
        if len(files) > 0:
            total += len(files)
            paths.append(root[len(input_path) + 1 :] or ".")

    return paths, total


def find_files(input_path: str, ext: str = None):
    for root, _dirs, files in os.walk(input_path):
        for file in files:
            if not ext or file.endswith(ext):
                yield os.path.join(root[len(input_path) + 1 :], file)
