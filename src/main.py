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
import lib.rvc as rvc
import lib.ww2ogg as ww2ogg
import lib.wwise as wwise
import config
from args import main as parser

load_dotenv(".env")


def clear_cache():
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


def map_sfx(args: Namespace):
    "Create a map of SFX events. Needs sfx_metadata and export_sfx."
    sfx_mapping.build_sfx_event_index(
        args.metadata_path,
        args.sfx_path,
        args.output,
    )


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


async def wwise_import(args: Namespace):
    """Import all found audio files to Wwise and runs conversion."""
    await wwise.convert_files(args.input, args.project, args.output)


def move_wwise_files(args: Namespace):
    """Finds the converted files and tries to find their correct location."""
    wwise.move_wwise_files_auto(args.project, args.output_path)


async def pack_files(args: Namespace):
    """Pack given folder into a .archive"""
    await wolvenkit.pack_files(args.archive, args.folder, args.output)


def zip(args: Namespace):
    """Zips given folder for distribution"""
    tqdm.write("Zipping folder...")
    shutil.make_archive(args.archive, "zip", args.folder)


async def _main():
    """Main function of the program."""

    # Run subcommand
    try:
        args = parser.parse_args(sys.argv[1:])
        if args.subcommand == "clear_cache":
            clear_cache()
        elif args.subcommand == "export_sfx":
            await export_sfx(args)
        elif args.subcommand == "sfx_metadata":
            await sfx_metadata(args)
        elif args.subcommand == "map_sfx":
            map_sfx(args)
        elif args.subcommand == "extract_files":
            await extract_files(args)
        elif args.subcommand == "export_wem":
            await export_wem(args)
        elif args.subcommand == "isolate_vocals":
            await isolate_vocals(args)
        elif args.subcommand == "revoice":
            await revoice(args)
        elif args.subcommand == "merge_vocals":
            await merge_vocals(args)
        elif args.subcommand == "wwise_import":
            await wwise_import(args)
        elif args.subcommand == "move_wwise_files":
            move_wwise_files(args)
        elif args.subcommand == "pack_files":
            await pack_files(args)
        elif args.subcommand == "zip":
            zip(args)
        elif args.subcommand == "workflow":
            from workflow import workflow
            await workflow(args)
        else:
            parser.print_help()
    except SystemExit as e:
        if e.code != 0:
            raise e


def main():
    """Main function of the program."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
