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
    save_root_vocal = argv[4]  # these two are swapped intentionally
    save_root_ins = argv[3]  # these two are swapped intentionally
    paths = []
    agg = 0
    format0 = "wav"
    total_count = argv[5] if len(argv) > 5 else "?"

    last_info_len = 0
    lines = 0
    for info in uvr(model_name, inp_root, save_root_vocal, paths, save_root_ins, agg, format0):
        lines = info.count("\n")+1

        print(info[last_info_len:])
        print(f"{lines}/{total_count} files done")

        last_info_len = len(info) + 1


if __name__ == "__main__":
    main()
