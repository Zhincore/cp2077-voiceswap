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

from functools import partialmethod
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# Disable tqdm, TQDM_DISABLE didn't work for some reason
tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)

from configs.config import Config
from infer.modules.uvr5.mdxnet import MDXNetDereverb


def main():
    input_path = argv[1]
    save_root_vocal = argv[3]  # these two are swapped intentionally
    save_root_ins = argv[2]  # these two are swapped intentionally

    config = Config()

    pre_fun = MDXNetDereverb(15, config.device)

    while True:
        try:
            file = input()
            path = os.path.dirname(file)
            pre_fun._path_audio_(
                os.path.join(input_path, file),
                os.path.join(save_root_ins, path),
                os.path.join(save_root_vocal, path),
                "wav",
            )
            print(file)
        except EOFError:
            break


if __name__ == "__main__":
    main()
