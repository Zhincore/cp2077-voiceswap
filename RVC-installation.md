# Installing RVC from source

[RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md) is a tool to change voice of an audio. It also allows to split audio to vocals and background noise, which is very useful for our purposes.

The linked README isn't very clear so I'll try to write the basic steps.
Choose whether you want to use [Poetry](https://python-poetry.org/docs/) or just pip, I'll try to describe both options.

1. Clone the [linked repository](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) or download it as zip and unpack.
2. **If you use pip,** create a virtual environment using `py -m venv venv` and activate it using `.\.venv\Scripts\activate`.
3. Install base dependencies:
   - **Poetry:** `poetry install`.
   - **Pip:** Choose the right command for your machine in the [`You can also use pip to install them:` section](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md).
4. Install the correct Torch for your system, _if you plan to use CPU only you can skip this step_:
   - Visit [PyTorch's documentation](https://pytorch.org/get-started/locally/), choose Stable, your OS, pip, Python and lastly choose either CUDA 11.8 or ROCm.
   - **With Poetry** run the generated command like `poetry run <command>`.
   - **With Pip** run the command directly.
5. Install onnxruntime:
   - **Poetry:** `poetry install onnxruntime`
   - **With Pip:** `pip install onnxruntime`
   - **If you use GPU** replace `onnxruntime` with `onnxruntime-gpu` in the above command for better performance!
6. Download the required models:
   - **Poetry:** `poetry run python tools/download_models.py`
   - **Pip:** `python tools/download_models.py`
7. Try to start the WebUI:
   - **Poetry:** `poetry run python infer-web.py`
   - **Pip:** `python infer-web.py`

**Note:** Intel ARC and AMD ROCm have some extra instructions in the [RVC's README](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/blob/main/docs/en/README.en.md).

If everything went correctly, after the last step, RVC should boot up and show you a page in your browser. You can now close the page and press `Ctrl+C` in the console to quit the script.
