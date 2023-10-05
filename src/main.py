import sys
import asyncio
import argparse
from dotenv import load_dotenv
import lib.wolvenkit as wolvenkit
import lib.ffmpeg as ffmpeg
import lib.rvc as rvc
import lib.ww2ogg as ww2ogg
from config import WOLVENKIT_OUTPUT, UVR_OUTPUT, UVR_MODEL, WW2OGG_OUTPUT

load_dotenv(".env")

parser = argparse.ArgumentParser(
    prog="voiceswap",
    description="What the program does")
subcommands = parser.add_subparsers(
    title="subcommand", dest="subcommand")

# Help
parser_help = subcommands.add_parser("help", help="Shows help.")

# Extract files
parser_extract_files = subcommands.add_parser(
    "extract_files",
    help="Extracts files from the game matching the given pattern."
)
parser_extract_files.add_argument(
    "pattern",
    type=str,
    help="The file name pattern to extract."
)
parser_extract_files.add_argument(
    "output",
    type=str,
    help="Path where to extract the files.",
    default=WOLVENKIT_OUTPUT
)

# export_wem
parser_export_wem = subcommands.add_parser(
    "export_wem",
    help="Converts all found .wem files to a usable format"
)
parser_export_wem.add_argument(
    "input",
    type=str,
    help="Path to folder of files to convert.",
    default=WOLVENKIT_OUTPUT,
    nargs="?"
)
parser_export_wem.add_argument(
    "output",
    type=str,
    help="Path where to output the converted files.",
    default=WW2OGG_OUTPUT,
    nargs="?"
)

# UVR
parser_isolate_vocals = subcommands.add_parser(
    "isolate_vocals", help="Splits audio files to vocals and the rest.")
parser_isolate_vocals.add_argument(
    "input",
    type=str,
    help="Path to folder of files to split.",
    default=WW2OGG_OUTPUT,
    nargs="?"
)
parser_isolate_vocals.add_argument(
    "output",
    type=str,
    help="Path where to output the split files.",
    default=UVR_OUTPUT,
    nargs="?"
)
parser_isolate_vocals.add_argument(
    "-m", "--model",
    type=str,
    help="Path to the model to use.",
    default=UVR_MODEL,
)


async def main():
    """Main function of the program."""

    # Run subcommand
    args = parser.parse_args(sys.argv[1:])
    if args.subcommand == "help":
        parser.print_help()
    elif args.subcommand == "extract_files":
        await extract_files(args)
    elif args.subcommand == "export_wem":
        await export_wem(args)
    elif args.subcommand == "isolate_vocals":
        await isolate_vocals(args)
    else:
        # TODO: Default command
        ...


async def extract_files(args=None):
    """Extracts files from the game matching the given pattern."""
    args = args or parser_extract_files.parse_args(sys.argv[1:])
    await wolvenkit.extract_files(args.pattern, args.output)


async def export_wem(args=None):
    """Converts all cached .wem files to a usable format."""
    args = args or parser_ww2ogg.parse_args(sys.argv[1:])
    await ww2ogg.ww2ogg_all(args.input, args.output)


async def isolate_vocals(args=None):
    """Splits audio files to vocals and the rest."""
    args = args or parser_split.parse_args(sys.argv[1:])
    await rvc.uvr(args.model, args.input, args.output)

if __name__ == "__main__":
    asyncio.run(main())
