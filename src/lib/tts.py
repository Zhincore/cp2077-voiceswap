import json
import os
import re

from tqdm import tqdm

from util import find_files


def map_subtitles(path: str, locale: str, pattern: str, gender: str):
    """Map subtitles to their audio file that matches the pattern."""

    regex = re.compile("\\\\" + pattern)

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

    wanted_ids = set()
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
                        wanted_ids.add(entry["stringId"])

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
                text = entry[gender + "Variant"]
                if text != "" and entry["stringId"] in wanted_ids:
                    wanted_ids.remove(entry["stringId"])
                    vo_map[entry["stringId"]] = text

    if len(wanted_ids) > 0:
        tqdm.write(f"Warning: {len(wanted_ids)} of wanted subtitles were not found.")

    return vo_map


def generate_speech(files: dict[str, str], reference: str, language: str):
    """
    Generate text-to-speech
    :param files: Dicitionary mapping output_path to text to speak.
    """
    tqdm.write("Loading TTS...")
    from TTS.api import TTS

    # Init TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)

    # Run TTS
    for file_path, text in files:
        tts.tts_to_file(
            text=text,
            speaker_wav=reference,
            language=language,
            file_path=file_path,
        )
