import sys
import os
import shutil
import asyncio
from argparse import Namespace
from dotenv import load_dotenv
from tqdm import tqdm
import lib.wolvenkit as wolvenkit
import lib.ffmpeg as ffmpeg
import lib.bnk_reader as bnk_reader
import lib.sfx_mapping as sfx_mapping
import lib.opustoolz as opustoolz
import lib.opuspak as opuspak
import lib.rvc as rvc
import lib.ww2ogg as ww2ogg
import lib.wwise as wwise
import config
from args import main as parser

load_dotenv(".env")


async def clear_cache():
    """Deletes the .cache folder."""
    shutil.rmtree(config.CACHE_PATH)


async def export_sfx(args: Namespace):
    """Exports all the SFX from the game."""
    tqdm.write("Extracting SFX containers from the game...")
    await wolvenkit.extract_files("sfx_container", args.output)

    tqdm.write("Exporting SFX audio files from the containers...")
    await opustoolz.export_all_sfx(args.opusinfo, args.output)


async def sfx_metadata(args: Namespace):
    """Extracts SFX metadata from the game."""

    pbar = tqdm(total=3, desc="Extracting SFX metadata")

    await wolvenkit.uncook_json("eventsmetadata.json", args.output)
    pbar.update(1)

    await wolvenkit.extract_files("sfx_container.bnk", args.output)
    pbar.update(1)

    await bnk_reader.convert_bnk(os.path.join(args.output, "base\\sound\\soundbanks\\sfx_container.bnk"),
                                 os.path.join(args.output, "base\\sound\\soundbanks\\sfx_container.json"))
    pbar.update(1)


async def map_sfx(args: Namespace):
    """Create a map of SFX events. Needs sfx_metadata and export_sfx."""
    sfx_mapping.build_sfx_event_index(
        args.metadata_path,
        args.sfx_path,
        args.output,
    )


async def select_sfx(args: Namespace):
    """Create symbolic links in output_dir to SFX in sfx_path that have the configured tags in map_path."""
    sfx_mapping.link_sfx(args.map_path, args.sfx_path,
                         args.output_dir, args.gender)


async def extract_files(args: Namespace):
    """Extracts files from the game matching the given pattern."""

    pattern = f"\\\\{args.pattern}\\.wem$"
    await wolvenkit.extract_files(pattern, args.output)


async def export_wem(args: Namespace):
    """Converts all cached .wem files to a usable format."""
    await ww2ogg.ww2ogg_all(args.input, args.output)


async def isolate_vocals(args: Namespace):
    """Splits audio files to vocals and the rest."""
    await rvc.uvr(args.model, args.input, args.output_vocals, args.output_rest)


async def revoice(args: Namespace):
    """Run RVC over given folder."""
    rest_args = dict(args.__dict__)
    del rest_args["subcommand"]
    await rvc.batch_rvc(**rest_args)


async def merge_vocals(args: Namespace):
    """Merge vocals with effects."""
    await ffmpeg.merge_vocals(args.vocals_path, args.others_path, args.output_path, args.voice_vol, args.effect_vol)


async def sfx_to_opus(args: Namespace):
    """Convert files to opuspak opus."""
    await ffmpeg.convert_opus(args.input_path, args.output_path)


async def wwise_import(args: Namespace):
    """Import all found audio files to Wwise and runs conversion."""
    await wwise.convert_files(args.input, args.project, args.output)


async def move_wwise_files(args: Namespace):
    """Finds the converted files and tries to find their correct location."""
    wwise.move_wwise_files_auto(args.project, args.output_path)


async def patch_opuspaks(args: Namespace):
    """Patch opuspaks with new opuses."""
    opuspak.patch_opuspaks(
        args.map_path, args.input_path, args.paks_path, args.output_path)


async def pack_files(args: Namespace):
    """Pack given folder into a .archive"""
    await wolvenkit.pack_files(args.archive, args.folder, args.output)


async def zip_files(args: Namespace):
    """Zips given folder for distribution"""
    tqdm.write("Zipping folder...")
    shutil.make_archive(args.archive, "zip", args.folder)


async def main_default(_args: Namespace):
    parser.print_help()


async def run_workflow(args: Namespace):
    from workflow import workflow
    await workflow(args)


async def _main():
    """Main function of the program."""

    args = parser.parse_args(sys.argv[1:])

    # Run subcommand
    try:
        await {
            "clear_cache": clear_cache,
            "export_sfx": export_sfx,
            "sfx_metadata": sfx_metadata,
            "map_sfx": map_sfx,
            "select_sfx": select_sfx,
            "extract_files": extract_files,
            "isolate_vocals": isolate_vocals,
            "revoice": revoice,
            "merge_vocals": merge_vocals,
            "sfx_to_opus": sfx_to_opus,
            "wwise_import": wwise_import,
            "move_wwise_files": move_wwise_files,
            "patch_opuspaks": patch_opuspaks,
            "pack_files": pack_files,
            "zip": zip_files,
            "workflow": run_workflow,
        }.get(args.subcommand, main_default)(args)
    except SystemExit as e:
        if e.code != 0:
            raise e


def main():
    """Main function of the program."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
