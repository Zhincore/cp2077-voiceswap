import argparse
import config

main = argparse.ArgumentParser(
    prog="voiceswap",
    description="Tool for automating the creation of AI voice-over mods for Cyberpunk 2077."
)
subcommands = main.add_subparsers(title="subcommands", dest="subcommand")

# Help
help = subcommands.add_parser("help", help="Shows help.")

# Clear cache
clear = subcommands.add_parser(
    "clear_cache",
    help="Deletes the .cache folder."
)

# Extract files
extract_files = subcommands.add_parser(
    "extract_files",
    help="Extracts files matching the given regex pattern from the game."
)
extract_files.add_argument(
    "pattern",
    type=str,
    help="The file name regex pattern to match against.",
    default="v_(?!posessed).*_f_.*",
    nargs=argparse.OPTIONAL,
)
extract_files.add_argument(
    "output",
    type=str,
    help="Path where to extract the files.",
    default=config.WOLVENKIT_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# export_wem
export_wem = subcommands.add_parser(
    "export_wem",
    help="Converts all found .wem files to a usable format"
)
export_wem.add_argument(
    "input",
    type=str,
    help="Path to folder of files to convert.",
    default=config.WOLVENKIT_OUTPUT,
    nargs=argparse.OPTIONAL,
)
export_wem.add_argument(
    "output",
    type=str,
    help="Path where to output the converted files.",
    default=config.WW2OGG_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Isolate vocals
isolate_vocals = subcommands.add_parser(
    "isolate_vocals", help="Splits audio files to vocals and the rest.")
isolate_vocals.add_argument(
    "input",
    type=str,
    help="Path to folder of files to split.",
    default=config.WW2OGG_OUTPUT,
    nargs=argparse.OPTIONAL,
)
isolate_vocals.add_argument(
    "output_vocals",
    type=str,
    help="Path where to output the vocals.",
    default=config.UVR_OUTPUT_VOCALS,
    nargs=argparse.OPTIONAL,
)
isolate_vocals.add_argument(
    "output_rest",
    type=str,
    help="Path where to output the rest.",
    default=config.UVR_OUTPUT_REST,
    nargs=argparse.OPTIONAL,
)
isolate_vocals.add_argument(
    "-m", "--model",
    type=str,
    help="Path to the model to use.",
    default=config.UVR_MODEL,
)

# Revoice
revoice = subcommands.add_parser(
    "revoice", help="Run RVC over given folder.")
# Copied over from https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/tools/infer_batch_rvc.py
revoice.add_argument(
    "--f0up_key",
    type=int,
    default=0,
)
revoice.add_argument(
    "--input_path",
    type=str,
    help="input path, relative to VoiceSwap",
    default=config.UVR_OUTPUT_VOCALS,
)
revoice.add_argument(
    "--index_path",
    type=str,
    help="index path, relative to RVC",
)
revoice.add_argument(
    "--f0method",
    type=str,
    default="rmvpe",
    help="harvest or pm or rmvpe or others",
)
revoice.add_argument(
    "--opt_path",
    type=str,
    help="output path, relative to VoiceSwap",
    default=config.RVC_OUTPUT,
)
revoice.add_argument(
    "--model_name",
    type=str,
    help="Model's filename in assets/weights folder",
    required=True
)
revoice.add_argument(
    "--index_rate",
    type=float,
    default=0.5,
    help="index rate",
)
revoice.add_argument(
    "--device",
    type=str,
    help="gpu id or 'cpu'",
)
revoice.add_argument(
    "--is_half",
    type=bool,
    action=argparse.BooleanOptionalAction,
    help="use half -> True",
)
revoice.add_argument(
    "--filter_radius",
    type=int,
    help="filter radius",
)
revoice.add_argument(
    "--resample_sr",
    type=int,
    help="resample sr, causes issues in current RVC's versions",
)
revoice.add_argument(
    "--rms_mix_rate",
    type=float,
    default=0.05,
    help="rms mix rate, I think this is the volume envelope stuff? The higher the more constant volume, the lower the more original volume.",
)
revoice.add_argument(
    "--protect",
    type=float,
    default=0.4,
    help="protect soundless vowels or something, 0.5 = disabled",
)

# Merge vocals
merge_vocals = subcommands.add_parser(
    "merge_vocals", help="Merge vocals with effects.")
merge_vocals.add_argument(
    "vocals_path",
    type=str,
    help="Path to folder of vocals.",
    default=config.RVC_OUTPUT,
    nargs=argparse.OPTIONAL,
)
merge_vocals.add_argument(
    "others_path",
    type=str,
    help="Path to folder of effects.",
    default=config.UVR_OUTPUT_REST,
    nargs=argparse.OPTIONAL,
)
merge_vocals.add_argument(
    "output_path",
    type=str,
    help="Path where to output the merged files.",
    default=config.MERGED_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# wwise_import
wwise_import = subcommands.add_parser(
    "wwise_import",
    help="Import all found audio files to Wwise and runs conversion to .wem."
)
wwise_import.add_argument(
    "input",
    type=str,
    help="Path to folder of files to import.",
    default=config.MERGED_OUTPUT,
    nargs=argparse.OPTIONAL,
)
wwise_import.add_argument(
    "project",
    type=str,
    help="The Wwise project to use.",
    default=config.WWISE_PROJECT,
    nargs=argparse.OPTIONAL,
)
wwise_import.add_argument(
    "output",
    type=str,
    help="Where to move the converted files.",
    default=config.WWISE_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Pack files
pack_files = subcommands.add_parser(
    "pack_files",
    help="Packs files into a .archive."
)
pack_files.add_argument(
    "archive",
    type=str,
    help="The name to give the archive.",
    default=config.ARCHIVE_NAME,
    nargs=argparse.OPTIONAL,
)
pack_files.add_argument(
    "folder",
    type=str,
    help="The folder to pack.",
    default=config.WWISE_OUTPUT,
    nargs=argparse.OPTIONAL,
)
pack_files.add_argument(
    "output",
    type=str,
    help="Where to put the pack.",
    default=config.PACKED_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Zip folder
zip = subcommands.add_parser(
    "zip",
    help="Zips a folder for distribution."
)
zip.add_argument(
    "archive",
    type=str,
    help="The name to give the archive.",
    default=config.ARCHIVE_NAME,
    nargs=argparse.OPTIONAL,
)
zip.add_argument(
    "folder",
    type=str,
    help="The folder to zip.",
    default=config.PACKED_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Workflow
workflow = subcommands.add_parser(
    "workflow",
    help="Executes the whole workflow sequentially.",
    parents=[revoice]
)
workflow.add_argument(
    "name",
    type=str,
    help="The name of the mod.",
    default=config.ARCHIVE_NAME,
    nargs=argparse.OPTIONAL,
)
workflow.add_argument(
    "pattern",
    type=str,
    help="The file name regex pattern to match against.",
    default="v_(?!posessed).*_f_.*",
    nargs=argparse.OPTIONAL,
)
isolate_vocals.add_argument(
    "--uvr-model",
    type=str,
    help="Path to UVR5 model to use for isolating vocals.",
    default=config.UVR_MODEL,
)
