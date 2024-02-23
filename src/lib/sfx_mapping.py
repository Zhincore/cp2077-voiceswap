import asyncio
import concurrent.futures
import json
import os
from itertools import chain

from tqdm import tqdm

from util import find_files

__g_bnk_entries = {}
__g_opusinfo = {}


def has_all(what: list, where: list):
    """Utility function that returns wether `where` has all items in `what`."""
    for item in what:
        if item not in where:
            return False
    return True


def select_sfx(map_path: str, gender: str):
    """Get V's grunts of given gender."""

    tqdm.write("Loading SFX map...")
    index = {}
    with open(map_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    files = []

    for _event_name, event in tqdm(
        index.items(), desc="Finding wanted events", unit="event"
    ):
        if "v" not in event["tags"]:
            continue

        for sound in event["sounds"]:
            if sound["inPak"] and sound.get("v_gender") == gender:
                files.append(sound)

    return files


async def build_sfx_event_index(
    metadata_path: str,
    output_path: str,
    keep_empty=True,
    sound_list_format=False,
    minified=False,
):
    """Maps event names to audio source ids"""

    bnk_entries = {}

    extracted_path = os.path.join(metadata_path, "extracted")
    for file in tqdm(
        list(find_files(extracted_path, ".json")), desc="Loading bnk files", unit="file"
    ):
        if file == "sfx_container.opusinfo.json":
            continue

        with open(os.path.join(extracted_path, file), "r", encoding="utf-8") as f:
            bnk = json.load(f)

            for entry in chain(
                *(s["Entries"] for s in bnk["Sections"] if s["Type"] == "HIRC")
            ):
                if entry["Id"] not in bnk_entries:
                    bnk_entries[entry["Id"]] = []

                bnk_entries[entry["Id"]].append(entry)

    tqdm.write("Loading opusinfo...")

    opusinfo = {}
    with open(
        os.path.join(extracted_path, "sfx_container.opusinfo.json"),
        "r",
        encoding="utf-8",
    ) as f:
        opusinfo = json.load(f)

    tqdm.write("Loading events metadata...")
    events = {}

    with open(
        os.path.join(metadata_path, "base/sound/event/eventsmetadata.json.json"),
        "r",
        encoding="utf-8",
    ) as f:
        events = json.load(f)["Data"]["RootChunk"]["root"]["Data"]

    # This could remain a chain iterator, but list gives us precise progress
    event_list = list(chain(*(v for v in events.values() if isinstance(v, list))))

    tqdm.write("Creating an SFX map...")
    index = {}

    try:
        index = await _create_index(
            event_list, bnk_entries, opusinfo, keep_empty, sound_list_format
        )
    finally:
        tqdm.write("Writing sfx index...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=None if minified else 4)


def _load_data(shared_bnk_entries: str, shared_opusinfo: str):
    global __g_bnk_entries, __g_opusinfo
    __g_bnk_entries = shared_bnk_entries
    __g_opusinfo = shared_opusinfo


async def _create_index(
    event_list,
    bnk_entries,
    opusinfo,
    keep_empty=True,
    sound_list_format=False,
):
    index = {}

    tqdm.write("Spawning subprocesses...")

    loop = asyncio.get_running_loop()
    with concurrent.futures.ProcessPoolExecutor(
        initializer=_load_data, initargs=(bnk_entries, opusinfo)
    ) as pool:
        pbar = tqdm(total=len(event_list), desc="Scanning events", unit="event")

        async def do_task(event):
            sounds = await loop.run_in_executor(pool, _find_sounds, event["wwiseId"])
            if keep_empty or len(sounds) > 0:
                index[event["redId"]["$value"]] = {
                    "sounds": sounds,
                    "tags": [tag["$value"] for tag in event["tags"]],
                }
            pbar.update(1)

        await asyncio.gather(*(do_task(event) for event in event_list))

    # Convert the index into a list of sounds instead of events
    if sound_list_format:
        sounds = {}

        for event_name, event in tqdm(
            index.items(), desc="Converting to sound list format", unit="event"
        ):
            for sound in event["sounds"]:
                sound_id = sound["hash"]
                indexed_sound = sounds[sound_id] if sound_id in sounds else None

                # Create sound if not found already
                if indexed_sound is None:
                    sounds[sound_id] = {**sound, "events": [], "tags": []}
                    indexed_sound = sounds[sound_id]

                # various vibe checks
                old_pak = indexed_sound["pak"] if "pak" in indexed_sound else None
                new_pak = sound["pak"] if "pak" in sound else None
                old_index = (
                    indexed_sound["indexInPak"]
                    if "indexInPak" in indexed_sound
                    else None
                )
                new_index = sound["indexInPak"] if "indexInPak" in sound else None

                if old_pak != new_pak:
                    tqdm.write(
                        f"WARNING: Sound {sound_id} is both in {old_pak} and {new_pak}!"
                    )
                elif old_index != new_index:
                    tqdm.write(f"WARNING! Sound {sound_id} has different pak indices!")

                # Add new event name in a sorted way
                indexed_sound["events"] = list(
                    sorted(chain(indexed_sound["events"], [event_name]))
                )
                # Add new unique tags
                indexed_sound["tags"].extend(
                    [tag for tag in event["tags"] if tag not in indexed_sound["tags"]]
                )

        index = sounds

    # Sort the index
    return dict(sorted(index.items()))


def _find_sounds(entry_id, switches: list = None, stack: set = None):
    entries = None
    try:
        entries = __g_bnk_entries[entry_id]
    except KeyError:
        return []

    sounds = []

    for entry in entries:
        sounds.extend(_find_sounds_in_entry(entry, switches, stack))

    # Deduplicate
    seen_hashes = set()
    deduplicated = []
    for sound in sounds:
        if sound["hash"] not in seen_hashes:
            seen_hashes.add(sound["hash"])
            deduplicated.append(sound)

    return deduplicated


def _find_sounds_in_entry(entry, gender: str = None, stack: set = None):
    stack = stack if stack is not None else set()
    stack.add(entry["Id"])

    if entry["EntryType"] == "Sound":
        return [_find_sound_in_opusinfo(entry["SourceId"], gender)]
    elif entry["EntryType"] == "MusicTrack":
        return [
            _sound_entry(
                source,
                False,
                True,
                gender,
                {
                    "filename": str(source) + ".wem",
                },
            )
            for source in entry["Sources"]
        ]
    elif entry["EntryType"] == "SwitchCntr":
        sounds = []

        for group in entry["Groups"]:
            _gender = {
                3111576190: "male",
                2204441813: "female",
            }.get(group["SwitchId"], gender)

            sounds.extend(_find_sounds_children(group["Items"], _gender, stack))
        return sounds

    children = {
        "RanSeqCntr": lambda entry: entry["Children"],
        "LayerCntr": lambda entry: entry["Children"],
        "MusicRanSeqCntr": lambda entry: entry["Children"],
        "MusicSwitchCntr": lambda entry: entry["Children"],
        "MusicSegment": lambda entry: entry["Children"],
        "Action": lambda entry: [entry["GameObjectReferenceId"]],
        "Event": lambda entry: entry["Events"],
    }.get(
        entry["EntryType"],
        lambda entry: tqdm.write("Unexpected entry type: " + entry["EntryType"]),
    )(
        entry
    )

    return _find_sounds_children(children, gender, stack)


def _find_sounds_children(children: list, gender: str, stack: set):
    if children is None:
        return []

    sounds = []
    for child in children:
        if child in stack:
            # Loop detected
            continue

        try:
            sounds.extend(_find_sounds(child, gender, stack))
        except RecursionError:
            # tqdm.write might cause stack error
            print(f"\nRecursionError while scanning {child}, stack: {stack}")

    return sounds


def _find_sound_in_opusinfo(sound_hash, gender: str = None):
    index = -1
    try:
        index = __g_opusinfo["OpusHashes"].index(sound_hash)
    except ValueError:
        # Not found
        return _sound_entry(sound_hash, False, False, gender)

    pak_index = __g_opusinfo["PackIndices"][index]
    index_in_pak = -1
    for i in range(index, 0, -1):
        if __g_opusinfo["PackIndices"][i] != pak_index:
            index_in_pak = index - (i + 1)
            break

    return _sound_entry(
        sound_hash,
        True,
        False,
        gender,
        {
            "pak": f"sfx_container_{pak_index}.opuspak",
            "indexInPak": index_in_pak,
            "opusOffset": __g_opusinfo["OpusOffsets"][index],
            "riffOpusOffset": __g_opusinfo["RiffOpusOffsets"][index],
            "opusStreamLength": __g_opusinfo["OpusStreamLengths"][index],
            "wavStreamLength": __g_opusinfo["WavStreamLengths"][index],
        },
    )


def _sound_entry(
    sound_hash: int, in_pak: bool, is_music: bool, gender: str = None, data: dict = None
):
    entry = {
        "hash": sound_hash,
        "inPak": in_pak,
        "isMusic": is_music,
        **(data or {}),
    }
    if gender is not None:
        entry["v_gender"] = gender

    return entry
