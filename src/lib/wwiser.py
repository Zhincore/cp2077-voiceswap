import asyncio
import concurrent.futures
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
        os.path.abspath("./libs/wwiser/wwiser.pyz"),
        *("-d", "xml"),
        *("-r", os.path.join(os.path.abspath(bnk_path), "**\\*.bnk")),
        cwd=os.path.abspath(output),
        stdin=asyncio.subprocess.DEVNULL,
    )

    result = await process.wait()

    if result != 0:
        raise SubprocessException(
            "Exporting banks failed with exit code " + str(result)
        )

    tqdm.write("Banks exported!")


_g_queue = None

# How often to update progress bar
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
    ulID: int
    children: set[int]
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
            case "field":
                value = attrs["value"]

                if self.__object is None:
                    return

                if name == self.__object.child_field:
                    self.__object.children.add(int(value))

                elif name == "ulID":
                    ul_id = int(value)
                    self.__object.ulID = ul_id
                    if ul_id not in self.__objects:
                        self.__objects[ul_id] = []
                    self.__objects[ul_id].append(self.__object)

                elif name in _DATA_FILEDS:
                    if name not in self.__object.data:
                        self.__object.data[name] = set()
                    self.__object.data[name].add(value)

            case "object":
                if name.startswith("CAk"):
                    self.__object = BankObject(name)

    def __end_element(self, _node_type: str):
        self.update__progress()


def _parse_bank(root: str):
    global _g_queue
    p = BanksParser()

    result = p.parse(root, _g_queue.put)

    p.update__progress(force=True)

    return result


def _initialize_worker(queue):
    global _g_queue
    _g_queue = queue


async def parse_banks(banks_folder: str):
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
            sub_result = await loop.run_in_executor(pool, _parse_bank, "<root" + root)
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

    # tqdm.write("Saving result...")
    # with open("banks.json", "w", encoding="utf-8") as f:
    #     json.dump(result, f, indent=4, default=_json_default)

    return result


def extract_embeded_sfx(banks_folder: str, output_folder: str):
    """Extracts SFX files that are embedded in the bnk files."""

    banks = {}

    last_bank = {"files": []}
    last_file = {}
    in_list = False

    p = xml.parsers.expat.ParserCreate()
    pbar = None

    def start_element(name: str, attrs: dict):
        nonlocal last_bank, last_file, in_list

        pbar.update(p.CurrentLineNumber - pbar.n)

        # Starting new bank
        if name == "root":
            last_bank = {"files": []}
            banks[os.path.join(attrs["path"], attrs["filename"])] = last_bank
            return

        obj_name = attrs["name"] if "name" in attrs else None

        if obj_name == "pData" and attrs["type"] == "gap":
            last_bank["offset"] = int(attrs["offset"])

        if name == "list" and obj_name == "pLoadedMedia":
            in_list = True
            return

        if in_list:
            match obj_name:
                case "MediaHeader":
                    last_bank["files"].append(last_file)
                    last_file = {}
                case "id" | "uOffset" | "uSize":
                    last_file[obj_name] = int(attrs["value"])

    def end_element(name: str):
        nonlocal in_list
        if name == "list":
            in_list = False

    tqdm.write("Reading banks.xml...")
    with open(os.path.join(banks_folder, "banks.xml"), "r", encoding="utf-8") as f:
        data = f.read()

        pbar = tqdm(total=data.count("\n"), desc="Parsing banks.xml", unit="lines")

        p.StartElementHandler = start_element
        p.EndElementHandler = end_element
        p.Parse("<data>" + data + "</data>")
        pbar.close()

    os.makedirs(output_folder, exist_ok=True)

    extracted_files = []
    for bnk_path, bnk in tqdm(banks.items(), desc="Scanning bnk files...", unit="file"):
        if len(bnk["files"]) == 0:
            continue

        with open(bnk_path, "rb") as f:
            for file in tqdm(
                bnk["files"], desc="Extracting files...", unit="file", position=1
            ):
                if "id" not in file or file["uOffset"] == 0:
                    continue

                out_path = os.path.join(output_folder, str(file["id"]) + ".wem")

                f.seek(bnk["offset"] + file["uOffset"])
                with open(out_path, "wb") as out:
                    out.write(f.read(file["uSize"]))

                extracted_files.append(file["id"])

    tqdm.write(f"Extracted {len(extracted_files)} embedded files.")

    return extracted_files


# def _json_default(d):
#     match d:
#         case set():
#             return list(d)

#     if hasattr(d, "as_dict"):
#         return d.as_dict()

#     if hasattr(d, "__dict__"):
#         return d.__dict__

#     d_type = type(d)
#     raise TypeError(f"Object of type {d_type} is not JSON serializable")
