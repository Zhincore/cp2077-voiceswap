import asyncio
import concurrent.futures
import json
import os
import sys
import time
import xml.parsers.expat
from multiprocessing import Queue
from queue import Empty

from tqdm import tqdm

from util import SubprocessException


async def export_banks(bnk_path: str, output: str):
    """Exports banks in given folder to banks.xml in given output folder."""
    tqdm.write("Exportink bnk files...")

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        os.path.abspath("./libs/wwiser/wwiser-master/wwiser.py"),
        *("-d", "xml"),
        *("-r", os.path.join(os.path.abspath(bnk_path), "**\\*.bnk")),
        cwd=os.path.abspath(output),
        stdin=asyncio.subprocess.DEVNULL,
    )

    # TODO: Translate output into TQDM
    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Exporting banks failed with exit code " + str(result)
        )

    tqdm.write("Banks exported!")


_g_queue = None

# How often to update progress bar
_UPDATE_DELAY = 0.005

_CHILD_FIELDS = {
    "CAkEvent": "ulActionID",
    "CAkActionSetSwitch": "idExt",
    "CAkActionSetAkProp": "idExt",
    "CAkActionPlay": "idExt",
    # "CAkActionBreak": "idExt",
    # "CAkActionSeek": "idExt",
    "CAkLayerCntr": "ulChildID",  # children is pLayers
    "CAkSwitchCntr": "ulChildID",  # children is SwitchList
    "CAkRanSeqCntr": "ulChildID",
    "CAkActorMixer": "ulChildID",
    "CAkMusicSwitchCntr": "ulChildID",
    "CAkMusicRanSeqCntr": "ulChildID",
    "CAkMusicSegment": "ulChildID",
    # Additional nodes found
    "CAkLayer": "ulAssociatedChildID",
    "CAkSwitchPackage": "NodeID",
    "CAkAuxBus": "fxID",
    # Goals # NOTE: casing issue in wwiser
    "CAkFxCustom": "sourceId",  # Embedded stuff I think?
    "CAkFxShareSet": "sourceId",  # Looks like also embedded stuff??
    "CAkSound": "sourceID",
    "CAkMusicTrack": "sourceID",
}
_ID_FIELD_OVERRIDES = {  # ulID by default
    "MediaHeader": "id",
    "CAkLayer": "ulLayerID",
    "CAkSwitchPackage": "ulSwitchID",
}
_ALLOWED_LISTS = {
    "CAkLayerCntr": "pLayers",
    "CAkSwitchCntr": "SwitchList",
}
# Fields we might need
_DATA_FILEDS = (
    "uInMemoryMediaSize",
    "RTPCID",
    "ulSwitchID",
    "ulSwitchGroupID",
    "ulStateID",
    "ulSwitchStateID",
    "sourceID",
    "sourceId",  # NOTE: casing issue in wwiser
)


class BankObject:
    """Storage class for CAk objects"""

    name: str
    ulID: int
    children: set[int]
    direct_children: set["BankObject"]
    data: dict

    child_field: str = None

    def __init__(self, name):
        self.name = name
        self.children = set()
        self.direct_children = set()
        self.data = {}

        self.child_field = _CHILD_FIELDS.get(name, None)

    def as_dict(self):
        return {
            "name": self.name,
            "ulID": self.ulID,
            "children": list(self.children),
            "direct_children": list(c.as_dict() for c in self.direct_children),
            "data": {k: list(v) for k, v in self.data.items()},
        }


