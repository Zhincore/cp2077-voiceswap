import os
import json
import asyncio
import functools
import concurrent.futures
import multiprocessing
from multiprocessing import current_process
from itertools import chain
from tqdm import tqdm
from util import SubprocessException, find_files

bnk_entries = []
opusinfo = {}


def has_all(what: list, where: list):
    """Utility function that returns wether `where` has all items in `what`."""
    for item in what:
        if item not in where:
            return False
    return True


def link_sfx(map_path: str, sfx_path: str, output_dir: str, gender: str):
    """Create hard links in output_dir to SFX in sfx_path that have the configured tags in map_path."""

    tqdm.write("Loading map...")
    index = {}
    with open(map_path, "r") as f:
        index = json.loads(f.read())

    os.makedirs(output_dir, exist_ok=True)

    for event_name, event in tqdm(index.items(), desc="Finding wanted events", unit="event"):
        if not has_all(["generic_"+gender, "set_01"], item["tags"]):
            continue

        for sound in event["sounds"]:
            if not sound["found"]:
                continue

            filename = str(sound["hash"]) + ".opus"

            os.link(
                os.path.join(sfx_path, filename),
                os.path.join(output_dir, filename)
            )


async def build_sfx_event_index(metadata_path: str, sfx_path: str, output_path: str):
    """Maps event names to audio source ids"""

    bnk_entries = []

    bnk_path = os.path.join(metadata_path, "extracted")
    for file in tqdm(list(find_files(bnk_path, ".json")), desc="Loading bnk files", unit="file"):
        with open(os.path.join(bnk_path, file), "r") as f:
            bnk = json.loads(f.read())
            bnk_entries.extend(
                chain(*(s["Entries"]
                      for s in bnk["Sections"] if s["Type"] == "HIRC"))
            )

    tqdm.write("Loading opusinfo...")

    opusinfo = {}
    with open(os.path.join(sfx_path, "info.json"), "r") as f:
        opusinfo = json.loads(f.read())

    tqdm.write("Loading events metadata...")
    events = {}

    with open(os.path.join(metadata_path,
                           "base\\sound\\event\\eventsmetadata.json.json"), "r") as f:
        events = json.loads(f.read())["Data"]["RootChunk"]["root"]["Data"]

    # This could remain a chain iterator, but list gives us precise progress
    event_list = list(chain(*(v for v in events.values() if type(v) is list)))

    tqdm.write("Creating an SFX map...")
    index = {}

    try:
        await create_index(event_list, bnk_entries, opusinfo, index)
    finally:
        tqdm.write("Writing sfx index...")
        with open(output_path, "w") as f:
            f.write(json.dumps(index, indent=4))


def load_data(shared_bnk_entries: str, shared_opusinfo: str):
    global bnk_entries, opusinfo
    bnk_entries = shared_bnk_entries
    opusinfo = shared_opusinfo


async def create_index(event_list, bnk_entries, opusinfo, index: dict = None):
    index = index if index is not None else {}

    tqdm.write("Spawning subprocesses...")

    loop = asyncio.get_running_loop()
    with concurrent.futures.ProcessPoolExecutor(max_workers=None, initializer=load_data, initargs=(bnk_entries, opusinfo)) as pool:
        pbar = tqdm(total=len(event_list),
                    desc="Scanning events", unit="event")

        async def do_task(event):
            sounds = await loop.run_in_executor(pool, find_sounds, event["wwiseId"])
            index[event["redId"]["$value"]] = {
                "sounds": sounds,
                "tags": [tag["$value"] for tag in event["tags"]]
            }
            pbar.update(1)

        await asyncio.gather(*(do_task(event) for event in event_list))

    return index


def find_sounds(entry_id, switches: list = None, stack: set = None):
    entry = None
    switches = switches if switches is not None else []
    stack = stack if stack is not None else set()
    stack.add(entry_id)

    try:
        entry = next(entry for entry in bnk_entries if entry["Id"] == entry_id)
    except StopIteration:
        return []

    if entry["EntryType"] == "Sound":
        return [find_sound_opusinfo(entry["SourceId"], switches)]
    elif entry["EntryType"] == "MusicTrack":
        return [{
            "hash": source,
            "inPak": False,
            "isMusic": True,
            "filename": str(source)+".wem",
            "switches": switches,
        } for source in entry["Sources"]]
    elif entry["EntryType"] == "SwitchCntr":
        switches.append(entry)

    children = {
        "RanSeqCntr": lambda: entry["Children"],
        "MusicRanSeqCntr": lambda: entry["Children"],
        "MusicSwitchCntr": lambda: entry["Children"],
        "MusicSegment": lambda: entry["Children"],
        "SwitchCntr": lambda: entry["Groups"],
        "Action": lambda: [entry["GameObjectReferenceId"]],
        "Event": lambda: entry["Events"],
    }.get(entry["EntryType"], lambda: tqdm.write("Unexpected entry type:", entry["EntryType"]))()

    if children is None:
        return []

    sounds = []
    for child in children:
        if child in stack:
            # Loop detected
            continue

        try:
            sounds.extend(find_sounds(child, switches, stack))
        except RecursionError:
            print(f"\nRecursionError while scanning {child} from {entry}")

    return sounds


def find_sound_opusinfo(sound_hash, switches=None):
    index = -1
    try:
        index = opusinfo["OpusHashes"].index(sound_hash)
    except ValueError:
        return {"hash": sound_hash, "inPak": False, "isMusic": False, "switches": switches}

    pak_index = opusinfo["PackIndices"][index]
    index_in_pak = -1
    for i in range(index, 0, -1):
        if opusinfo["PackIndices"][i] != pak_index:
            index_in_pak = index - (i + 1)
            break

    return {
        "hash": sound_hash,
        "inPak": True,
        "isMusic": False,
        "pak": f"sfx_container_{pak_index}.opuspak",
        "indexInPak": index_in_pak,
        "opusOffset": opusinfo["OpusOffsets"][index],
        "riffOpusOffset": opusinfo["RiffOpusOffsets"][index],
        "opusStreamLength": opusinfo["OpusStreamLengths"][index],
        "wavStreamLength": opusinfo["WavStreamLengths"][index],
        "switches": switches
    }
