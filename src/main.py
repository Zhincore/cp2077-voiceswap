import asyncio
import json
import os
import shutil
import sys
from argparse import Namespace

from dotenv import load_dotenv
from tqdm import tqdm

import config
import util
from args import main as parser
from lib import (
    ffmpeg,
    opustoolz,
    rvc,
    sfx_mapping,
    tts,
    vgmstream,
    wolvenkit,
    wwise,
    wwiser,
)

load_dotenv(".env")


async def sfx_metadata(args: Namespace):
    """Extracts SFX metadata from the game."""

    parallel = util.Parallel("Extracting SFX metadata", unit="tasks", total=4)

    async def eventsmetadata():
        await wolvenkit.uncook_json("eventsmetadata\\.json", args.output)
        parallel.finished()

    async def bnk_opusinfo():
        await wolvenkit.extract_files(".*\\.(bnk|opusinfo)", args.output)
        parallel.finished()

    parallel.run(wwiser.export_banks, args.output, args.output)

    parallel.run(
        opustoolz.export_info,
        os.path.join(args.output, "base/sound/soundbanks/sfx_container.opusinfo"),
        os.path.join(args.output, "extracted/sfx_container.opusinfo.json"),
    )

    parallel.prepare()
    await bnk_opusinfo()
    await asyncio.gather(parallel.wait(), eventsmetadata())


async def map_sfx(args: Namespace):
    """Create a map of SFX events. Needs sfx_metadata."""

    banks_cache = os.path.join(args.metadata_path, "banks.json")
    banks = {}

    try:
        with open(banks_cache, "r", encoding="utf-8") as f:
            tqdm.write("Reading parsed banks cache...")
            banks = json.load(f)
    except (IOError, ValueError):
        banks = await wwiser.parse_banks(args.metadata_path, banks_cache)

    await sfx_mapping.build_sfx_event_index(
        banks,
        args.metadata_path,
        args.output,
        args.keep_empty,
        args.sound_list_format,
        args.minify,
    )


async def extract_subtitles(args: Namespace):
    """Extract subttiles and their audio file names."""

    await wolvenkit.uncook_json(
        "|".join(
            (
                "localization\\\\en-us\\\\voiceovermap.*\\.json",
                f"localization\\\\{args.locale}\\\\subtitles\\\\.*\\.json",
            ),
        ),
        args.output,
    )


async def extract_all_sfx(args: Namespace):
    """Extract all SFX including music from the game."""

    tqdm.write("Loading SFX map...")
    sfx_map = {}
    with open(args.map_path, "r", encoding="utf-8") as f:
        sfx_map = json.load(f)

    pak_hashes = set()
    other_hashes = set()

    for event in tqdm(sfx_map.values(), desc="Preparing extraction", unit="event"):
        for sound in event["sounds"]:
            if sound["inPak"]:
                pak_hashes.add(str(sound["hash"]))
            else:
                other_hashes.add(str(sound["hash"]))

    out_path = os.path.join(args.sfx_cache_path, "base\\sound\\soundbanks")
    os.makedirs(out_path, exist_ok=True)

    # Run SFX in background
    sfx_task = asyncio.create_task(
        _extract_sfx(list(pak_hashes), args.sfx_cache_path, args.output)
    )

    # Run in other thread to keep the above task running
    export_bnks = util.Parallel("Extracting embedded SFX")
    for file in util.find_files(args.metadata_path, ".bnk"):
        export_bnks.run(
            vgmstream.export_embedded,
            os.path.join(args.metadata_path, file),
            out_path,
        )
    embedded_task = asyncio.create_task(export_bnks.wait())

    await wolvenkit.extract_files(
        "base\\\\sound\\\\soundbanks\\\\.*\\.wem",
        args.sfx_cache_path,
        log=False,
    )

    not_found = 0
    for sound in tqdm(other_hashes, desc="Converting wem SFX"):
        input_path = os.path.join(
            args.sfx_cache_path, f"base\\sound\\soundbanks\\{sound}.wem"
        )
        output_path = os.path.join(args.output, f"{sound}.wav")
        if os.path.exists(input_path):
            try:
                await vgmstream.decode(input_path, output_path)
            except util.SubprocessException:
                tqdm.write(f"Converting {sound} failed, continuing...")
                not_found += 1
        else:
            tqdm.write(f"Sound {sound} not found.")
            not_found += 1

    total_other = len(other_hashes)
    tqdm.write(
        f"Finished extracting wem SFX, {not_found}/{total_other} were not found or failed."
    )

    tqdm.write("Waiting for threads to finish...")
    await asyncio.gather(embedded_task, sfx_task)

    tqdm.write("Done.")


async def _extract_sfx(hashes: list, cache_path: str, output: str, paks: list = None):
    tqdm.write("Extracting SFX containers from the game...")
    await wolvenkit.extract_files(
        "sfx_container(_("
        + ("|".join(paks) if paks else ".*")
        + ")\\.opuspak|\\.opusinfo)",
        cache_path,
        log=paks is not None,
    )

    tqdm.write("Extracting SFX audio files from the containers...")
    await opustoolz.extract_sfx(
        os.path.join(cache_path, "base/sound/soundbanks/sfx_container.opusinfo"),
        hashes,
        output,
    )


