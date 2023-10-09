import sys
import shutil
import asyncio
from argparse import Namespace
from dotenv import load_dotenv
import lib.wolvenkit as wolvenkit
import lib.ffmpeg as ffmpeg
import lib.rvc as rvc
import lib.ww2ogg as ww2ogg
import lib.wwise as wwise
import config
from args import main as parser

load_dotenv(".env")


def main():
    """Main function of the program."""
    asyncio.run(_main())


def clear_cache():
    """Deletes the .cache folder."""
    shutil.rmtree(config.CACHE_PATH)


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
    await ffmpeg.merge_vocals(args.vocals_path, args.others_path, args.output_path)


async def wwise_import(args: Namespace):
    """Import all found audio files to Wwise and runs conversion."""
    await wwise.convert_files(args.input, args.project, args.output)


async def pack_files(args: Namespace):
    """Pack given folder into a .archive"""
    await wolvenkit.pack_files(args.archive, args.folder, args.output)


def zip(args: Namespace):
    """Zips given folder for distribution"""
    shutil.make_archive(args.archive+".zip", "zip", args.folder)


async def _main():
    """Main function of the program."""

    # Run subcommand
    args = parser.parse_args(sys.argv[1:])
    if args.subcommand == "clear_cache":
        clear_cache()
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
    elif args.subcommand == "pack_files":
        await pack_files(args)
    elif args.subcommand == "zip":
        zip(args)
    elif args.subcommand == "workflow":
        from workflow import workflow
        workflow(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
