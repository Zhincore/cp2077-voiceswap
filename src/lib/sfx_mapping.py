import os
import json
import asyncio
from itertools import chain
from tqdm import tqdm
from util import SubprocessException


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


def build_sfx_event_index(metadata_path: str, sfx_path: str, output_path: str):
    """Maps event names to audio source ids"""

    tqdm.write("Reading bnk...")
    bnk = {}

    with open(os.path.join(metadata_path,
                           "base\\sound\\soundbanks\\sfx_container.json"), "r") as f:
        bnk = json.loads(f.read())
    # This could remain a chain iterator, but list gives us precise progress
    bnk_entries = list(
        chain(*(s["Entries"] for s in bnk["Sections"] if s["Type"] == "HIRC")))

    tqdm.write("Reading events metadata...")
    events = {}

    with open(os.path.join(metadata_path,
                           "base\\sound\\event\\eventsmetadata.json.json"), "r") as f:
        events = json.loads(f.read())["Data"]["RootChunk"]["root"]["Data"]

    # This could remain a chain iterator, but list gives us precise progress
    event_list = list(chain(*(v for v in events.values() if type(v) is list)))

    tqdm.write("Reading opusinfo...")
    opusinfo = {}

    with open(os.path.join(sfx_path, "info.json"), "r") as f:
        opusinfo = json.loads(f.read())

    tqdm.write("Creating an SFX map...")
    index = create_index(bnk_entries, event_list, opusinfo)

    tqdm.write("Writing sfx index...")
    with open(output_path, "w") as f:
        f.write(json.dumps(index, indent=4))


def create_index(bnk_entries, event_list, opusinfo):
    index = {}

    for event in tqdm(event_list, desc="Scanning events", unit="event"):
        # No sounds will be found
        if event["maxDuration"] == 0:
            continue

        event_name = event["redId"]["$value"]

        sounds = find_sounds(bnk_entries, opusinfo,
                             event["wwiseId"], event_name)

        if len(sounds):
            index[event_name] = {
                "sounds": sounds,
                "tags": [tag["$value"] for tag in event["tags"]]
            }

    return index


def find_sounds(bnk_entries, opusinfo, entry_id, event_name: str):
    entry = None
    try:
        entry = next(entry for entry in bnk_entries if entry["Id"] == entry_id)
    except (StopIteration, RecursionError):
        return []

    if entry["EntryType"] == "Sound":
        return [find_sound_opusinfo(opusinfo, entry["SourceId"], event_name)]

    children = {
        "RanSeqCntr": lambda: entry["Children"],
        "Action": lambda: [entry["GameObjectReferenceId"]],
        "Event": lambda: entry["Events"],
    }.get(entry["EntryType"], lambda: None)()

    if children is None:
        return sounds

    sounds = []
    for child in children:
        sounds.extend(
            find_sounds(
                bnk_entries,
                opusinfo,
                child,
                event_name
            )
        )

    return sounds


def find_sound_opusinfo(opusinfo, sound_hash, event_name: str):
    index = -1
    try:
        index = opusinfo["OpusHashes"].index(sound_hash)
    except ValueError:
        tqdm.write(
            f"Warning: sound {sound_hash} for event {event_name} was not found in opuspaks.")
        return {"hash": sound_hash, "found": False}

    pak_index = opusinfo["PackIndices"][index]
    index_in_pak = -1
    for i in range(index, 0, -1):
        if opusinfo["PackIndices"][i] != pak_index:
            index_in_pak = index - (i + 1)
            break

    return {
        "hash": sound_hash,
        "found": True,
        "pak": f"sfx_container_{pak_index}.opuspak",
        "indexInPak": index_in_pak,
        "opusOffset": opusinfo["OpusOffsets"][index],
        "riffOpusOffset": opusinfo["RiffOpusOffsets"][index],
        "opusStreamLength": opusinfo["OpusStreamLengths"][index],
        "wavStreamLength": opusinfo["WavStreamLengths"][index],
    }
