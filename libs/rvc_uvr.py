"""
Very basic CLI wrapper for the UVR5 module.
"""

import os
import sys
from pathlib import Path

now_dir = os.getcwd()  # nopep8
sys.path.append(now_dir)  # nopep8
import sys  # nopep8

argv = sys.argv
sys.argv = [argv[0]]

from infer.modules.uvr5.modules import uvr  # nopep8


def main():
    model_name = argv[1]
    inp_root = argv[2]
    save_root_vocal = argv[3]
    save_root_ins = save_root_vocal
    paths = []
    agg = 0
    format0 = "wav"

    for info in uvr(model_name, inp_root, save_root_vocal, paths, save_root_ins, agg, format0):
        print(info)


if __name__ == "__main__":
    main()
