import argparse

import config

main = argparse.ArgumentParser(
    prog="voiceswap",
    description="Tool for automating the creation of AI voice-over mods for Cyberpunk 2077.",
)
subcommands = main.add_subparsers(title="subcommands", dest="subcommand")

# Help
help_ = subcommands.add_parser("help", help="Shows help.")


# Extract SFX metadata
sfx_metadata = subcommands.add_parser(
    "sfx_metadata", help="Extracts SFX metadata from the game."
)
sfx_metadata.add_argument(
    "output",
    type=str,
    help="Where to put the metadata.",
    default=config.METADATA_EXTRACT_PATH,
    nargs=argparse.OPTIONAL,
)

# Map SFX events
map_sfx = subcommands.add_parser(
    "map_sfx", help="Create a map of SFX events. Needs sfx_metadata and export_sfx."
)
map_sfx.add_argument(
    "metadata_path",
    type=str,
    help="Path where SFX metadata is stored.",
    default=config.METADATA_EXTRACT_PATH,
    nargs=argparse.OPTIONAL,
)
map_sfx.add_argument(
    "output",
    type=str,
    help="Path to json file that will be created with the map.",
    default=config.SFX_MAP_PATH,
    nargs=argparse.OPTIONAL,
)

# Extract subtitles
extract_subtitles = subcommands.add_parser(
    "extract_subtitles", help="Extract subttiles and their audio file names."
)
extract_subtitles.add_argument(
    "locale",
    type=str,
    help="What locale of subtitles to extract.",
    default="cz-cz",
    nargs=argparse.OPTIONAL,
)
extract_subtitles.add_argument(
    "output",
    type=str,
    help="Path to file where the subtitles will be put.",
    default=config.METADATA_EXTRACT_PATH,
    nargs=argparse.OPTIONAL,
)

# Select SFX files
extract_sfx = subcommands.add_parser(
    "extract_sfx",
    help="Extract V's SFX files of given gender.",
)
extract_sfx.add_argument(
    "gender",
    type=lambda a: {"f": "female", "m": "male"}.get(a, a),
    choices=["male", "female", "f", "m"],
    help="Which gender of grunts to export (male or female).",
)
extract_sfx.add_argument(
    "output",
    type=str,
    help="Where to put the SFX audio files.",
    default=config.SFX_EXPORT_PATH,
    nargs=argparse.OPTIONAL,
)
extract_sfx.add_argument(
    "--map-path",
    type=str,
    help="Path to sfx_map.json file.",
    default=config.SFX_MAP_PATH,
    nargs=argparse.OPTIONAL,
)
extract_sfx.add_argument(
    "--sfx-cache-path",
    type=str,
    help="Path where to store SFX containers.",
    default=config.SFX_CACHE_PATH,
    nargs=argparse.OPTIONAL,
)

# Extract files
extract_files = subcommands.add_parser(
    "extract", help="Extracts files matching the given regex pattern from the game."
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
    "export_wem", help="Converts all found .wem files to a usable format"
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
    "isolate_vocals", help="Splits audio files to vocals and the rest."
)
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
    "--overwrite",
    default=True,
    action=argparse.BooleanOptionalAction,
    help="Whether to overwrite old files",
)

# TTS
tts = subcommands.add_parser("tts", help="Converts subtitles to speech.")
tts.add_argument(
    "gender",
    type=lambda a: {"f": "female", "m": "male"}.get(a, a),
    choices=["male", "female", "f", "m"],
    help="Which gender of V to process (male or female).",
)
tts.add_argument(
    "locale",
    type=str,
    help="What locale of subtitles to use.",
    default="cz-cz",
)
tts.add_argument(
    "language",
    type=str,
    help="What language of TTS to use.",
    default="cs",
)
tts.add_argument(
    "reference",
    type=str,
    help="Path to a reference audio file to use for voice.",
)
tts.add_argument(
    "output",
    type=str,
    help="Path to file where the subtitles will be put.",
    default=config.TTS_OUTPUT,
    nargs=argparse.OPTIONAL,
)
tts.add_argument(
    "pattern",
    type=str,
    help="The file name regex pattern to match against.",
    default="v_(?!posessed).*_f_.*",
    nargs=argparse.OPTIONAL,
)
tts.add_argument(
    "--subtitles-path",
    type=str,
    help="Path where subtitle files were extracted.",
    default=config.METADATA_EXTRACT_PATH,
    nargs=argparse.OPTIONAL,
)

