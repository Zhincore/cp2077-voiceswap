# Cyberpunk 2077 - Voice Swap

## Requiremens

- Windows 10 or later _(unfortunately)_
- Python 3.7 or later
- Cyberpunk 2077
- [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md)
  - Either use poetry or create a venv for RVC (or use the same venv as for this project, but that is not recommended)
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
If you've done everything correctly, you should have the following commands available:

### Commands

- `extract_files <pattern>` - Extracts files matching specified pattern from the game using WolvenKit to `.cache/archive` folder (e.g. `extract_files "\\v_(?!posessed).*_f_.*\.wem$"` extracts all female V's voicelines without Johnny's)
- `wem2ogg` - Converts all wem files in `.cache/archive` to .ogg files in `.cache/raw`

## Development

- Run `pip install .[dev]` to install development dependencies

## Credits

### These dependencies are installed by the install script

- [WolvenKit](https://github.com/WolvenKit/WolvenKit)
- [ww2ogg](https://github.com/hcs64/ww2ogg)
