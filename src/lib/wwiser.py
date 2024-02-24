import asyncio
import concurrent.futures
import json
import os
import time
import xml.parsers.expat
from multiprocessing import Queue, current_process
from queue import Empty

from colorama import Fore
from tqdm import tqdm

_g_queue = None

# How often to update progress bars
_UPDATE_DELAY = 0.005

# Thank you https://www.nexusmods.com/cyberpunk2077/mods/11075
_CHILD_FIELDS = {
    "CAkEvent": "ulActionID",
    "CAkActionSetSwitch": "idExt",
    "CAkActionSetAkProp": "idExt",
    "CAkActionPlay": "idExt",
    "CAkActionBreak": "idExt",
    "CAkActionSeek": "idExt",
    "CAkLayerCntr": "ulChildID",
    "CAkSwitchCntr": "ulChildID",
    "CAkRanSeqCntr": "ulChildID",
    "CAkActorMixer": "ulChildID",
    "CAkMusicSwitchCntr": "ulChildID",
    "CAkMusicRanSeqCntr": "ulChildID",
    "CAkMusicSegment": "ulChildID",
    # Goals
    "CAkSound": "sourceID",
    "CAkMusicTrack": "sourceID",
}
# Fields we might need
_DATA_FILEDS = ("ulSwitchID",)


class BankObject:
    """Storage class for CAk objects"""

    name: str
    ulID: str
    children: set[str]
    data: dict

    child_field: str = None

    def __init__(self, name):
        self.name = name
        self.children = set()
        self.data = {}

        self.child_field = _CHILD_FIELDS.get(name, None)


class BanksParser:
    __p = None
    __progress = None
    __last_progress = 0

    __sources: dict

    __last_line = 0
    __object: BankObject = None
    __list_name: str = None
    __objects: dict

    def __init__(self):
        self.__p = xml.parsers.expat.ParserCreate()
        self.__p.StartElementHandler = self.__start_element
        self.__p.EndElementHandler = self.__end_element

        self.__objects = {}

    def parse(self, content: str, progress=None):
        """Parse given XML string and return result."""
        self.__progress = progress

        self.__p.Parse(content)

        return self.__objects

    def __update__progress(self):
        if self.__progress is None:
            return

        # Throttle updates
        now = time.monotonic()
        if now - self.__last_progress < _UPDATE_DELAY:
            return

        self.__last_progress = now

        # Do update
        self.__progress(self.__p.CurrentLineNumber - self.__last_line)
        self.__last_line = self.__p.CurrentLineNumber

    def __start_element(self, node_type: str, attrs: dict):
        self.__update__progress()

        name = attrs["name"] if "name" in attrs else None

        match node_type:
            case "field":
                value = attrs["value"]

                if self.__object is None:
                    return

                if name == self.__object.child_field:
                    self.__object.children.add(value)

                elif name == "ulID":
                    self.__object.ulID = value
                    if value not in self.__objects:
                        self.__objects[value] = []
                    self.__objects[value].append(self.__object)

                elif name in _DATA_FILEDS:
                    if name not in self.__object.data:
                        self.__object.data[name] = set()
                    self.__object.data[name].add(value)

            case "object":
                if name.startswith("CAk"):
                    self.__object = BankObject(name)

    def __end_element(self, _node_type: str):
        self.__update__progress()


def _parse_bank(root: str, index: int):
    global _g_queue
    p = BanksParser()

    process_id = int(current_process().name.split("-")[-1])
    total = root.count("\n")
    _g_queue.put((process_id, index, total, None))

    result = p.parse(root, lambda v: _g_queue.put((process_id, index, None, v)))

    _g_queue.put((process_id, index, None, None))

    return result


def _initialize_worker(queue):
    global _g_queue
    _g_queue = queue


async def parse_banks(filename: str):
    """Parses banks.xml"""

    result = {}
    data = ""

    tqdm.write("Reading banks.xml...")
    with open(filename, "r", encoding="utf-8") as f:
        data = f.read()

    roots = data.split("<root")
    root_count = len(roots)
    tqdm.write(f"Starting parsing for {root_count} chunks...\n")

    loop = asyncio.get_running_loop()
    max_workers = os.cpu_count()

    progress_queue = Queue()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_initialize_worker,
        initargs=(progress_queue,),
    ) as pool:
        sub_pbars = [
            tqdm(unit="lines", position=i, leave=False) for i in range(max_workers)
        ]
        pbar = tqdm(
            total=root_count,
            desc=Fore.BLUE + "Parsing banks.xml",
            unit="chunks",
            position=max_workers,
            leave=False,
        )

        async def do_task(root: str, index: int):
            sub_result = await loop.run_in_executor(
                pool, _parse_bank, "<root" + root, index
            )
            result.update(sub_result)
            pbar.update(1)

        async def watch_progress():
            while pbar.n < pbar.total:
                try:
                    worker, chunk, total, progress = progress_queue.get_nowait()
                    sub_pbar = sub_pbars[worker - 1]
                    if total is not None:
                        # New job
                        sub_pbar.set_description(
                            f"{Fore.YELLOW}Worker {worker} is parsing chunk {chunk} of {root_count}"
                        )
                        sub_pbar.reset(total)
                    elif progress is not None:
                        # Job progress
                        sub_pbar.update(progress)
                    else:
                        # Job finished
                        sub_pbar.set_description(f"{Fore.GREEN}Worker {worker} is done")
                        sub_pbar.n = sub_pbar.total
                        sub_pbar.refresh()
                except Empty:
                    await asyncio.sleep(_UPDATE_DELAY)

        await asyncio.gather(
            watch_progress(),
            *(do_task(root, i) for i, root in enumerate(roots)),
        )

        for sub_pbar in sub_pbars:
            sub_pbar.close()
        pbar.close()

    # the progress bars leave empty lines and last one isn't full width...
    tqdm.write("\nParsing banks.xml finished.")

    tqdm.write("Saving result...")
    with open("banks.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, default=_json_default)

    return result


def _json_default(d):
    match d:
        case set():
            return list(d)

    if hasattr(d, "as_dict"):
        return d.as_dict()

    if hasattr(d, "__dict__"):
        return d.__dict__

    d_type = type(d)
    raise TypeError(f"Object of type {d_type} is not JSON serializable")
