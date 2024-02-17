import json
import os
import re

from tqdm import tqdm

from multiprocessing import Pool
from util import find_files

GENDERS = ["male", "female"]


def map_subtitles(path: str, locale: str, pattern: str, gender: str):
    """Map subtitles to their audio file that matches the pattern."""

    regex = re.compile("\\\\" + pattern)
    other_gender = GENDERS[(GENDERS.index(gender) + 1) % len(GENDERS)]

    map_paths = [*find_files(path, subfolder="en-us")]
    sub_paths = [*find_files(path, ".json.json", locale)]

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

    wanted_ids = {}

    for file in tqdm(map_paths, desc="Scanning voiceover maps", unit="file"):
        if not os.path.basename(file).startswith("voiceovermap") or not file.endswith(
            ".json.json"
        ):
            continue

        with open(os.path.join(path, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]

            for entry in entries:
                for res_path in ("femaleResPath", "maleResPath"):
                    dep_path = entry[res_path]["DepotPath"]["$value"]
                    if regex.search(dep_path):
                        wanted_ids[entry["stringId"]] = dep_path
                        break
    vo_map = {}
    for file in tqdm(
        sub_paths,
        desc="Scanning subtitle files",
        unit="file",
    ):
        if os.path.basename(file).startswith("voiceovermap") or file.endswith(
            "subtitles.json.json"
        ):
            continue

        with open(os.path.join(path, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            entries = data["Data"]["RootChunk"]["root"]["Data"]["entries"]

            for entry in entries:
                text = entry[gender + "Variant"] or entry[other_gender + "Variant"]

                if text != "" and entry["stringId"] in wanted_ids:
                    vo_map[entry["stringId"]] = (wanted_ids[entry["stringId"]], text)

                    del wanted_ids[entry["stringId"]]

    if len(wanted_ids) > 0:
        tqdm.write(f"Warning: {len(wanted_ids)} of wanted subtitles were not found.")
    tqdm.write(f"Found {len(vo_map)} subtitle entries.")

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
