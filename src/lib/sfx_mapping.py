import json
import os
from enum import Enum

from tqdm import tqdm


class SoundLocation(Enum):
    VIRTUAL = "virtual"
    PAK = "opuspak"
    BNK = "bnk"
    WEM = "wem"


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


def build_sfx_event_index(
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
                "pak": f"sfx_container_{pak_index}.opuspak",
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

    index = {}

    index = _create_index(eventmetadata, banks, opusinfo)

    tqdm.write("Saving SFX map...")
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


def _create_index(
    eventmetadata: dict,
    bnk_entries: dict,
    opusinfo: dict,
):
    _load_data(bnk_entries, opusinfo, eventmetadata)  # TODO: Remove globals?
    index = {}

    event_list = list(eventmetadata["events"].values())
    not_found_events = []

    found = tqdm(bar_format="Found {n_fmt} sounds", miniters=1)

    for event in tqdm(event_list, desc="Scanning events", unit="event", leave=False):
        event_name = event["redId"]["$value"]
        sounds = _find_sounds(str(event["wwiseId"]))

        if len(sounds) == 0:
            not_found_events.append(event_name)

        new_sounds = 0
        for sound_hash, sound in sounds.items():
            sound["events"] = [event_name]
            sound["tags"] = [tag["$value"] for tag in event["tags"]]

            if sound_hash in index:
                index[sound_hash] = _merge_sound_entry(index[sound_hash], sound)
            else:
                index[sound_hash] = sound
                new_sounds += 1
        found.update(new_sounds)

    found.close()

    if len(not_found_events) > 0:
        tqdm.write(f"Warning: No sounds found for {len(not_found_events)} events")

    # Sort the index
    return dict(sorted(index.items(), key=lambda a: a[0]))


def _find_sounds(
    entry_id: str, params: dict = None, stack: set = None, sounds: dict = None
):
    if (stack and entry_id in stack) or entry_id not in __g_bnk_entries:
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
    params = params.copy()
    _update_params("RTPCID", entry["data"], "gameParameter", params)
    _update_params("ulStateID", entry["data"], "state", params)
    _update_params("ulSwitchStateID", entry["data"], "stateGroup", params)
    _update_params("ulSwitchID", entry["data"], "switch", params)
    _update_params("ulSwitchGroupID", entry["data"], "switchGroup", params)

    if entry["name"] == "CAkAuxBus":
        _update_params("ulID", entry, "bus", params)

    # Our goal  # NOTE: casing issue in wwiser
    if "sourceID" in entry["data"] or "sourceId" in entry["data"]:
        _save_sound(sounds, entry, params)

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


def _save_sound(sounds: dict, entry: dict, params: dict):
    is_music = entry["name"] == "CAkMusicTrack"

    location = SoundLocation.WEM

    # Detect 0 size files
    if (
        "uInMemoryMediaSize" in entry["data"]
        and entry["data"]["uInMemoryMediaSize"][0] == "0"
    ):
        location = SoundLocation.VIRTUAL

    for source_id in entry["children"]:
        source_id_int = int(source_id)

        sound = {
            "hash": source_id_int,
            "location": location.value,
            "isMusic": is_music,
        }

        # Find if is it embedded and where
        if source_id in __g_bnk_entries:
            has_children = False
            embedded_in = []

            for sub_child in __g_bnk_entries[source_id]:
                if "bank" in sub_child["data"]:
                    embedded_in.extend(sub_child["data"]["bank"])
                elif "sourceId" in sub_child["data"]:
                    has_children = True
                    break

            # Don't save the entry if it has children
            if has_children:
                continue

            if len(embedded_in) > 0:
                embedded_in.sort()
                sound["embeddedIn"] = embedded_in
                sound["location"] = SoundLocation.BNK.value

        # Find data in opusinfo
        if source_id_int in __g_opusinfo:
            sound.update(__g_opusinfo[source_id_int])
            sound["location"] = SoundLocation.PAK.value

        # Add sorted params
        for key, value in params.items():
            if len(value) > 0:
                value.sort()
                sound[key] = value

        # Save findings
        if source_id in sounds:
            sounds[source_id] = _merge_sound_entry(sounds[source_id], sound)
        else:
            sounds[source_id] = sound


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

            entry[key] = [*value, *(v for v in new_value if v not in value)]

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
