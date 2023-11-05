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
from torch.multiprocessing import Pool, set_start_method
from scipy import signal
from infer.lib.audio import load_audio
from infer.modules.vc.utils import *

from configs.config import Config
from infer.modules.vc.modules import VC
from infer.modules.vc.pipeline import Pipeline


g_vc = None
g_args = None

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


def get_f0(
    self,
    input_audio_path,
    x,
    p_len,
    f0_up_key,
    f0_contrast,
    f0_method,
    filter_radius,
    inp_f0=None,
):
    time_step = self.window / self.sr * 1000
    f0_min = 50
    f0_max = 1100
    f0_mel_min = 1127 * np.log(1 + f0_min / 700)
    f0_mel_max = 1127 * np.log(1 + f0_max / 700)
    if not hasattr(self, "model_rmvpe"):
        from infer.lib.rmvpe import RMVPE

        logger.info("Loading rmvpe model,%s" % "%s/rmvpe.pt" % os.environ["rmvpe_root"])
        self.model_rmvpe = RMVPE(
            "%s/rmvpe.pt" % os.environ["rmvpe_root"],
            is_half=self.is_half,
            device=self.device,
        )
    f0 = self.model_rmvpe.infer_from_audio(x, thred=0.03)

    # pitch change
    f0 *= pow(2, f0_up_key / 12)

    # contrast change
    avg = np.average(f0)
    f0 -= avg
    f0 *= f0_contrast
    f0 += avg

    # with open("test.txt","w")as f:f.write("\n".join([str(i)for i in f0.tolist()]))
    tf0 = self.sr // self.window  # 每秒f0点数
    if inp_f0 is not None:
        delta_t = np.round((inp_f0[:, 0].max() - inp_f0[:, 0].min()) * tf0 + 1).astype(
            "int16"
        )
        replace_f0 = np.interp(list(range(delta_t)), inp_f0[:, 0] * 100, inp_f0[:, 1])
        shape = f0[self.x_pad * tf0 : self.x_pad * tf0 + len(replace_f0)].shape[0]
        f0[self.x_pad * tf0 : self.x_pad * tf0 + len(replace_f0)] = replace_f0[:shape]
    # with open("test_opt.txt","w")as f:f.write("\n".join([str(i)for i in f0.tolist()]))
    f0bak = f0.copy()
    f0_mel = 1127 * np.log(1 + f0 / 700)
    f0_mel[f0_mel > 0] = (f0_mel[f0_mel > 0] - f0_mel_min) * 254 / (
        f0_mel_max - f0_mel_min
    ) + 1
    f0_mel[f0_mel <= 1] = 1
    f0_mel[f0_mel > 255] = 255
    f0_coarse = np.rint(f0_mel).astype(np.int32)
    return f0_coarse, f0bak  # 1-0


def pipeline(
    self,
    model,
    net_g,
    sid,
    audio,
    input_audio_path,
    times,
    f0_up_key,
    f0_contrast,
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

    audio_pad = np.pad(audio, (self.t_pad, self.t_pad), mode="reflect")
    p_len = audio_pad.shape[0] // self.window
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
        pitch, pitchf = get_f0(
            self,
            input_audio_path,
            audio_pad,
            p_len,
            f0_up_key,
            f0_contrast,
            f0_method,
            filter_radius,
            inp_f0,
        )
        pitch = pitch[:p_len]
        pitchf = pitchf[:p_len]
        if "mps" not in str(self.device) or "xpu" not in str(self.device):
            pitchf = pitchf.astype(np.float32)
        pitch = torch.tensor(pitch, device=self.device).unsqueeze(0).long()
        pitchf = torch.tensor(pitchf, device=self.device).unsqueeze(0).float()
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
    f0_up_key,
    f0_contrast,
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
            input_audio_path,
            times,
            f0_up_key,
            f0_contrast,
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
    # My custom args
    parser.add_argument(
        "--f0_contrast", type=float, default=1, help="multiply pitch contrast"
    )
    parser.add_argument(
        "--batchsize", type=int, default=1, help="how many RVC processes to spawn"
    )

    args = parser.parse_args()
    sys.argv = sys.argv[:1]

    return args


def init_worker(p_args):
    global g_vc, g_args
    g_args = p_args

    config = Config()
    config.device = p_args.device if p_args.device else config.device
    config.is_half = p_args.is_half if p_args.is_half else config.is_half

    g_vc = VC(config)
    g_vc.get_vc(p_args.model_name)


def run_worker(file_path, *params):
    args = g_args
    vc = g_vc

    _, wav_opt = vc_single(
        vc,
        0,
        os.path.join(args.input_path, file_path),
        args.f0up_key,
        args.f0_contrast,
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
    out_path = os.path.join(args.opt_path, file_path)
    wavfile.write(out_path, wav_opt[0], wav_opt[1])


def main():
    load_dotenv(".env")
    args = arg_parse()

    with Pool(args.batchsize, init_worker, (args,)) as pool:
        # Collect tasks
        audios = []
        for root, _dirs, files in os.walk(args.input_path):
            for file in files:
                if file.endswith(".wav"):
                    file_path = os.path.join(root, file)
                    audios.append(file_path)

        pbar = tq.tqdm("Converting", total=len(audios), unit="file")

        for _ in pool.imap_unordered(run_worker, audios):
            pbar.update(1)


if __name__ == "__main__":
    main()
