import asyncio
import os
import shutil
from itertools import chain
from tqdm import tqdm
import numpy as np
import config
import lib.ffmpeg as ffmpeg
from util import Parallel, SubprocessException, find_files, spawn
from functools import partial
import logging
from librosa.util.exceptions import ParameterError
from inspect import currentframe, getframeinfo
from torch.multiprocessing import Pool

old_tqdm_init = tqdm.__init__


def new_tqdm_init(*args, **kwargs):
    """Disable tqdm progress bar for audio_separator."""
    traceback = getframeinfo(currentframe().f_back)
    if "site-packages/audio_separator" in traceback.filename:
        kwargs["disable"] = True

    old_tqdm_init(*args, **kwargs)


tqdm.__init__ = new_tqdm_init


def _custom_final_process(
    output_path: str, filename: str, self, _stem_path, source, stem_name
):
    os.makedirs(output_path, exist_ok=True)
    self.write_audio(
        os.path.join(output_path, f"{filename}_{stem_name.lower()}.wav"),
        source,
    )

    return {stem_name: source}


g_separator = None


def _init_worker():
    global g_separator
    from audio_separator.separator import Separator

    g_separator = Separator(
        log_level=logging.WARNING,
        mdx_params={
            "hop_length": 1024,
            "segment_size": 512,
            "overlap": 0.5,
            "batch_size": 1,
            "enable_denoise": True,
        },
        vr_params={
            "batch_size": 1,
            "window_size": 320,
            "aggression": 5,
            "enable_tta": False,
            "enable_post_process": False,
            "post_process_threshold": 0.2,
            "high_end_process": False,
        },
    )

    g_separator.load_model(model_filename=config.UVR_FIRST_MODEL)


def _run_worker(args, attempt=0):
    input_path, output_path, file = args

    dirname = os.path.dirname(file)
    filename = os.path.basename(file)

    g_separator.model_instance.final_process = partial(
        _custom_final_process,
        os.path.join(output_path, dirname),
        filename,
        g_separator.model_instance,
    )

    try:
        return g_separator.separate(os.path.join(input_path, file))
    except ParameterError:
        if attempt < 3:
            return _run_worker(args, attempt + 1)
        raise


async def isolate_vocals(
    input_path: str,
    output_path: str,
    overwrite: bool = True,
    batchsize=1,
    cache_path=config.TMP_PATH,
):
    """Splits audio files to vocals and the rest. The audio has to be correct wav."""

    # Load list of files
    files = []

    if overwrite:
        files = list(find_files(input_path))
    # else:
    #     skipped = 0

    #     for file in find_files(input_path):
    #         filename = os.path.basename(file)
    #         output_filename = _get_output_filename(filename, config.UVR_FIRST_MODEL)
    #         if os.path.exists(os.path.join(output_path, output_filename)):
    #             skipped += 1
    #         else:
    #             files.append(file)

    #     tqdm.write(f"Skipping {skipped} already done files.")

    if len(files) == 0:
        tqdm.write("No files to process.")
        return

    # Prepare UVR
    tqdm.write("Loading libraries...")

    pbar = tqdm(total=len(files))
    with Pool(processes=batchsize, initializer=_init_worker) as pool:
        for _result in pool.imap_unordered(
            _run_worker,
            ((input_path, output_path, file) for file in files),
        ):
            pbar.update(1)
        pool.close()
        pool.join()