# Revoice
revoice = subcommands.add_parser("revoice", help="Run RVC over given folder.")
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
    "--f0_contrast",
    type=float,
    default=1,
    help="multiply pitch contrast",
)
revoice.add_argument(
    "--batchsize",
    type=int,
    default=1,
    help="how many RVC processes to spawn",
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
    required=True,
)
revoice.add_argument(
    "--index_rate",
    type=float,
    default=0.9,
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
    default=0.5,
    help="rms mix rate, I think this is the volume envelope stuff? The higher the more constant volume, the lower the more original volume.",
)
revoice.add_argument(
    "--protect",
    type=float,
    default=0.25,
    help="protect soundless vowels or something, 0.5 = disabled",
)

# Revoice SFX
revoice_sfx = subcommands.add_parser(
    "revoice_sfx",
    help="Run RVC over SFX or given folder.",
    parents=[revoice],
    conflict_handler="resolve",
)
revoice_sfx.add_argument(
    "gender",
    type=lambda a: {"f": "female", "m": "male"}.get(a, a),
    choices=["male", "female", "f", "m"],
    help="Which gender of grunts to revoice (male or female).",
)
revoice_sfx.add_argument(
    "--input_path",
    type=str,
    help="input path, relative to VoiceSwap",
    default=config.SFX_EXPORT_PATH,
)
revoice_sfx.add_argument(
    "--opt_path",
    type=str,
    help="output path, relative to VoiceSwap",
    default=config.SFX_RVC_OUTPUT,
)

# Merge vocals
merge_vocals = subcommands.add_parser("merge_vocals", help="Merge vocals with effects.")
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
merge_vocals.add_argument(
    "--voice-vol",
    type=float,
    help="Adjust the volume of the voice. 1 is original volume.",
    default=1.5,
)
merge_vocals.add_argument(
    "--effect-vol",
    type=float,
    help="Adjust the volume of the effects. 1 is original volume.",
    default=1,
)

# wwise convert
wwise_import = subcommands.add_parser(
    "wwise", help="Import all found audio files to Wwise and runs conversion to .wem."
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

# Move Wwise files
move_wwise_files = subcommands.add_parser(
    "move_wwise_files",
    help="In case Wwise conversion gets stuck or you do the conversion manually, "
    + "this command finds the converted files and tries to find their correct location.",
)
move_wwise_files.add_argument(
    "project",
    type=str,
    help="The Wwise project to use.",
    default=config.WWISE_PROJECT,
    nargs=argparse.OPTIONAL,
)
move_wwise_files.add_argument(
    "output_path",
    type=str,
    help="Path to the reference folder to find paths against.",
    default=config.WWISE_OUTPUT,
    nargs=argparse.OPTIONAL,
)

# Convert sfx to opus
pack_opuspaks = subcommands.add_parser(
    "pack_opuspaks", help="Patch opuspaks with new opuses."
)
pack_opuspaks.add_argument(
    "input_path",
    type=str,
    help="Path with the new opus files.",
    default=config.SFX_RVC_OUTPUT,
    nargs=argparse.OPTIONAL,
)
pack_opuspaks.add_argument(
    "output_path",
    type=str,
    help="Path where to output the patched paks.",
    default=config.SFX_PAKS_OUTPUT + "/base/sound/soundbanks",
    nargs=argparse.OPTIONAL,
)
pack_opuspaks.add_argument(
    "opusinfo",
    type=str,
    help="Path to .opusinfo file.",
    default=config.SFX_CACHE_PATH + "/base/sound/soundbanks/sfx_container.opusinfo",
    nargs=argparse.OPTIONAL,
)

# Pack files
pack_files = subcommands.add_parser("pack", help="Packs files into a .archive.")
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
zip_files = subcommands.add_parser("zip", help="Zips a folder for distribution.")
zip_files.add_argument(
    "archive",
    type=str,
    help="The name to give the archive.",
    default=config.ARCHIVE_NAME,
    nargs=argparse.OPTIONAL,
)
zip_files.add_argument(
    "folder",
    type=str,
    help="The folder to zip.",
    default=config.PACKED_OUTPUT,
    nargs=argparse.OPTIONAL,
)