async def extract_sfx(args: Namespace):
    """Extract wanted SFX from the game."""

    tqdm.write("Finding wanted SFX files...")
    files = sfx_mapping.select_sfx(args.map_path, args.gender)
    hashes = set(file["hash"] for file in files)
    paks = set(file["pak"][len("sfx_container_") : -len(".opuspak")] for file in files)
    tqdm.write(f"Found {len(hashes)} matching SFX files in {len(paks)} paks.")

    await _extract_sfx(
        hashes, args.sfx_cache_path, os.path.join(args.output, args.gender), paks
    )


async def extract_files(args: Namespace):
    """Extracts files from the game matching the given pattern."""

    pattern = f"\\\\{args.pattern}\\.wem$"
    await wolvenkit.extract_files(pattern, args.output)


async def export_wem(args: Namespace):
    """Converts all cached .wem files to a usable format."""
    await vgmstream.decode_all(args.input, args.output)


async def isolate_vocals(args: Namespace):
    """Splits audio files to vocals and the rest."""
    await rvc.uvr(args.input, args.output_vocals, args.output_rest, args.overwrite)


async def export_subtitle_map(args: Namespace):
    """Exports voiceover map"""
    vo_map = tts.map_subtitles(
        args.subtitles_path, args.locale, args.pattern, args.gender
    )
    # sort
    vo_map = dict(sorted(vo_map.items()))

    output = args.output or os.path.join(config.METADATA_PATH, "subtitles.json")

    with open(output, mode="w", encoding="utf-8") as f:
        json.dump(vo_map, f, indent=4, ensure_ascii=False)
        tqdm.write(f"Wrote {output}!")


async def do_tts(args: Namespace):
    """Converts subtitles to speech."""

    vo_map = tts.map_subtitles(
        args.subtitles_path, args.locale, args.pattern, args.gender
    )

    is_ref_dir = os.path.isdir(args.reference)

    files = []
    done = []
    for file, text in tqdm(vo_map.items(), desc="Preparing data", unit="file"):
        orig_file = file.replace("\\", os.path.sep)
        file_path = os.path.join(args.output, orig_file.replace(".wem", ".wav"))

        if not args.overwrite and os.path.exists(file_path):
            continue

        if is_ref_dir:
            ref = None
            for f in (".wav", ".ogg"):
                ref = os.path.join(args.reference, orig_file.replace(".wem", f))
                if os.path.isfile(ref):
                    break
                ref = None

            if not ref:
                if args.fallback_reference:
                    ref = args.fallback_reference
                else:
                    raise RuntimeError(f"Reference for '{orig_file}' not found.")

            files.append((file_path, text, ref))
        else:
            files.append((file_path, text))

    done = len(vo_map) - len(files)
    tqdm.write(f"Skipping {done} voice lines already done")

    tts.generate_speech(files, args.reference, args.language, args.batchsize)


async def revoice(args: Namespace):
    """Run RVC over given folder."""
    rest_args = dict(args.__dict__)
    del rest_args["subcommand"]
    await rvc.batch_rvc(**rest_args)


async def revoice_sfx(args: Namespace):
    """Run RVC over SFX in given folder."""
    input_path = os.path.join(args.input_path, args.gender)

    rest_args = dict(args.__dict__)
    del rest_args["subcommand"]
    del rest_args["gender"]
    rest_args["input_path"] = input_path
    await rvc.batch_rvc(**rest_args)


async def merge_vocals(args: Namespace):
    """Merge vocals with effects."""
    await ffmpeg.merge_vocals(
        args.vocals_path,
        args.others_path,
        args.output_path,
        args.voice_vol,
        args.effect_vol,
        args.filter_complex,
    )


async def wwise_import(args: Namespace):
    """Import all found audio files to Wwise and runs conversion."""
    await wwise.convert_files(args.input, args.project, args.output, args.overwrite)


async def move_wwise_files(args: Namespace):
    """Finds the converted files and tries to find their correct location."""
    wwise.move_wwise_files_auto(args.project, args.output_path)


async def pack_opuspaks(args: Namespace):
    """Patch opuspaks with new opuses."""
    await opustoolz.repack_sfx(args.opusinfo, args.input_path, args.output_path)


async def pack_files(args: Namespace):
    """Pack given folder into a .archive"""
    await wolvenkit.pack_files(args.archive, args.folder, args.output)


async def zip_files(args: Namespace):
    """Zips given folder for distribution"""
    tqdm.write("Zipping folder...")
    shutil.make_archive(args.archive, "zip", args.folder)


async def main_default(_args: Namespace):
    parser.print_help()


async def _main():
    """Main function of the program."""

    args = parser.parse_args(sys.argv[1:])

    # Run subcommand
    await {
        "sfx_metadata": sfx_metadata,
        "map_sfx": map_sfx,
        "extract_subtitles": extract_subtitles,
        "extract_all_sfx": extract_all_sfx,
        "extract_sfx": extract_sfx,
        "extract": extract_files,
        "export_wem": export_wem,
        "isolate_vocals": isolate_vocals,
        "map_subtitles": export_subtitle_map,
        "tts": do_tts,
        "revoice": revoice,
        "revoice_sfx": revoice_sfx,
        "merge_vocals": merge_vocals,
        "wwise": wwise_import,
        "move_wwise_files": move_wwise_files,
        "pack_opuspaks": pack_opuspaks,
        "pack": pack_files,
        "zip": zip_files,
    }.get(args.subcommand, main_default)(args)


def main():
    """Main function of the program."""
    asyncio.run(asyncio.shield(_main()))


if __name__ == "__main__":
    main()
