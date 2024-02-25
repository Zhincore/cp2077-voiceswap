import asyncio
import concurrent.futures
import json
import os

from tqdm import tqdm

__g_bnk_entries = {}
__g_opusinfo = {}
__g_eventsmetadata = {}


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
    eventmetadata = {}

    with open(
        os.path.join(metadata_path, "base/sound/event/eventsmetadata.json.json"),
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)["Data"]["RootChunk"]["root"]["Data"]
        for key, value in data.items():
            if isinstance(value, list):
                eventmetadata[key] = {item["wwiseId"]: item for item in value}

    tqdm.write("Creating an SFX map...")
    index = {}

    try:
        index = await _create_index(eventmetadata, banks, opusinfo)
    finally:
        tqdm.write("Writing sfx index...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                index,
                f,
                indent=None if minified else 4,
                separators=(",", ":") if minified else None,
            )


def _load_data(
    shared_bnk_entries: dict, shared_opusinfo: dict, shared_eventsmetadata: dict
):
    global __g_bnk_entries, __g_opusinfo, __g_eventsmetadata
    __g_bnk_entries = shared_bnk_entries
    __g_opusinfo = shared_opusinfo
    __g_eventsmetadata = shared_eventsmetadata


async def _create_index(
    eventmetadata: dict,
    bnk_entries: dict,
    opusinfo: dict,
):
    index = {}

    event_list = list(eventmetadata["events"].values())
    loop = asyncio.get_event_loop()
    with concurrent.futures.ProcessPoolExecutor(
        initializer=_load_data,
        initargs=(bnk_entries, opusinfo, eventmetadata),
    ) as pool:
        found = tqdm(bar_format="Found {n_fmt} sounds", miniters=1)
        pbar = tqdm(
            total=len(event_list), desc="Scanning events", unit="event", leave=False
        )

        async def do_task(event):
            sounds = await loop.run_in_executor(
                pool, _find_sounds, str(event["wwiseId"])
            )

            new_sounds = 0
            for sound_hash, sound in sounds.items():
                sound["events"] = [event["redId"]["$value"]]
                sound["tags"] = [tag["$value"] for tag in event["tags"]]

                if sound_hash in index:
                    index[sound_hash] = _merge_sound_entry(index[sound_hash], sound)
                else:
                    index[sound_hash] = sound
                    new_sounds += 1
            found.update(new_sounds)
            pbar.update(1)

        await asyncio.gather(*(do_task(event) for event in reversed(event_list)))
        pbar.close()
        found.close()

    # Sort the index
    return dict(sorted(index.items(), key=lambda a: a[0]))


def _find_sounds(
    entry_id: str, params: dict = None, stack: set = None, sounds: dict = None
):
    if (
        stack and (len(stack) > 64 or entry_id in stack)
    ) or entry_id not in __g_bnk_entries:
        return {}

    entries = __g_bnk_entries[entry_id]

    if sounds is None:
        sounds = {}
    if params is None:
        params = {}
    if stack is None:
        stack = set()
    else:
        stack = set(stack)
    stack.add(entry_id)

    for entry in entries:
        try:
            _find_sounds_in_entry(sounds, entry, params, stack)
        except RecursionError:
            str_stack = " > ".join(stack)
            # tqdm.write might cause stack error
            print(f"\nRecursionError while scanning {entry_id}, stack: {str_stack}")

    return sounds


def _find_sounds_in_entry(
    sounds: dict, entry: dict, params: dict = None, stack: set = None
):
    # Our goal
    if "sourceID" in entry["data"]:
        is_music = entry["name"] == "CAkMusicTrack"
        for child in entry["data"]["sourceID"]:
            sound = {}

            # Find where is it embedded
            embedded = False
            if child in __g_bnk_entries:
                embedded_in = [
                    obj["data"]["bank"]
                    for obj in __g_bnk_entries[child]
                    if "bank" in obj["data"]
                ]
                if len(embedded_in) > 0:
                    sound["embeddedIn"] = embedded_in
                    embedded = True

            # Find data in opusinfo
            in_pak = False
            child_hash = int(child)
            if child_hash in __g_opusinfo:
                sound.update(__g_opusinfo[child_hash])
                in_pak = True

            sound_entry = _sound_entry(child, in_pak, is_music, embedded, params, sound)
            if child in sounds:
                sounds[child] = _merge_sound_entry(sounds[child], sound_entry)
            else:
                sounds[child] = sound_entry
            return

    params = params.copy()
    _update_params("RTPCID", entry["data"], "gameParameter", params)
    _update_params("ulStateID", entry["data"], "state", params)
    _update_params("ulSwitchStateID", entry["data"], "stateGroup", params)
    _update_params("ulSwitchID", entry["data"], "switch", params)
    _update_params("ulSwitchGroupID", entry["data"], "switchGroup", params)

    if entry["name"] == "CAkAuxBus":
        _update_params("ulID", entry, "bus", params)

    for child in entry["direct_children"]:
        _find_sounds_in_entry(sounds, child, params, stack)

    for child in entry["children"]:
        _find_sounds(str(child), params, stack, sounds)


def _update_params(data_id: str, data: dict, param_name: str, params: dict):
    if data_id not in data:
        return

    if param_name not in params:
        params[param_name] = []
    else:
        params[param_name] = [*params[param_name]]

    param_values = params[param_name]

    for data_item_id in data[data_id]:
        data_item_id = int(data_item_id)
        if data_item_id not in __g_eventsmetadata[param_name]:
            continue

        value = __g_eventsmetadata[param_name][data_item_id]["redId"]["$value"]

        if value not in param_values:
            param_values.append(value)


def _sound_entry(
    sound_hash: int,
    in_pak: bool,
    is_music: bool,
    is_embedded: bool,
    params: dict = None,
    data: dict = None,
):
    entry = {
        "hash": sound_hash,
        "inPak": in_pak,
        "isMusic": is_music,
        "isEmbedded": is_embedded,
    }

    if params:
        entry.update(params)

    if data:
        entry.update(data)

    return entry


def _merge_sound_entry(entry0: dict, entry1: dict, entry_id: str = None):
    entry = {**entry0, **entry1}
    entry_id = entry_id or entry["hash"]

    for key, value in entry0.items():
        if key not in entry1:
            continue

        new_value = entry1[key]

        if isinstance(value, list):
            if not isinstance(new_value, list):
                raise ValueError(
                    f"Entry {entry_id} has mismatched types for key {key} while merging"
                )

            value.extend([v for v in new_value if v not in value])

        elif isinstance(value, dict):
            if not isinstance(new_value, dict):
                raise ValueError(
                    f"Entry {entry_id} has mismatched types for key {key} while merging"
                )

            entry[key] = _merge_sound_entry(value, new_value, entry_id)

        elif value != new_value:
            raise ValueError(
                f"Entry {entry_id} has different values for key {key} while merging"
            )

    return entry
