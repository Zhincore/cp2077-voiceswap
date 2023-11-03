import asyncio
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _EventHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue, *args, **kwargs):
        self.__queue = queue
        super().__init__(*args, **kwargs)

    def on_created(self, event: FileSystemEvent) -> None:
        self.__queue.put_nowait(event)


def watch_async(path: str, recursive: bool = False):
    """Watch a directory for changes."""
    queue = asyncio.Queue()

    handler = _EventHandler(queue)

    observer = Observer()
    observer.schedule(handler, path, recursive=recursive)
    observer.start()

    return queue, observer
