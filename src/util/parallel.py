import asyncio
import os
from asyncio import Semaphore

from tqdm import tqdm


class Parallel:
    """Wrapper around semaphore to limit concurrency"""

    __jobs: list
    __semaphore: Semaphore
    __tqdm: tqdm
    __total: int

    def __init__(
        self,
        title: str = None,
        unit="file",
        concurrency=os.cpu_count(),
    ):
        self.__jobs = []
        self.__semaphore = Semaphore(concurrency)
        self.__tqdm = tqdm(desc=title, unit=unit)

    async def __run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        async with self.__semaphore:
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.__tqdm.update(1)

    def run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        self.__jobs.append(asyncio.create_task(self.__run(func, *args, **kwargs)))

    def log(self, message: str):
        """tqdm.write"""
        tqdm.write(message)

    async def wait(self):
        """Run the collected tasks."""
        self.__tqdm.reset(len(self.__jobs))

        await asyncio.gather(*self.__jobs)

        self.__tqdm.close()
