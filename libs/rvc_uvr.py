"""
Very basic CLI wrapper for the UVR5 module.
"""
import os
import sys

now_dir = os.getcwd()  # nopep8
sys.path.append(now_dir)  # nopep8
import sys  # nopep8

from dotenv import load_dotenv  # nopep8
from infer.modules.uvr5.modules import uvr


def main():
    model_name = sys.argv[1]
    inp_root = ""
    save_root_vocal = sys.argv[2]
    save_root_ins = sys.argv[3]
    paths = sys.argv[4:]
    agg = None
    format0 = "wav"

    for info in uvr(model_name, inp_root, save_root_vocal, paths, save_root_ins,  agg, format0):
        print(info)


if __name__ == "__main__":
    main()
