import json
import os
import re
from itertools import chain
from multiprocessing import Pool

from tqdm import tqdm

from util import find_files

GENDERS = ["female", "male"]


def map_subtitles(path: str, locale: str):
    """Map subtitles to their audio file that matches the pattern."""

    map_paths = [
        *chain(
            find_files(path, subfolder=locale),
            find_files(path, subfolder="en-us"),
            find_files(path, subfolder="common"),
        )
    ]
    sub_paths = [*find_files(path, ".json.json", locale)]
    skip_path = f"localization/{locale}"  # this will be replaced with {} in paths

    # Make sure we have all files # Spoiler alert: We don't
    # subtitle_lists = [*find_files(path, "subtitles.json.json", locale)]

    # for file in subtitle_lists:
    #     with open(os.path.join(path, file), "r", encoding="utf-8") as f:
    #         data = json.load(f)
    #         entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]

    #         for entry in entries:
    #             depot_path = entry["subtitleFile"]["DepotPath"]["$value"]
    #             if not os.path.exists(os.path.join(path, depot_path)):
    #                 tqdm.write(f"Warning: Cannot find '{depot_path}'")

    vo_map = {}
    for file in tqdm(
        sub_paths,
        desc="Scanning subtitle files",
        unit="file",
    ):
        if os.path.basename(file).startswith(
            ("voiceovermap", "subtitles")
        ) or not file.endswith(".json.json"):
            continue

        with open(os.path.join(path, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]

            for entry in entries:
                item = {}

                for gender in GENDERS:
                    text = entry[gender + "Variant"]

                    if text and text != "":
                        item[gender] = {"text": text}

                if len(item) > 0:
                    item["_path"] = (
                        file.replace(".json.json", "")
                        .replace("\\", "/")
                        .replace(skip_path, "{}")
                    )
                    vo_map[entry["stringId"]] = item

    found_files = set()
    not_found_subtitles = set()

    for file in tqdm(map_paths, desc="Searching for mappings", unit="file"):
        filename = os.path.basename(file)
        if not filename.startswith("voiceovermap") or not filename.endswith(
            ".json.json"
        ):
            continue

        effect_type = filename.split(".", 2)[0].split("_")[-1]
        if effect_type in ("1", "voiceovermap"):
            effect_type = "main"

        with open(os.path.join(path, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]

            for entry in entries:
                if entry["stringId"] not in vo_map:
                    not_found_subtitles.add(entry["stringId"])
                    # Create item without text
                    vo_map[entry["stringId"]] = {}
                    for gender in GENDERS:
                        vo_map[entry["stringId"]][gender] = {
                            "vo": {},
                        }

                item = vo_map[entry["stringId"]]
                found_files.add(entry["stringId"])
                prev_depot = None

                for gender, subitem in item.items():
                    if gender.startswith("_"):
                        continue

                    dep_path = entry[gender + "ResPath"]["DepotPath"]["$value"]

                    if prev_depot and dep_path == prev_depot:
                        # Remove non-gendered stuff
                        del item[gender]
                        break

                    prev_depot = dep_path

                    if "vo" not in subitem:
                        subitem["vo"] = {}

                    subitem["vo"][effect_type] = dep_path.replace("\\", "/").replace(
                        skip_path, "{}"
                    )

    tqdm.write(f"Found {len(found_files)} subtitle mappings.")
    missing_vo = len(vo_map) - len(found_files)
    if missing_vo > 0:
        tqdm.write(f"Warning: Not found voiceovers for {missing_vo} subtitles!")
    missing_sub = len(not_found_subtitles)
    if missing_sub > 0:
        tqdm.write(f"Warning: Not found subtitles for {missing_sub} voiceovers!")

    return vo_map


_g_tts = None
_g_reference = None
_g_language = None


def _init_tts_worker(p_refenrece: str, p_language: str):
    global _g_tts, _g_reference, _g_language
    _g_reference = p_refenrece
    _g_language = p_language

    from TTS.api import TTS

    # Init TTS
    _g_tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")


def _tts_worker(entry):
    if len(entry) > 2:
        file_path, text, reference = entry
    else:
        file_path, text = entry
        reference = _g_reference
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    text = re.sub(r".$", "", text).replace(".", ",-;")
    if not re.match(r"\w+", text):
        return

    _g_tts.tts_to_file(
        text=text,
        speaker_wav=reference,
        language=_g_language,
        file_path=file_path,
    )


def generate_speech(
    files: list[list[str, str]], reference: str, language: str, batchsize=1
):
    """Generate text-to-speech."""
    tqdm.write("Loading TTS...")

    # Run TTS
    pbar = tqdm(total=len(files), desc="Generating speech", unit="line")
    with Pool(batchsize, _init_tts_worker, (reference, language)) as pool:
        for _ in pool.imap_unordered(_tts_worker, files):
            pbar.update(1)
