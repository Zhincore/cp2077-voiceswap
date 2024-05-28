import asyncio
import os
from functools import partial
import logging
from inspect import currentframe, getframeinfo
import ctypes
from typing import TYPE_CHECKING
from queue import Empty
from librosa.util.exceptions import ParameterError
from torch.multiprocessing import Process, Queue, JoinableQueue, Value
from tqdm import tqdm
import config
from util import Parallel, find_files
import lib.ffmpeg as ffmpeg

if TYPE_CHECKING:
    from audio_separator.separator import Separator


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


class UVRProcess(Process):
    """Process for running UVR"""

    def __init__(self, queue: Queue = None, progress: Value = None, **kwargs):
        Process.__init__(self, **kwargs)

        self._run = Value(ctypes.c_bool, False)
        self._queue = queue or JoinableQueue()
        self._progress = progress or Value(ctypes.c_int, 0)
        self._last_model = None
        self._separator = None

    def _separate(self, input_path: str, output_path: str, file: str, attempt=0):
        dirname = os.path.dirname(file)
        filename = os.path.basename(file)

        self._separator.model_instance.final_process = partial(
            _custom_final_process,
            os.path.join(output_path, dirname),
            filename,
            self._separator.model_instance,
        )

        try:
            return self._separator.separate(os.path.join(input_path, file))
        except ParameterError:
            if attempt < 3:
                return self._separate(input_path, output_path, file, attempt + 1)
            raise

    def terminate(self):
        if self._run:
            self._run = False
        else:
            Process.terminate(self)

    def run(self):
        from audio_separator.separator import Separator

        self._separator = Separator(
            log_level=logging.WARNING,
            model_file_dir=config.UVR_MODEL_CACHE,
            mdx_params={
                "hop_length": 1024,
                "segment_size": 512,
                "overlap": 0.5,
                "batch_size": 1,
                "enable_denoise": True,
            },
            vr_params={
                "batch_size": 4,
                "window_size": 320,
                "aggression": 5,
                "enable_tta": False,
                "enable_post_process": False,
                "post_process_threshold": 0.2,
                "high_end_process": False,
            },
        )

        while self._run:
            try:
                input_path, output_path, file, wanted_model = self._queue.get(
                    timeout=0.1
                )
            except (Empty, TimeoutError):
                continue

            try:
                # Load new model if needed
                if wanted_model != self._last_model:
                    self._separator.load_model(wanted_model)
                    self._last_model = wanted_model

                # Run separation
                self._separate(input_path, output_path, file)

                with self._progress.get_lock():
                    self._progress.value += 1
            except:
                # We failed, put the task back (I expect low VRAM, not unparsable file)
                self._queue.put((input_path, output_path, file, wanted_model))
                raise
            finally:
                # but either way we need to mark it done otherwise it would be undone twice
                self._queue.task_done()


class UVRProcessManager:
    """Manage multiple UVR processes."""

    def __init__(self, jobs=1):
        self._queue = JoinableQueue()
        self._progress = Value(ctypes.c_int, 0)
        self._wanted_model = None

        self._workers = set(
            UVRProcess(self._queue, self._progress) for _ in range(jobs)
        )
        self.pbar = tqdm(disable=True)

        for worker in self._workers:
            worker.start()

    def submit(self, input_path: str, output_path: str, file: str):
        """Submit work to workers."""
        if self._wanted_model is None:
            raise ValueError("No model has been set yet.")

        self._queue.put((input_path, output_path, file, self._wanted_model))

    def set_model(self, model: str):
        """Change to loaded model."""
        self._wanted_model = model

    def wait(self):
        """Wait for all workers to finish."""
        self._queue.join()

    async def watch(self):
        """Wait and update the progress asynchronously."""
        while self.pbar.n < self.pbar.total:
            # Update progress bar
            with self._progress.get_lock():
                self.pbar.update(self._progress.value)
                self._progress.value = 0

            # Check on workers
            for worker in [*self._workers]:
                if worker.exitcode is not None:
                    tqdm.write("WARNING: A worker died, respawning...")
                    self._workers.remove(worker)
                    new_worker = UVRProcess(self._queue, self._progress)
                    new_worker.start()
                    self._workers.add(new_worker)

            # TODO: a return queue?
            await asyncio.sleep(0.01)

    def terminate(self):
        """Terminate all workers."""
        for worker in self._workers:
            worker.terminate()

    def join(self):
        """Join all workers."""
        for worker in self._workers:
            worker.join()


async def isolate_vocals(
    input_path: str,
    cache_path=config.CACHE_PATH,
    overwrite: bool = True,
    n_workers=1,
):
    """Splits audio files to vocals and the rest. The audio has to be correct wav."""
    # Prepare paths
    formatted_path = os.path.join(cache_path, config.UVR_FORMAT_CACHE)
    split_path = os.path.join(cache_path, config.UVR_FIRST_CACHE)
    reverb_path = os.path.join(cache_path, config.UVR_SECOND_CACHE)

    # Load list of files
    files = set(find_files(input_path))

    if not overwrite:
        skipped = 0

        for file in list(files):
            output_file = file.replace(".ogg", ".wav") + config.UVR_SECOND_SUFFIX
            if os.path.exists(os.path.join(reverb_path, output_file)):
                skipped += 1
                files.remove(file)

        tqdm.write(f"Skipping {skipped} already done files.")

    if len(files) == 0:
        tqdm.write("No files to process.")
        return

    # Prepare conversion and splitting
    ffmpegs = Parallel("[Phase 1/3] Converting files", leave=True, unit="file")
    split_pbar = tqdm(desc="[Phase 2/3] Separating audio", leave=True, unit="file")
    uvr_workers = UVRProcessManager(n_workers)
    uvr_workers.pbar = split_pbar

    uvr_workers.set_model(config.UVR_FIRST_MODEL)

    async def convert_and_process(file: str):
        dirname = os.path.dirname(file)
        os.makedirs(os.path.join(formatted_path, dirname), exist_ok=True)

        converted_file = file.replace(".ogg", ".wav")
        converted_path = os.path.join(formatted_path, converted_file)
        if overwrite or not os.path.exists(converted_path):
            await ffmpeg.to_wav(os.path.join(input_path, file), converted_path)

        uvr_workers.submit(formatted_path, split_path, converted_file)

    # Run conversion and splitting
    split_files = []

    for file in files:
        output_file = file.replace(".ogg", ".wav") + config.UVR_FIRST_SUFFIX

        if not overwrite:
            output = os.path.join(split_path, output_file)
            if os.path.exists(output):
                continue

        split_files.append(output_file)

        ffmpegs.run(convert_and_process, file)

    cached = len(files) - len(split_files)

    if not overwrite and cached > 0:
        tqdm.write(f"Won't split {cached} already split files.")

    split_pbar.reset(ffmpegs.count_jobs())

    await asyncio.gather(ffmpegs.wait(), uvr_workers.watch())
    split_pbar.close()

    tqdm.write("Waiting for workers...")
    uvr_workers.wait()

    # Reset workers
    reverb_pbar = tqdm(
        total=len(files), desc="[Phase 3/3] Removing reverb", unit="file"
    )
    uvr_workers.pbar = reverb_pbar
    uvr_workers.set_model(config.UVR_SECOND_MODEL)

    for file in files:
        input_file = file.replace(".ogg", ".wav") + config.UVR_FIRST_SUFFIX
        uvr_workers.submit(split_path, reverb_path, input_file)

    await uvr_workers.watch()
    split_pbar.close()

    tqdm.write("Waiting for workers...")
    uvr_workers.wait()
    uvr_workers.terminate()
    uvr_workers.join()
