import argparse
import os
import sys

now_dir = os.getcwd()
sys.path.append(now_dir)
import sys

import tqdm as tq
from dotenv import load_dotenv
import numpy as np

from infer.lib.audio import load_audio

argv = sys.argv
sys.argv = [argv[0]]

from configs.config import Config
from infer.modules.vc.pipeline import Pipeline


def main():
    load_dotenv(".env")
    config = Config()

    pipeline = Pipeline(1, config)

    input_audio_path = "D:\\Projects\\VoiceSwap\\.cache\\split\\vocals\\ep1\\localization\\en-us\\vo_helmet\\v_q303_m_2b7fec87214e600c.ogg.reformatted.wav_main_vocal.wav"

    audio = load_audio(input_audio_path, 16000)
    audio_max = np.abs(audio).max() / 0.95
    if audio_max > 1:
        audio /= audio_max

    audio_pad = np.pad(audio, (pipeline.t_pad, pipeline.t_pad), mode="reflect")
    p_len = audio_pad.shape[0] // pipeline.window

    pitch, pitchf = pipeline.get_f0(
        input_audio_path,
        audio_pad,
        p_len,
        f0_up_key=0,
        f0_method="rmvpe",
        filter_radius=3,
        inp_f0=None,
    )
    pitch = pitch[:p_len]
    pitchf = pitchf[:p_len]

    print(pitch, pitchf)


if __name__ == "__main__":
    main()
