import asyncio
import os
from asyncio import Semaphore

from tqdm import tqdm


class Parallel:
    """Wrapper around semaphore to limit concurrency"""

    __jobs: list
    __semaphore: Semaphore
    __tqdm: tqdm
    __immediate: bool

    def __init__(
        self,
        title: str = None,
        unit="file",
        concurrency=os.cpu_count(),
        immediate=False,
        **kwargs,
    ):
        self.__jobs = []
        self.__semaphore = Semaphore(concurrency)
        self.__tqdm = tqdm(desc=title, unit=unit, **kwargs)
        self.__immediate = immediate

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
        job = self.__run(func, *args, **kwargs)
        if self.__immediate:
            job = asyncio.create_task(job)
        self.__jobs.append(job)

    def log(self, message: str):
        """tqdm.write"""
        tqdm.write(message)

    def count_jobs(self):
        """Returns the number of jobs in the queue"""
        return len(self.__jobs)

    async def wait(self):
        """Run the collected tasks."""
        self.__tqdm.reset(self.count_jobs())

        await asyncio.gather(*self.__jobs)

        self.__tqdm.close()
