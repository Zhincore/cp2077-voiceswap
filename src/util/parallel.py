import asyncio
import os
from asyncio import Semaphore

from tqdm import tqdm
from typing_extensions import Awaitable


class Parallel:
    """Wrapper around semaphore to limit concurrency"""

    __jobs: list[Awaitable] = []
    __tqdm: tqdm | None = None
    __total: int | None = None
    __prepared = False

    def __init__(
        self,
        title: str = None,
        unit="file",
        concurrency=os.cpu_count(),
        pbar=True,
        total=None,
    ):
        self.__semaphore = Semaphore(concurrency)
        self.__tqdm = tqdm(total, desc=title, unit=unit, disable=not pbar)
        self.__total = total

    async def __run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        async with self.__semaphore:
            result = await func(*args, **kwargs)
            self.__tqdm.update(1)
            return result

    def run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        if self.__prepared:
            raise RuntimeError("Cannot add tasks to already prepared Parallel.")

        self.__jobs.append(asyncio.create_task(self.__run(func, *args, **kwargs)))

    def log(self, message: str):
        """tqdm.write"""
        tqdm.write(message)

    def finished(self):
        """Manually add 1 to the finished count."""
        self.__tqdm.update(1)

    def prepare(self):
        """Initialize the progress bar and stuff. Done automatically in wait()."""
        if self.__prepared:
            return

        self.__tqdm.reset(max(self.__total or 0, len(self.__jobs)))
        self.__prepared = True

    async def wait(self):
        """Run the collected tasks."""
        self.prepare()

        await asyncio.gather(*self.__jobs)

        self.__tqdm.close()
