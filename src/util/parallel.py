import os
import asyncio
from asyncio import Semaphore
from typing_extensions import Awaitable
from tqdm import tqdm


class Parallel:
    """Wrapper around semaphore to limit concurrency"""
    __processes: list[Awaitable] = []
    __tqdm: tqdm | None = None

    def __init__(self, title: str = None, unit="file", concurrency=os.cpu_count()):
        self.__semaphore = Semaphore(concurrency)
        self.__tqdm = tqdm(desc=title, unit=unit)

    async def __run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        async with self.__semaphore:
            result = await func(*args, **kwargs)
            self.__tqdm.update(1)
            return result

    def run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        self.__processes.append(
            asyncio.create_task(
                self.__run(func, *args, **kwargs)
            )
        )

    def log(self, message: str):
        tqdm.write(message)

    async def wait(self):
        self.__tqdm.reset(len(self.__processes))

        await asyncio.gather(*self.__processes)

        self.__tqdm.close()
