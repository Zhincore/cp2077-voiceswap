# Cyberpunk 2077 - VoiceSwap

Tool for automating the creation of AI voice-over mods for Cyberpunk 2077.

> ⚠️ This project is rather experimental, don't expect it to be perfect!  
> It's usage and functionality may change as it's still in development.

🗨️ [Join my Discord server](https://discord.gg/5mVrUh34Nd) for support and chat!

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

This project aims to achieve the following:

0. Download and install dependencies
1. Unpack wanted voice lines from the game (WolvenKit)
2. Convert them from .wem to a usable format (ww2ogg)
3. (SFX) Extract all SFX audio files and metadata from the game (WolvenKit + OpusToolZ + CpBnkReader)
4. (SFX) Select needed SFX files
5. Separate voice and effects (RVC)
6. Convert to wanted voice (RVC) **TODO: SFX too**
7. Merge the new voice and effects (FFmpeg)
8. Convert the voice lines back to .wem (WWise)
9. (SFX) Repack converted SFX back into their opuspaks (OpusToolZ) **TODO**
10. Pack the whole mod as an .archive (WolvenKit)
11. Zip the mod for distribution

SFX steps are optional and experimntal and currently only support V's grunts.

## TODO

- Extract only needed hashes of SFX

- [ ] Projects? e.g. separated cache folders and saved settings for phases
- [ ] Allow main command to run from a specific phase.

## Installation

### 1. Install RVC

Download a ready-made 7zip for your system from the [RVC Releases page](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/releases) (Recommended) or follow the instructions in my [Installing RVC from source guide](/RVC-installation.md).

Unpack the downloaded zip and test that it works by running the `go-web.bat` script, you can then close the console window to end RVC.

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
3.  Run `.\install.ps1` to install the project and dependencies.  
    **NOTE:** If you get the _"scripting is disabled on this system"_ error, run this command instead:  
    `powershell.exe -noprofile -executionpolicy bypass -file .\install.ps1`
4.  Copy or rename file `.env.example` to `.env` and configure it for your setup.
    The example file contains comments which will hopefully help you.

## Usage

Before starting, open PowerShell (or other command-line) in the project's folder and run `.\.venv\Scripts\activate` to activate venv if you haven't already.

To run all phases described later in a sequential order without needing any further user input  
use the command `voiceswap workflow [name] --model_name <model> [--index_path <index_path>] [--f0up_key <pitch_shift>] [pattern]`.
The parameters have following meanings:

**NOTE:** This main command is still work-in-progress, at the moment it is better to execute the phases bellow manually.

- `name` - The name of the mod basically, will be used as archive name. Don't use spaces or special symbols. Example: `ArianaGrandeVO`, default is `voiceswap`
- `--model_name` - The voice model to use, it has to be the name of a file in RVC's `assets/weights/`. Example: `arianagrandev2.pth`
- `--index_path` - Optional path to a voice index. Example: `logs/arianagrandev2.index`
- `--f0up_key` - Optionally pitch shift the audio before converting, this is very useful when the original voice is deeper or higher than the new voice. 12 is one octave up, -12 is one octave down. You can experiment with this in the origin RVC WebUI
- `pattern` - Regex pattern of voice lines to replace. Default is `v_(?!posessed).*_f_.*` which is all female V's lines but not Johnny-possessed ones.
  - **Technical note:** The regex is prepended with `\\` and appended with `\.wem$` and is matched agains the full path in game's archive.

Once this command completes successfully, you can find your mod in the root folder of the project as `<name>.zip` (depending on the name you chose).

Use command `voiceswap help` for more paramaters and information.

**Legend:** Parameters in `<angle brackets>` are required, ones in `[square brackets]` are optional.  
This README only shows important parameters, other parameters have defaults that guarentee seamless flow between phases.

### Subcommands / Phases

If you want to run only a specific phase of the process, you can use the following subcommands.
You can use these as `voiceswap <subcommand>`.

Use `voiceswap <subcommand> -h` to display better detailed help.

- `clear_cache` - Utility command to delete the whole .cache folder, **this removes your whole progress!**
- **Phase 1:** `extract [regex]` - Extracts files matching specified regex pattern from the game using WolvenKit to the `.cache/archive` folder.
  - Example: `extract "v_(?!posessed).*_f_.*"` extracts all female V's voicelines without Johnny-possessed ones (default).
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
- **Phase 6:** `wwise` - Import all found audio files to Wwise and runs conversion to .wem.
  - **Warning:** This phase opens an automated Wwise window.  
    If everything goes well, you shouldn't have to touch the window at all, you can minimize it, but don't close it, it will be closed automatically.
  - **Note:** Wwise might freeze a few times, especially right after opening. In my experience it unfreezes when you let it run.
  - This can take just a few minutes or few hours depending on your drive speed.
- **Phase 7:** `pack [archive_name]` - Packs the files into a `.archive`.
  - Should be pretty quick.
- **Phase 8:** `zip [archive_name]` - Zips the resulting files for distribution.
  - This final step should be fast too.

## Development

- Run `pip install .[dev]` to install development dependencies

## Credits

### These dependencies are installed by the install script

- [WolvenKit](https://github.com/WolvenKit/WolvenKit) - modding the game
- [ww2ogg](https://github.com/hcs64/ww2ogg) - converting .wem files to a standard format
