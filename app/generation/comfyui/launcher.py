import subprocess
import time


COMFY_PYTHON = (
    r"C:\Users\USER\Documents\ComfyUI\.venv\Scripts\python.exe"
)

COMFYUI_MAIN = r"C:\Users\USER\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\main.py"

COMFYUI_BASE = r"C:\Users\USER\Documents\ComfyUI"

def start_comfyui():
    return subprocess.Popen(
        [
            COMFY_PYTHON,
            "-s",
            COMFYUI_MAIN,

            "--base-directory",
            COMFYUI_BASE,

            "--user-directory",
            rf"{COMFYUI_BASE}\user",

            "--database-url",
            rf"sqlite:///{COMFYUI_BASE}\user\comfyui.db",

            "--port",
            "8000",

            "--enable-manager",

            "--extra-model-paths-config",
            r"C:\Users\USER\AppData\Roaming\Comfy Desktop"
            r"\instance-model-paths\inst-1788425594142.yaml",

            "--input-directory",
            rf"{COMFYUI_BASE}\input",

            "--output-directory",
            rf"{COMFYUI_BASE}\output",
        ],
        cwd=COMFYUI_BASE,
    )

def stop_comfyui(process):

    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()