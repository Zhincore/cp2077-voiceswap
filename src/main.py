import sys
import asyncio
import argparse
from dotenv import load_dotenv
import lib.wolvenkit as wolvenkit
import lib.ffmpeg as ffmpeg
import lib.rvc as rvc
from wem2wav import wem2wav_all_cache
from config import WOLVENKIT_OUTPUT, UVR_OUTPUT, UVR_MODEL, WAV_OUTPUT

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

# wem2wav
parser_wem2wav = subcommands.add_parser(
    "wem2wav",
    help="Converts all found .wem files to .wav files"
)
parser_wem2wav.add_argument(
    "input",
    type=str,
    help="Path to folder of files to convert.",
    default=WOLVENKIT_OUTPUT,
    nargs="?"
)
parser_wem2wav.add_argument(
    "output",
    type=str,
    help="Path where to output the converted files.",
    default=WAV_OUTPUT,
    nargs="?"
)

# UVR
parser_isolate_vocals = subcommands.add_parser(
    "isolate_vocals", help="Splits audio files to vocals and the rest.")
parser_isolate_vocals.add_argument(
    "input",
    type=str,
    help="Path to folder of files to split.",
    default=WAV_OUTPUT,
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
    elif args.subcommand == "wem2wav":
        await wem2wav(args)
    elif args.subcommand == "isolate_vocals":
        await isolate_vocals(args)
    else:
        # TODO: Default command
        ...


async def extract_files(args=None):
    """Extracts files from the game matching the given pattern."""
    args = args or parser_extract_files.parse_args(sys.argv[1:])
    await wolvenkit.extract_files(args.pattern, args.output)


async def wem2wav(args=None):
    """Converts all cached .wem files to .ogg files"""
    args = args or parser_wem2wav.parse_args(sys.argv[1:])
    await wem2wav_all_cache(args.input, args.output)


async def isolate_vocals(args=None):
    """Splits audio files to vocals and the rest."""
    args = args or parser_split.parse_args(sys.argv[1:])
    await rvc.uvr(args.model, args.input, args.output)

if __name__ == "__main__":
    asyncio.run(main())
