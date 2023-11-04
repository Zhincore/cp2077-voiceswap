import argparse
import os
import sys
import traceback
import logging

now_dir = os.getcwd()
sys.path.append(now_dir)
import sys

import tqdm as tq
from dotenv import load_dotenv
from scipy.io import wavfile


logger = logging.getLogger(__name__)

from functools import lru_cache
from time import time as ttime

import faiss
import librosa
import numpy as np
import torch
import torch.nn.functional as F
from scipy import signal
from infer.lib.audio import load_audio
from infer.modules.vc.utils import *

from configs.config import Config
from infer.modules.vc.modules import VC
from infer.modules.vc.pipeline import Pipeline


# My modified methods


bh, ah = signal.butter(N=5, Wn=48, btype="high", fs=16000)


def change_rms(data1, sr1, data2, sr2, rate):  # 1是输入音频，2是输出音频,rate是2的占比
    # print(data1.max(),data2.max())
    rms1 = librosa.feature.rms(
        y=data1, frame_length=sr1 // 2 * 2, hop_length=sr1 // 2
    )  # 每半秒一个点
    rms2 = librosa.feature.rms(y=data2, frame_length=sr2 // 2 * 2, hop_length=sr2 // 2)
    rms1 = torch.from_numpy(rms1)
    rms1 = F.interpolate(
        rms1.unsqueeze(0), size=data2.shape[0], mode="linear"
    ).squeeze()
    rms2 = torch.from_numpy(rms2)
    rms2 = F.interpolate(
        rms2.unsqueeze(0), size=data2.shape[0], mode="linear"
    ).squeeze()
    rms2 = torch.max(rms2, torch.zeros_like(rms2) + 1e-6)
    data2 *= (
        torch.pow(rms1, torch.tensor(1 - rate))
        * torch.pow(rms2, torch.tensor(rate - 1))
    ).numpy()
    return data2


def pipeline(
    self,
    model,
    net_g,
    sid,
    audio,
    f0_audio,
    input_audio_path,
    times,
    f0_up_key,
    f0_method,
    file_index,
    index_rate,
    if_f0,
    filter_radius,
    tgt_sr,
    resample_sr,
    rms_mix_rate,
    version,
    protect,
    f0_file=None,
):
    if (
        file_index != ""
        # and file_big_npy != ""
        # and os.path.exists(file_big_npy) == True
        and os.path.exists(file_index)
        and index_rate != 0
    ):
        try:
            index = faiss.read_index(file_index)
            # big_npy = np.load(file_big_npy)
            big_npy = index.reconstruct_n(0, index.ntotal)
        except:
            traceback.print_exc()
            index = big_npy = None
    else:
        index = big_npy = None
    audio = signal.filtfilt(bh, ah, audio)
    audio_pad = np.pad(audio, (self.window // 2, self.window // 2), mode="reflect")
    opt_ts = []
    if audio_pad.shape[0] > self.t_max:
        audio_sum = np.zeros_like(audio)
        for i in range(self.window):
            audio_sum += np.abs(audio_pad[i : i - self.window])
        for t in range(self.t_center, audio.shape[0], self.t_center):
            opt_ts.append(
                t
                - self.t_query
                + np.where(
                    audio_sum[t - self.t_query : t + self.t_query]
                    == audio_sum[t - self.t_query : t + self.t_query].min()
                )[0][0]
            )
    s = 0
    audio_opt = []
    t = None
    t1 = ttime()

    f0_audio_diff = f0_audio.shape[0] - audio.shape[0]
    ad_pad_add = f0_audio_diff if f0_audio_diff > 0 else 0
    f0_pad_add = -f0_audio_diff if f0_audio_diff < 0 else 0

    f0_audio_pad = np.pad(
        f0_audio, (self.t_pad, f0_pad_add + self.t_pad), mode="reflect"
    )
    f0_p_len = f0_audio_pad.shape[0] // self.window
    inp_f0 = None
    if hasattr(f0_file, "name"):
        try:
            with open(f0_file.name, "r") as f:
                lines = f.read().strip("\n").split("\n")
            inp_f0 = []
            for line in lines:
                inp_f0.append([float(i) for i in line.split(",")])
            inp_f0 = np.array(inp_f0, dtype="float32")
        except:
            traceback.print_exc()
    sid = torch.tensor(sid, device=self.device).unsqueeze(0).long()
    pitch, pitchf = None, None
    if if_f0 == 1:
        pitch, pitchf = self.get_f0(
            input_audio_path,  # This should be f0_input_path for harvest method!!
            f0_audio_pad,
            f0_p_len,
            f0_up_key,
            f0_method,
            filter_radius,
            inp_f0,
        )
        pitch = pitch[:f0_p_len]
        pitchf = pitchf[:f0_p_len]
        if "mps" not in str(self.device) or "xpu" not in str(self.device):
            pitchf = pitchf.astype(np.float32)
        pitch = torch.tensor(pitch, device=self.device).unsqueeze(0).long()
        pitchf = torch.tensor(pitchf, device=self.device).unsqueeze(0).float()
    audio_pad = np.pad(audio, (self.t_pad, ad_pad_add + self.t_pad), mode="reflect")
    t2 = ttime()
    times[1] += t2 - t1
    for t in opt_ts:
        t = t // self.window * self.window
        if if_f0 == 1:
            audio_opt.append(
                self.vc(
                    model,
                    net_g,
                    sid,
                    audio_pad[s : t + self.t_pad2 + self.window],
                    pitch[:, s // self.window : (t + self.t_pad2) // self.window],
                    pitchf[:, s // self.window : (t + self.t_pad2) // self.window],
                    times,
                    index,
                    big_npy,
                    index_rate,
                    version,
                    protect,
                )[self.t_pad_tgt : -self.t_pad_tgt]
            )
        else:
            audio_opt.append(
                self.vc(
                    model,
                    net_g,
                    sid,
                    audio_pad[s : t + self.t_pad2 + self.window],
                    None,
                    None,
                    times,
                    index,
                    big_npy,
                    index_rate,
                    version,
                    protect,
                )[self.t_pad_tgt : -self.t_pad_tgt]
            )
        s = t
    if if_f0 == 1:
        audio_opt.append(
            self.vc(
                model,
                net_g,
                sid,
                audio_pad[t:],
                pitch[:, t // self.window :] if t is not None else pitch,
                pitchf[:, t // self.window :] if t is not None else pitchf,
                times,
                index,
                big_npy,
                index_rate,
                version,
                protect,
            )[self.t_pad_tgt : -self.t_pad_tgt]
        )
    else:
        audio_opt.append(
            self.vc(
                model,
                net_g,
                sid,
                audio_pad[t:],
                None,
                None,
                times,
                index,
                big_npy,
                index_rate,
                version,
                protect,
            )[self.t_pad_tgt : -self.t_pad_tgt]
        )
    audio_opt = np.concatenate(audio_opt)
    if rms_mix_rate != 1:
        audio_opt = change_rms(audio, 16000, audio_opt, tgt_sr, rms_mix_rate)
    if tgt_sr != resample_sr >= 16000:
        audio_opt = librosa.resample(audio_opt, orig_sr=tgt_sr, target_sr=resample_sr)
    audio_max = np.abs(audio_opt).max() / 0.99
    max_int16 = 32768
    if audio_max > 1:
        max_int16 /= audio_max
    audio_opt = (audio_opt * max_int16).astype(np.int16)
    del pitch, pitchf, sid
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return audio_opt


def vc_single(
    self,
    sid,
    input_audio_path,
    f0_audio_path,
    f0_up_key,
    f0_file,
    f0_method,
    file_index,
    file_index2,
    index_rate,
    filter_radius,
    resample_sr,
    rms_mix_rate,
    protect,
):
    if input_audio_path is None:
        return "You need to upload an audio", None
    f0_up_key = int(f0_up_key)
    try:
        audio = load_audio(input_audio_path, 16000)
        audio_max = np.abs(audio).max() / 0.95
        if audio_max > 1:
            audio /= audio_max
        f0_audio = load_audio(f0_audio_path, 16000)
        f0_audio_max = np.abs(audio).max() / 0.95
        if f0_audio_max > 1:
            f0_audio /= f0_audio_max
        times = [0, 0, 0]

        if self.hubert_model is None:
            self.hubert_model = load_hubert(self.config)

        file_index = (
            (
                file_index.strip(" ")
                .strip('"')
                .strip("\n")
                .strip('"')
                .strip(" ")
                .replace("trained", "added")
            )
            if file_index != ""
            else file_index2
        )  # 防止小白写错，自动帮他替换掉

        audio_opt = pipeline(
            self.pipeline,
            self.hubert_model,
            self.net_g,
            sid,
            audio,
            f0_audio,
            input_audio_path,
            times,
            f0_up_key,
            f0_method,
            file_index,
            index_rate,
            self.if_f0,
            filter_radius,
            self.tgt_sr,
            resample_sr,
            rms_mix_rate,
            self.version,
            protect,
            f0_file,
        )
        if self.tgt_sr != resample_sr >= 16000:
            tgt_sr = resample_sr
        else:
            tgt_sr = self.tgt_sr
        index_info = (
            "Index:\n%s." % file_index
            if os.path.exists(file_index)
            else "Index not used."
        )
        return (
            "Success.\n%s\nTime:\nnpy: %.2fs, f0: %.2fs, infer: %.2fs."
            % (index_info, *times),
            (tgt_sr, audio_opt),
        )
    except:
        info = traceback.format_exc()
        logger.warning(info)
        return info, (None, None)


# The script itself


def arg_parse() -> tuple:
    parser = argparse.ArgumentParser()
    parser.add_argument("--f0up_key", type=int, default=0)
    parser.add_argument("--input_path", type=str, help="input path")
    parser.add_argument("--index_path", type=str, help="index path")
    parser.add_argument(
        "--f0_path", type=str, default=None, help="input path to use for f0"
    )
    parser.add_argument("--f0method", type=str, default="harvest", help="harvest or pm")
    parser.add_argument("--opt_path", type=str, help="opt path")
    parser.add_argument("--model_name", type=str, help="store in assets/weight_root")
    parser.add_argument("--index_rate", type=float, default=0.66, help="index rate")
    parser.add_argument("--device", type=str, help="device")
    parser.add_argument("--is_half", type=bool, help="use half -> True")
    parser.add_argument("--filter_radius", type=int, default=3, help="filter radius")
    parser.add_argument("--resample_sr", type=int, default=0, help="resample sr")
    parser.add_argument("--rms_mix_rate", type=float, default=1, help="rms mix rate")
    parser.add_argument("--protect", type=float, default=0.33, help="protect")

    args = parser.parse_args()
    sys.argv = sys.argv[:1]

    return args


def main():
    load_dotenv(".env")
    args = arg_parse()
    config = Config()
    config.device = args.device if args.device else config.device
    config.is_half = args.is_half if args.is_half else config.is_half
    vc = VC(config)
    vc.get_vc(args.model_name)
    audios = os.listdir(args.input_path)
    for file in tq.tqdm(audios):
        if file.endswith(".wav"):
            file_path = os.path.join(args.input_path, file)
            f0_path = None
            if args.f0_path:
                f0_path = os.path.join(args.f0_path, file.replace("_m_", "_f_"))
                if not os.path.exists(f0_path):
                    tq.tqdm.write(f"F0 file for {file} not found")
                    f0_path = None

            _, wav_opt = vc_single(
                vc,
                0,
                file_path,
                f0_path or file_path,
                args.f0up_key,
                None,
                args.f0method,
                args.index_path,
                None,
                args.index_rate,
                args.filter_radius,
                args.resample_sr,
                args.rms_mix_rate,
                args.protect,
            )
            out_path = os.path.join(args.opt_path, file)
            wavfile.write(out_path, wav_opt[0], wav_opt[1])


if __name__ == "__main__":
    main()
