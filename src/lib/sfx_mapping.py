import asyncio
import concurrent.futures
import json
import os
from itertools import chain
from multiprocessing import Manager

from tqdm import tqdm

__g_bnk_entries = {}
__g_opusinfo = {}

# ulSwitchId mapping to gender
_GENDERS = {
    "3111576190": "male",
    "2204441813": "female",
}


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
    banks: dict,
    metadata_path: str,
    output_path: str,
    keep_empty=True,
    sound_list_format=False,
    minified=False,
):
    """Maps event names to audio source ids"""
    extracted_path = os.path.join(metadata_path, "extracted")

    tqdm.write("Loading opusinfo...")

    opusinfo = {}
    with open(
        os.path.join(extracted_path, "sfx_container.opusinfo.json"),
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

        last_pak = -1
        index_in_pak = 0

        for index, opus_hash in enumerate(data["OpusHashes"]):
            pak_index = data["PackIndices"][index]

            if last_pak != pak_index:
                last_pak = pak_index
                index_in_pak = 0

            opusinfo[opus_hash] = {
                "pak_index": f"sfx_container_{pak_index}.opuspak",
                "indexInPak": index_in_pak,
                "opusOffset": data["OpusOffsets"][index],
                "riffOpusOffset": data["RiffOpusOffsets"][index],
                "opusStreamLength": data["OpusStreamLengths"][index],
                "wavStreamLength": data["WavStreamLengths"][index],
            }
            index_in_pak += 1

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
            event_list, banks, opusinfo, keep_empty, sound_list_format
        )
    finally:
        tqdm.write("Writing sfx index...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                index,
                f,
                indent=None if minified else 4,
                separators=(",", ":") if minified else None,
            )


def _load_data(shared_bnk_entries: str, shared_opusinfo: str):
    global __g_bnk_entries, __g_opusinfo
    __g_bnk_entries = shared_bnk_entries
    __g_opusinfo = shared_opusinfo


async def _create_index(
    event_list: list,
    bnk_entries: dict,
    opusinfo: dict,
    keep_empty=True,
    sound_list_format=False,
):
    index = {}

    tqdm.write("Preparing workers...")

    loop = asyncio.get_running_loop()
    with Manager() as manager:
        shared_bnk_entries = manager.dict(bnk_entries)
        shared_opusinfo = manager.dict(opusinfo)
        with concurrent.futures.ProcessPoolExecutor(
            initializer=_load_data, initargs=(shared_bnk_entries, shared_opusinfo)
        ) as pool:
            pbar = tqdm(total=len(event_list), desc="Scanning events", unit="event")

            async def do_task(event):
                sounds = await loop.run_in_executor(
                    pool, _find_sounds, event["wwiseId"]
                )
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
    return dict(
        sorted(
            index.items(), key=lambda a: a[0].lower() if isinstance(a[0], str) else a[0]
        )
    )


def _find_sounds(entry_id: int, switches: list = None, stack: set = None):
    entries = None
    try:
        entries = __g_bnk_entries[entry_id]
    except KeyError:
        return []

    sounds = []

    for entry in entries:
        _find_sounds_in_entry(sounds, entry, switches, stack)

    # Deduplicate
    seen_hashes = set()
    deduplicated = []
    for sound in sounds:
        if sound["hash"] not in seen_hashes:
            seen_hashes.add(sound["hash"])
            deduplicated.append(sound)

    return deduplicated


def _find_sounds_in_entry(
    sounds: list, entry: int, gender: str = None, stack: set = None
):
    # Our goal
    if entry.name in ("CAkSound", "CAkMusicTrack"):
        for child in entry.children:
            sounds.append(
                _find_sound_in_opusinfo(child, gender, entry.name == "CAkMusicTrack")
            )
        return

    # Gender detection
    if "ulSwitchID" in entry.data:
        for switch_id in entry.data["ulSwitchID"]:
            if switch_id in _GENDERS:
                gender = _GENDERS[switch_id]
                break

    stack = stack if stack is not None else set()
    stack.add(entry.ulID)
    _find_sounds_children(sounds, entry.children, gender, stack)


def _find_sounds_children(sounds: list, children: list[int], gender: str, stack: set):
    for child in children:
        if child in stack:
            # Loop detected
            continue

        try:
            sounds.extend(_find_sounds(child, gender, stack))
        except RecursionError:
            # tqdm.write might cause stack error
            print(f"\nRecursionError while scanning {child}, stack: {list(stack)}")

    return sounds


def _find_sound_in_opusinfo(sound_hash: int, gender: str = None, is_music=False):
    if sound_hash not in __g_opusinfo:
        return _sound_entry(sound_hash, False, is_music, gender)

    entry = __g_opusinfo[sound_hash]

    return _sound_entry(sound_hash, True, is_music, gender, entry)


def _sound_entry(
    sound_hash: int, in_pak: bool, is_music: bool, gender: str = None, data: dict = None
):
    entry = data or {}
    entry["hash"] = sound_hash
    entry["inPak"] = in_pak
    entry["isMusic"] = is_music
    if gender is not None:
        entry["v_gender"] = gender

    return entry