class BanksParser:
    __bank_folder: str
    __p = None
    __progress = None
    __last_progress = 0

    __last_line = 0
    __object: BankObject = None
    __current_list_owner: BankObject = None

    __bank_path: str
    __objects: dict

    def __init__(self, bank_folder: str):
        self.__bank_folder = bank_folder

        self.__p = xml.parsers.expat.ParserCreate()
        self.__p.StartElementHandler = self.__start_element
        self.__p.EndElementHandler = self.__end_element

        self.__objects = {}

    def parse(self, content: str, progress=None):
        """Parse given XML string and return result."""
        self.__progress = progress

        self.__p.Parse(content)

        return self.__objects

    def update__progress(self, force=False):
        """Call the progress function with progress"""
        if self.__progress is None:
            return

        # Throttle updates
        now = time.monotonic()
        if not force and now - self.__last_progress < _UPDATE_DELAY:
            return

        self.__last_progress = now

        # Do update
        self.__progress(self.__p.CurrentLineNumber - self.__last_line)
        self.__last_line = self.__p.CurrentLineNumber

    def __start_element(self, node_type: str, attrs: dict):
        self.update__progress()

        name = attrs["name"] if "name" in attrs else None

        match node_type:
            case "root":
                self.__bank_path = os.path.relpath(
                    os.path.join(attrs["path"], attrs["filename"]),
                    self.__bank_folder,
                )

            case "field":
                if self.__object is None:
                    return

                value = attrs["value"]

                if name == self.__object.child_field:
                    self.__object.children.add(value)

                if name == _ID_FIELD_OVERRIDES.get(self.__object.name, "ulID"):
                    self.__object.ulID = value

                    if (
                        self.__current_list_owner is not None
                        and self.__current_list_owner is not self.__object
                    ):
                        self.__current_list_owner.direct_children.add(self.__object)
                    else:
                        if value not in self.__objects:
                            self.__objects[value] = []
                        self.__objects[value].append(self.__object)

                if name in _DATA_FILEDS:
                    if name not in self.__object.data:
                        self.__object.data[name] = set()
                    self.__object.data[name].add(value)

            case "object":
                is_media = name == "MediaHeader"
                if is_media or name.startswith("CAk"):
                    self.__object = BankObject(name)
                    if is_media:
                        self.__object.data["bank"] = self.__bank_path

            case "list":
                if self.__object is not None and name == _ALLOWED_LISTS.get(
                    self.__object.name, None
                ):
                    self.__current_list_owner = self.__object

    def __end_element(self, node_type: str):
        self.update__progress()

        if node_type == "list":
            self.__current_list_owner = None


def _parse_bank(folder: str, root: str):
    p = BanksParser(folder)

    result = p.parse(root, _g_queue.put)

    p.update__progress(force=True)

    return result


def _initialize_worker(queue):
    global _g_queue
    _g_queue = queue


async def parse_banks(banks_folder: str, cache_path: str = None):
    """Parses banks.xml"""

    result = {}
    data = ""

    tqdm.write("Reading banks.xml...")
    with open(os.path.join(banks_folder, "banks.xml"), "r", encoding="utf-8") as f:
        data = f.read()

    roots = data.split("<root")
    root_count = len(roots)
    total_lines = data.count("\n") + root_count
    tqdm.write(f"Starting parsing of {root_count} chunks...")

    loop = asyncio.get_running_loop()
    max_workers = os.cpu_count()

    progress_queue = Queue()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_initialize_worker,
        initargs=(progress_queue,),
    ) as pool:
        pbar = tqdm(
            total=total_lines,
            desc="Parsing banks.xml",
            unit="lines",
        )

        async def do_task(root: str):
            sub_result = await loop.run_in_executor(
                pool, _parse_bank, banks_folder, "<root" + root
            )
            result.update(sub_result)

        async def watch_progress():
            while pbar.n < pbar.total:
                try:
                    pbar.update(progress_queue.get_nowait())
                except Empty:
                    await asyncio.sleep(_UPDATE_DELAY)

        await asyncio.gather(
            watch_progress(),
            *(do_task(root) for root in roots),
        )

        pbar.close()

    # the progress bars leave empty lines and last one isn't full width...
    tqdm.write("Parsing banks.xml finished.")

    if cache_path:
        tqdm.write("Saving result...")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, default=_json_default)

    return {k: [o.as_dict() for o in v] for k, v in result.items()}


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
