"""
Very basic CLI wrapper for the UVR5 module.
"""

import os
import sys

now_dir = os.getcwd()
sys.path.append(now_dir)
import sys

argv = sys.argv
sys.argv = [argv[0]]

import torch
from functools import partialmethod
from tqdm import tqdm
from dotenv import load_dotenv
from queue import Queue
import warnings
warnings.filterwarnings("ignore")

torch.manual_seed(114514)

# Disable tqdm, TQDM_DISABLE didn't work for some reason
tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)

from configs.config import Config
from infer.modules.uvr5.mdxnet import MDXNetDereverb
from infer.modules.uvr5.vr import AudioPre
from torch.multiprocessing import Pool
from librosa.util.exceptions import ParameterError
from functools import partial


g_pre_fun = None


def init_worker(model: str):
    global g_pre_fun
    config = Config()

    if model == "onnx_dereverb_By_FoxJoy":
        g_pre_fun = MDXNetDereverb(15, config.device)
    else:  # HP5_only_main_vocal
        g_pre_fun = AudioPre(
            agg=15,
            model_path=os.path.join(os.getenv("weight_uvr5_root"), model + ".pth"),
            device=config.device,
            is_half=config.is_half,
        )


def run_worker(input_file: str, output_path: str, attempt=0):
    try:
        g_pre_fun._path_audio_(
            input_file,
            output_path,
            output_path,
            "wav",
        )
    except ParameterError as e:
        if str(e) == "Audio buffer is not finite everywhere" and attempt < 3:
            run_worker(input_file, output_path, attempt + 1)
            return
        raise e


def main():
    load_dotenv(".env")
    model = argv[1]
    input_path = argv[2]
    output_path = argv[3]
    batch_size = int(argv[4]) if len(argv) > 4 else 1

    def callback(file: str, _res):
        print(file)

    with Pool(batch_size, init_worker, (model,)) as pool:
        results = Queue()
        while True:
            try:
                if not results.empty():
                    result = results.get_nowait()
                    if result.ready():
                        result.get()
                    else:
                        results.put_nowait(result)

                file = input()
                if file == "":
                    continue

                res = pool.apply_async(
                    run_worker,
                    (os.path.join(input_path, file), output_path),
                    callback=partial(callback, file),
                )
                results.put_nowait(res)
            except EOFError:
                break
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
