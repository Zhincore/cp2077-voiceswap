import os
import json
import asyncio
from itertools import chain
from tqdm import tqdm
from util import SubprocessException


def patch_opuspaks(map_path: str, input_path: str, paks_path: str, output_path: str):
    """Patches opus files in input_path to correct opuspaks in paks_path and outputs them to output_path."""

    tqdm.write("Loading map...")
    index = {}
    with open(map_path, "r") as f:
        index = json.loads(f.read())

    os.makedirs(output_path, exist_ok=True)

    files = set(int(file.replace(".opus", ""))
                for file in os.listdir(input_path))
    matched = {}

    for event_name, event in tqdm(index.items(), desc="Matching files", unit="event"):
        for sound in event["sounds"]:
            if not sound["found"] or sound["hash"] not in files:
                continue

            if sound["pak"] not in matched:
                matched[sound["pak"]] = []

            matched[sound["pak"]].append(sound)
            files.remove(sound["hash"])

    for pak_name, sounds in tqdm(matched.items(), desc="Patching opuspaks", unit="pak"):
        patch_opuspak(sounds, input_path, pak_name, paks_path, output_path)

    tqdm.write("Patching done!")


def patch_opuspak(sounds: list, sound_dir: str, pak_name: str, pak_dir: str, output_dir: str):
    """Patch given opuses into given opuspak."""

    # Sort by offset so we can go sequentially
    sounds.sort(key=lambda s: s["opusOffset"])

    inpak = None
    outpak = None
    try:
        inpak = open(os.path.join(pak_dir, pak_name), "rb")
        outpak = open(os.path.join(output_dir, pak_name), "wb")

        for sound in tqdm(sounds, desc="Patching "+pak_name, unit="sound"):
            sound_id = sound["hash"]
            length = sound["opusStreamLength"] - sound["riffOpusOffset"]
            path = os.path.join(sound_dir, str(sound_id)+".opus")
            filesize = os.stat(path).st_size

            if filesize > length:
                tqdm.write(f"File {sound_id} is too big, skipping...")
                continue

            # Write skipped bytes
            offset = sound["opusOffset"] + sound["riffOpusOffset"]
            skipped = offset - inpak.tell()
            outpak.write(inpak.read(skipped))

            # Write the opus
            with open(path, "rb") as f:
                outpak.write(f.read())

            # Fill saved bytes with zeroes
            empty = length - filesize
            outpak.write(b"\0" * empty)
            inpak.seek(length, os.SEEK_CUR)  # match inpak to the same position

        remaining = os.fstat(inpak.fileno()).st_size - inpak.tell()
        if remaining > 0:
            tqdm.write("Writing remaining bytes...")
            outpak.write(inpak.read(remaining))
        elif remaining < 0:
            raise RuntimeError("Resulting pak is bigger than original!")

    finally:
        if inpak:
            inpak.close()
        if outpak:
            outpak.close()
