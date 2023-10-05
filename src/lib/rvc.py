import os


def get_rvc_prefix():
    venv = os.getenv("RVC_VENV")
    if venv is None or venv == "":
        return "poetry", "run"
    else:
        return os.path.join(venv, Scripts/python.exe), "python"
