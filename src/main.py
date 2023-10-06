import sys
import shutil
import asyncio
import argparse
from dotenv import load_dotenv
import lib.wolvenkit as wolvenkit
import lib.ffmpeg as ffmpeg
import lib.rvc as rvc
import lib.ww2ogg as ww2ogg
import config

load_dotenv(".env")

parser = argparse.ArgumentParser(
    prog="voiceswap",
    description="Tool for automating the creation of AI voice-over mods for Cyberpunk 2077."
)
subcommands = parser.add_subparsers(title="subcommands", dest="subcommand")

# Help
parser_help = subcommands.add_parser("help", help="Shows help.")


# Clear cache
parser_clear = subcommands.add_parser(
    "clear_cache",
    help="Deletes the .cache folder."
)

# Extract files
parser_extract_files = subcommands.add_parser(
    "extract_files",
    help="Extracts files matching the given regex pattern from the game."
)
parser_extract_files.add_argument(
    "pattern",
    type=str,
    help="The file name regex pattern to match against.",
    default="\\\\v_(?!posessed).*_f_.*\\.wem$",
    nargs=argparse.OPTIONAL,
)
parser_extract_files.add_argument(
    "output",
    type=str,
    help="Path where to extract the files.",
    default=config.WOLVENKIT_OUTPUT,
    nargs=argparse.OPTIONAL,
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
    default=config.WOLVENKIT_OUTPUT,
    nargs=argparse.OPTIONAL,
)
parser_export_wem.add_argument(
    "output",
    type=str,
    help="Path where to output the converted files.",
    default=config.WW2OGG_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Isolate vocals
parser_isolate_vocals = subcommands.add_parser(
    "isolate_vocals", help="Splits audio files to vocals and the rest.")
parser_isolate_vocals.add_argument(
    "input",
    type=str,
    help="Path to folder of files to split.",
    default=config.WW2OGG_OUTPUT,
    nargs=argparse.OPTIONAL,
)
parser_isolate_vocals.add_argument(
    "output_vocals",
    type=str,
    help="Path where to output the vocals.",
    default=config.UVR_OUTPUT_VOCALS,
    nargs=argparse.OPTIONAL,
)
parser_isolate_vocals.add_argument(
    "output_rest",
    type=str,
    help="Path where to output the rest.",
    default=config.UVR_OUTPUT_REST,
    nargs=argparse.OPTIONAL,
)
parser_isolate_vocals.add_argument(
    "-m", "--model",
    type=str,
    help="Path to the model to use.",
    default=config.UVR_MODEL,
)

# Revoice
parser_revoice = subcommands.add_parser(
    "revoice", help="Run RVC over given folder.")
# Copied over from https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/tools/infer_batch_rvc.py
parser_revoice.add_argument(
    "--f0up_key",
    type=int,
    default=0,
)
parser_revoice.add_argument(
    "--input_path",
    type=str,
    help="input path, relative to VoiceSwap",
    default=config.UVR_OUTPUT_VOCALS,
)
parser_revoice.add_argument(
    "--index_path",
    type=str,
    help="index path, relative to RVC",
)
parser_revoice.add_argument(
    "--f0method",
    type=str,
    default="rmvpe",
    help="harvest or pm or rmvpe or others",
)
parser_revoice.add_argument(
    "--opt_path",
    type=str,
    help="output path, relative to VoiceSwap",
    default=config.RVC_OUTPUT,
)
parser_revoice.add_argument(
    "--model_name",
    type=str,
    help="Model'S filename in assets/weights folder",
    required=True
)
parser_revoice.add_argument(
    "--index_rate",
    type=float,
    default=0.5,
    help="index rate",
)
parser_revoice.add_argument(
    "--device",
    type=str,
    help="gpu id or 'cpu'",
)
parser_revoice.add_argument(
    "--is_half",
    type=bool,
    help="use half -> True",
)
parser_revoice.add_argument(
    "--filter_radius",
    type=int,
    help="filter radius",
)
parser_revoice.add_argument(
    "--resample_sr",
    type=int,
    help="resample sr, causes issues in current RVC's versions",
)
parser_revoice.add_argument(
    "--rms_mix_rate",
    type=float,
    default=0.05,
    help="rms mix rate, I think this is the volume envelope stuff? The higher the more constant volume, the lower the more original volume.",
)
parser_revoice.add_argument(
    "--protect",
    type=float,
    default=0.4,
    help="protect soundless vowels or something, 0.5 = disabled",
)

# Merge vocals
parser_merge_vocals = subcommands.add_parser(
    "merge_vocals", help="Merge vocals with effects.")
parser_merge_vocals.add_argument(
    "vocals_path",
    type=str,
    help="Path to folder of vocals.",
    default=config.RVC_OUTPUT,
    nargs=argparse.OPTIONAL,
)
parser_merge_vocals.add_argument(
    "others_path",
    type=str,
    help="Path to folder of effects.",
    default=config.UVR_OUTPUT_REST,
    nargs=argparse.OPTIONAL,
)
parser_merge_vocals.add_argument(
    "output_path",
    type=str,
    help="Path where to output the merged files.",
    default=config.MERGED_OUTPUT,
    nargs=argparse.OPTIONAL,
)


async def main():
    """Main function of the program."""

    # Run subcommand
    args = parser.parse_args(sys.argv[1:])
    if args.subcommand == "help":
        parser.print_help()
    elif args.subcommand == "clear_cache":
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
    else:
        # TODO: Default command
        ...


def clear_cache():
    """Deletes the .cache folder."""
    shutil.rmtree(config.CACHE_PATH)


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
    await rvc.uvr(args.model, args.input, args.output_vocals, args.output_rest)


async def revoice(args=None):
    """Run RVC over given folder."""
    args = args or parser_revoice.parse_args(sys.argv[1:])
    rest_args = dict(args.__dict__)
    del rest_args["subcommand"]
    await rvc.batch_rvc(**rest_args)


async def merge_vocals(args=None):
    """Merge vocals with effects."""
    args = args or parser_merge_vocals.parse_args(sys.argv[1:])
    await ffmpeg.merge_vocals(args.vocals_path, args.others_path, args.output_path)

if __name__ == "__main__":
    asyncio.run(main())
