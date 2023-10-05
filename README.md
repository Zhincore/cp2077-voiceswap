# Cyberpunk 2077 - VoiceSwap

Tool for automating the creation of AI voice-over mods for Cyberpunk 2077.  
Using WolvenKit for modding and RVC for voice conversion.

## Requiremens

- Windows 10 or later _(unfortunately)_
- Python 3.7 or later
- Cyberpunk 2077
- [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md)
  - Either use poetry or create a venv for RVC (or use the same venv as for this project, but that is not recommended)
- [Audiokinetic Wwise](https://www.audiokinetic.com/en/products/wwise)
  - In the launcher download Wwise version **2019.2**, other versions don't seem to work with Cyberpunk
- FFmpeg (usually included in RVC WebUI)
- Basic knowledge of PowerShell

## Goals

0. Download and install dependencies
1. Unpack wanted voice lines from the game (WolvenKit)
2. Convert them from .wem to .ogg (ww2ogg)
   1. Convert .ogg to .wav (FFmpeg)
3. Separate voice and effects (RVC) **TODO**
4. Convert to wanted voice (RVC) **TODO**
5. Merge the new voice and effects (FFmpeg) **TODO**
6. Convert the voice lines back to .wem (WWise) **TODO**
7. Pack the new lines as a mod (WolvenKit) **TODO**

## Installation

Before starting, make sure you have all the [requirements](#requiremens)!
Especially RVC, which has specific install instructions.

0. Clone this repository (e.g. `git clone https://github.com/zhincore/cp2077-voiceswap` or download it as a zip and unpack).
1. Go to the projects's folder (e.g. `cd cp2077-voiceswap`).
2. Run `install.ps1` to install the project and dependencies.
3. Create a file named `.env`, use `.env.example` as a template and configure it for your setup.

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

- **Phase 1:** `extract_files <regex>` - Extracts files matching specified regex pattern from the game using WolvenKit to the `.cache/archive` folder.
  - Example: `extract_files "\\v_(?!posessed).*_f_.*\.wem$"` extracts all female V's voicelines without Johnny-possessed ones.
  - This usually takes few a minutes, depending on the number of files and drive speed.
- **Phase 2:** `wem2wav` - Converts all .wem files in `.cache/archive` to .wav files in `.cache/raw`.
  - This usually takes a few minutes, too.

## Development

- Run `pip install .[dev]` to install development dependencies

## Credits

### These dependencies are installed by the install script

- [WolvenKit](https://github.com/WolvenKit/WolvenKit) - modding the game
- [ww2ogg](https://github.com/hcs64/ww2ogg) - converting .wem files to a standard format
