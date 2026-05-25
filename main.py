import ctypes
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
EXPECTED_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def _prepare_desktop_runtime():
    os.chdir(PROJECT_ROOT)

    running_python = Path(sys.executable).resolve()
    if EXPECTED_PYTHON.exists() and running_python != EXPECTED_PYTHON.resolve():
        print(
            "[Multiple Save Manager] Python incorreto detectado. "
            f"Reabrindo com {EXPECTED_PYTHON}."
        )
        subprocess.Popen([str(EXPECTED_PYTHON), str(PROJECT_ROOT / "main.py")], cwd=PROJECT_ROOT)
        sys.exit(0)

    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            print(
                "[Multiple Save Manager] Aviso: o app esta rodando como administrador. "
                "O Windows pode bloquear drag and drop vindo do Explorer normal."
            )
    except Exception:
        pass


if __name__ == "__main__":
    _prepare_desktop_runtime()
    from app_ui import run_app

    run_app()
