import sys
import asyncio
import argparse
from dotenv import load_dotenv
import lib.wolvenkit as wolvenkit
import lib.ww2ogg as ww2ogg

load_dotenv(".env")

parser = argparse.ArgumentParser(
    prog="Cyberpunk2077 VoiceSwap",
    description="What the program does")
subcommands = parser.add_subparsers(
    title="subcommand", required=True, dest="subcommand")

# Extract files
parser_extract_files = subcommands.add_parser(
    "extract_files", help="Extracts files from the game matching the given pattern.")
parser_extract_files.add_argument(
    "pattern", type=str, help="The file name pattern to extract.")

# wem2ogg
parser_wem2ogg = subcommands.add_parser(
    "wem2ogg", help="Converts all cached .wem files to .ogg files")


async def main():
    """Main function of the program."""

    # Run subcommand
    args = parser.parse_args(sys.argv[1:])
    if args.subcommand == "extract_files":
        await wolvenkit.extract_files(args.pattern)
    elif args.subcommand == "wem2ogg":
        await ww2ogg.ww2ogg_all_cache()
    else:
        parser.print_usage()


async def extract_files():
    """Extracts files from the game matching the given pattern."""
    args = parser_extract_files.parse_args(sys.argv[1:])
    await wolvenkit.extract_files(args.pattern)


async def wem2ogg():
    """Converts all cached .wem files to .ogg files"""
    await ww2ogg.ww2ogg_all_cache()

if __name__ == "__main__":
    asyncio.run(main())
