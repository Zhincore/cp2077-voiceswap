# Cyberpunk 2077 - VoiceSwap

Tool for automating the creation of AI voice-over mods for Cyberpunk 2077.  
Using WolvenKit for modding and RVC for voice conversion.

## Requirements

- Windows 10 or later _(unfortunately)_
- Python 3.9 or later
- Cyberpunk 2077
- [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md)
- [Audiokinetic Wwise](https://www.audiokinetic.com/en/products/wwise) **2019.2.15**
- FFmpeg (usually included in RVC WebUI)
- Basic knowledge of PowerShell
- At least 35 GB of free disk space, 45 GB if you're going for V's voicelines
  - This is including >12GB RVC

### Highly recommended:

- [git](https://git-scm.com/downloads)
- [Poetry](https://python-poetry.org/docs/) - for easier installing and running of RVC
- GPU with up-to-date drivers - on CPU the process will take much longer
  - For NVIDIA make sure to instal [CUDA **11.8**](https://developer.nvidia.com/cuda-11-8-0-download-archive) or 11.7

## Goals

0. Download and install dependencies
1. Unpack wanted voice lines from the game (WolvenKit)
2. Convert them from .wem to a usable format (ww2ogg)
3. Separate voice and effects (RVC)
4. Convert to wanted voice (RVC)
5. Merge the new voice and effects (FFmpeg)
6. Convert the voice lines back to .wem (WWise)
7. Pack the new lines as an .archive (WolvenKit)
8. Zip the mod for distribution **TODO**

## TODO

- Preserve folders over wwise conversion (fix the current renaming behavior)

- [ ] Projects? e.g. separated cache folders and saved settings for phases
- [ ] Allow main command to run from a specific phase.

## Installation

### 1. Install RVC

[RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md) is a tool for converting voices using AI.

The linked README isn't very clear so I'll try to write the basic steps.
Choose whether you want to use [Poetry](https://python-poetry.org/docs/) or just pip, I'll try to describe both options.

1. Clone the [linked repository](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) or download it as zip and unpack.
2. **If you use pip,** create a virtual environment using `py -m venv venv` and activate it using `.\.venv\Scripts\activate`.
3. Install base dependencies:
   - **Poetry:** `poetry install`.
   - **Pip:** Choose the right command for your machine in the [`You can also use pip to install them:` section](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md).
4. Install the correct Torch for your system, _if you plan to use CPU only you can skip this step_:
   - Visit [PyTorch's documentation](https://pytorch.org/get-started/locally/), choose Stable, your OS, pip, Python and lastly choose either CUDA 11.8 or ROCm.
   - **With Poetry** run the generated command like `poetry run <command>`.
   - **With Pip** run the command directly.
5. Install onnxruntime:
   - **Poetry:** `poetry install onnxruntime`
   - **With Pip:** `pip install onnxruntime`
   - **If you use GPU** replace `onnxruntime` with `onnxruntime-gpu` in the above command for better performance!
6. Download the required models:
   - **Poetry:** `poetry run python tools/download_models.py`
   - **Pip:** `python tools/download_models.py`
7. Try to start the WebUI:
   - **Poetry:** `poetry run python infer-web.py`
   - **Pip:** `python infer-web.py`

**Note:** Intel ARC and AMD ROCm have some extra instructions in the [RVC's README](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md).

If everything went correctly, the RVC should boot up and show you a page in your browser. You can now close the page and press `Ctrl+C` in the console to quit the script.

You will need the location where you installed RVC later.

#### Installing Voice Models

There are many voice models available online, they usually ship as a zip of two or three files:

- `.pth` file - place it in RVC's `assets/weights/` folder.
- `.index` file - place it in RVC's `logs/` folder.
- I haven't figured out the third one, but it seems uncommon and not needed.
- Make sure both files have sensible names, they usually don't; rename them if needed.

### 2. Install Wwise

[Audiokinetic Wwise](https://www.audiokinetic.com/en/products/wwise) is a free enterprise-level suite for processing audio for games.

1. Install their launcher.
2. Using the launcher, install Wwise version **2019.2.15**, other versions don't seem to work with Cyberpunk.

The program looks kind of scary, it's a professional tool.
But don't worry, this script will do everything for you.

### 3. Install this project:

1.  Clone this repository (e.g. `git clone https://github.com/zhincore/cp2077-voiceswap` or download it as a zip and unpack).
2.  Go to the projects's folder (e.g. `cd cp2077-voiceswap`).
3.  Run `install.ps1` to install the project and dependencies.
4.  Copy or rename file `.env.example` to `.env` and configure it for your setup.
    The example file contains comments which will hopefully help you.

## Usage

Before starting, open PowerShell (or other command-line) in the project's folder and run `.\.venv\Scripts\activate` to activate venv if you haven't already.

To run all phases described later in a sequential order without needing any further user input  
use the command `voiceswap workflow [name] --model_name <model> [--index_path <index_path>] [--f0up_key <pitch_shift>] [pattern]`.
The parameters have following meanings:

- `name` - The name of the mod basically, will be used as archive name. Don't use spaces or special symbols. Example: `ArianaGrandeVO`, default is `voiceswap`
- `--model_name` - The voice model to use, it has to be the name of a file in RVC's `assets/weights/`. Example: `arianagrandev2.pth`
- `--index_path` - Optional path to a voice index. Example: `logs/arianagrandev2.index`
- `--f0up_key` - Optionally pitch shift the audio before converting, this is very useful when the original voice is deeper or higher than the new voice. 12 is one octave up, -12 is one octave down. You can experiment with this in the origin RVC WebUI
- `pattern` - Regex pattern of voice lines to replace. Default is `v_(?!posessed).*_f_.*` which is all female V's lines but not Johnny-possessed ones.
  - **Technical note:** The regex is prepended with `\\` and appended with `\.wem$` and is matched agains the full path in game's archive.

Use command `voiceswap help` for more paramaters and information.

**Legend:** Parameters in `<angle brackets>` are required, ones in `[square brackets]` are optional.  
This README only shows important parameters, other parameters have defaults that guarentee seamless flow between phases.

### Subcommands / Phases

If you want to run only a specific phase of the process, you can use the following subcommands.
You can use these as `voiceswap <subcommand>`.

Use `voiceswap <subcommand> -h` to display better detailed help.

- `clear_cache` - Utility command to delete the whole .cache folder, **this removes your whole progress!**
- **Phase 1:** `extract_files [regex]` - Extracts files matching specified regex pattern from the game using WolvenKit to the `.cache/archive` folder.
  - Example: `extract_files "v_(?!posessed).*_f_.*"` extracts all female V's voicelines without Johnny-possessed ones (default).
  - This usually takes few a minutes, depending on the number of files and drive speed.
- **Phase 2:** `export_wem` - Converts all .wem files in `.cache/archive` to a usable format in `.cache/raw`.
  - This usually takes a few minutes, too.
- **Phase 3:** `isolate_vocals` - Splits audio files in `.cache/raw` to vocals and effects in `.cache/split`.
  - This may take a few hours on V's voicelines, this is probably the longest phase.
  - It is done to preserve reverb and other effects, otherise the AI will make the effects by "mouth" and that's awful.
- **Phase 4:** `revoice --model_name <model> [--index_path <index_path>] [--f0up_key <pitch_shift>]` - Processes audio files in `.cache/split/vocals` with given voice model and ouputs to `.cache/voiced`.
  - Example: `revoice --model_name arianagrandev2.pth --index_path logs/arianagrandev2.index --f0up_key 4`
  - This may take a few hours on V's voicelines.
- **Phase 5:** `merge_vocals` - Merge the new vocals with effects.
  - This should take just a few minutes.
- **Phase 6:** `wwise_import` - Import all found audio files to Wwise and runs conversion to .wem.
  - **Warning:** This phase opens an automated Wwise window.  
    If everything goes well, you shouldn't have to touch the window at all, you can minimize it, but don't close it, it will be closed automatically.
  - This can take an hour or two on V's voicelines.
- **Phase 7:** `pack_files [archive_name]` - Packs the files into a `.archive`.
  - Should be pretty quick.
- **Phase 8:** `zip [archive_name]` - Zips the resulting files for distribution.
  - This final step should be nearly instant, too.

## Development

- Run `pip install .[dev]` to install development dependencies

## Credits

### These dependencies are installed by the install script

- [WolvenKit](https://github.com/WolvenKit/WolvenKit) - modding the game
- [ww2ogg](https://github.com/hcs64/ww2ogg) - converting .wem files to a standard format
