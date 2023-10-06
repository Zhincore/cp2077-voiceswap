# Cyberpunk 2077 - VoiceSwap

Tool for automating the creation of AI voice-over mods for Cyberpunk 2077.  
Using WolvenKit for modding and RVC for voice conversion.

## Requirements

- Windows 10 or later _(unfortunately)_
- Python 3.7 or later
- Cyberpunk 2077
- [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md)
- [Audiokinetic Wwise](https://www.audiokinetic.com/en/products/wwise) **2019.2.15**
- FFmpeg (usually included in RVC WebUI)
- Basic knowledge of PowerShell

**Highly recommended:** a good GPU with up-to-date drivers and installed [CUDA **11**](https://developer.nvidia.com/cuda-11-8-0-download-archive) for NVIDIA GPUs.

## Goals

0. Download and install dependencies
1. Unpack wanted voice lines from the game (WolvenKit)
2. Convert them from .wem to a usable format (ww2ogg)
3. Separate voice and effects (RVC)
4. Convert to wanted voice (RVC) **WIP**
5. Merge the new voice and effects (FFmpeg) **TODO**
6. Convert the voice lines back to .wem (WWise) **TODO**
7. Pack the new lines as a mod (WolvenKit) **TODO**

## Installation

1. Install [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md) to a folder of your choice.
   - The linked README isn't very clear and I am not sure how I got it working either so... good luck.
   - Either use poetry or create a venv to use with pip.
   - In addition to RVC's installation also run `poetry add onnxruntime` or `pip install onnxruntime` (depending on which one you used previously).
     - **TIP:** If you use CUDA, replace `onnxruntime` with `onnxruntime-gpu` for big performance improvement.
2. Install [Audiokinetic Wwise](https://www.audiokinetic.com/en/products/wwise):
   1. Install their launcher.
   2. Using the launcher, install Wwise version **2019.2.15**, other versions don't seem to work with Cyberpunk.
3. Install this project:
   1. Clone this repository (e.g. `git clone https://github.com/zhincore/cp2077-voiceswap` or download it as a zip and unpack).
   2. Go to the projects's folder (e.g. `cd cp2077-voiceswap`).
   3. Run `install.ps1` to install the project and dependencies.
   4. Create a file named `.env`, use `.env.example` as a template and configure it for your setup.

## Usage

This project has to be used from the command line.

Before running any of the commands, you must activate the venv using `.\.venv\Scripts\activate`!  
If you've done everything correctly, the following commands should be available in the command line.
Also make sure your `.env` file contains the correct paths.

To start the whole automated process, use the command `voiceswap (...arguments...)`.
This runs all phases specified later in sequential order without needing any further user input.  
Use the following arguments to configure that process:

- **TODO**

### Subcommands / Phases

If you want to run only a specific phase of the process, you can use the following subcommands.
These can be used either as `voiceswap <subcommand> (...arguments...)` or directly as `<subcommand> (...arguments...)` without the voiceswap prefix.

**Legend:** Parameters in `<angle brackets>` are required, ones in `[square brackets]` are optional.  
This README only shows important parameters, other parameters have defaults that guarentee seamless flow between phases.  
Use `<subcommand> -h` to display better detailed help.

- **Phase 1:** `extract_files [regex]` - Extracts files matching specified regex pattern from the game using WolvenKit to the `.cache/archive` folder.
  - Example: `extract_files "\\v_(?!posessed).*_f_.*\.wem$"` extracts all female V's voicelines without Johnny-possessed ones.
  - This usually takes few a minutes, depending on the number of files and drive speed.
- **Phase 2:** `export_wem` - Converts all .wem files in `.cache/archive` to a usable format in `.cache/raw`.
  - This usually takes a few minutes, too.
- **Phase 3:** `isolate_vocals` - Splits audio files in `.cache/raw` to vocals and effects in `.cache/split`.
  - This may take a few hours on V's voicelines, this is probably the longest phase.
  - It is done to preserve reverb and other effects, otherise the AI will make the effects by "mouth" and that's awful.
- **Phase 4:** `revoice --model_name <model> [--index_path <index_path>]` - Processes audio files in `.cache/split/vocals` with given voice model and ouputs to `.cache/voiced`.
  - Example: `revoice --model_name arianagrandev2 --index_path logs/arianagrandev2.index`
  - This may take approximately an hour on V's voicelines.

## Development

- Run `pip install .[dev]` to install development dependencies

## Credits

### These dependencies are installed by the install script

- [WolvenKit](https://github.com/WolvenKit/WolvenKit) - modding the game
- [ww2ogg](https://github.com/hcs64/ww2ogg) - converting .wem files to a standard format
