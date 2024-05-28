WOLVENKIT_EXE = "./libs/WolvenKit/WolvenKit.CLI"

METADATA_PATH = ".metadata"
SFX_CACHE_PATH = ".sfx_cache"
CACHE_PATH = ".cache"
TMP_PATH = ".tmp"

METADATA_EXTRACT_PATH = METADATA_PATH + "/raw"
SFX_EXPORT_PATH = SFX_CACHE_PATH + "/exported"
SFX_MAP_PATH = METADATA_PATH + "/sfx_map.json"

WOLVENKIT_OUTPUT = CACHE_PATH + "/archive"

WW2OGG_OUTPUT = CACHE_PATH + "/raw"

UVR_FORMAT_CACHE = "formatted"
UVR_MODEL_CACHE = CACHE_PATH + "/uvr_models"
UVR_FIRST_MODEL = "6_HP-Karaoke-UVR.pth"
UVR_FIRST_SUFFIX = "_vocals.wav"
UVR_FIRST_SUFFIX_O = "_instrumental.wav"
UVR_FIRST_CACHE = "karaoke"
UVR_SECOND_MODEL = "Reverb_HQ_By_FoxJoy.onnx"
UVR_SECOND_SUFFIX = UVR_FIRST_SUFFIX + "_instrumental.wav"
UVR_SECOND_SUFFIX_O = UVR_FIRST_SUFFIX + "_reverb.wav"
UVR_SECOND_CACHE = "isolated"

TTS_OUTPUT = CACHE_PATH + "/tts"

RVC_OUTPUT = CACHE_PATH + "/voiced"
SFX_RVC_OUTPUT = CACHE_PATH + "/voiced_sfx"

MERGED_OUTPUT = CACHE_PATH + "/merged"
MERGED_SILENT_FILENAME = "_silent_files.json"

WWISE_PROJECT = CACHE_PATH + "/wwise_project"
WWISE_OUTPUT = CACHE_PATH + "/complete"
SFX_PAKS_OUTPUT = CACHE_PATH + "/complete_sfx"

ARCHIVE_NAME = "voiceswap"

PACKED_OUTPUT = CACHE_PATH + "/packed"
