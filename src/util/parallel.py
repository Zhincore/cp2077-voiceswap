import os
from asyncio import Semaphore


class Parallel:
    """Wrapper around semaphore to limit concurrency"""

    def __init__(self, concurrency: int = os.cpu_count()):
        self.__semaphore = Semaphore(concurrency)

    async def run(self, func: callable, *args, **kwargs):
        """Runs the given function with limited concurrency."""
        async with self.__semaphore:
            return await func(*args, **kwargs)
