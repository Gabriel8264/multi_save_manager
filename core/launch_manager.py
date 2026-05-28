import ctypes
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from ctypes import wintypes


VALID_LAUNCH_EXTENSIONS = {".exe", ".bat"}
LAUNCH_LOG_FILE = Path("launcher_launch.log")

_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_shell_execute_w = _shell32.ShellExecuteW
_shell_execute_w.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_int,
]
_shell_execute_w.restype = ctypes.c_void_p


class LaunchError(RuntimeError):
    pass


class LaunchCancelled(LaunchError):
    pass


@dataclass(frozen=True)
class LaunchConfig:
    executable_path: str = ""
    launch_arguments: str = ""
    launch_as_admin: bool = False


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "sim", "on"}
    return bool(value)


def normalize_launch_config(config=None):
    config = config or {}
    return LaunchConfig(
        executable_path=str(config.get("executable_path") or "").strip(),
        launch_arguments=str(config.get("launch_arguments") or ""),
        launch_as_admin=_coerce_bool(config.get("launch_as_admin", False)),
    )


def launch_config_to_dict(config):
    config = normalize_launch_config(config.__dict__ if isinstance(config, LaunchConfig) else config)
    return {
        "executable_path": config.executable_path,
        "launch_arguments": config.launch_arguments,
        "launch_as_admin": config.launch_as_admin,
    }


def validate_launch_config(config=None):
    config = normalize_launch_config(config)
    if not config.executable_path:
        return config

    launch_path = Path(config.executable_path).resolve()
    if not launch_path.exists():
        raise ValueError("Arquivo de inicialização não encontrado.")
    if not launch_path.is_file():
        raise ValueError("O arquivo de inicialização deve ser um arquivo .exe ou .bat, não uma pasta.")
    if launch_path.suffix.lower() not in VALID_LAUNCH_EXTENSIONS:
        raise ValueError("Selecione um arquivo de inicialização .exe ou .bat.")

    return config


def has_valid_launch_config(config=None):
    try:
        config = validate_launch_config(config)
    except ValueError:
        return False
    return bool(config.executable_path)


def _write_launch_log(message):
    try:
        with LAUNCH_LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now().isoformat(timespec='seconds')} - {message}\n")
    except OSError:
        pass


def _build_bat_parameters(launch_path, arguments):
    parameters = f'/c call {subprocess.list2cmdline([str(launch_path)])}'
    if arguments:
        parameters = f"{parameters} {arguments}"
    return parameters


def _resolve_shell_execute_target(launch_path, arguments, suffix):
    if suffix == ".bat":
        return "cmd.exe", _build_bat_parameters(launch_path, arguments)
    return str(launch_path), arguments


def launch_game(config=None):
    config = validate_launch_config(config)
    if not config.executable_path:
        raise LaunchError("Configure um arquivo de inicialização antes de jogar.")

    launch_path = Path(config.executable_path).resolve()
    working_dir = str(launch_path.parent)
    suffix = launch_path.suffix.lower()
    verb = "runas" if config.launch_as_admin else "open"
    target, parameters = _resolve_shell_execute_target(launch_path, config.launch_arguments, suffix)

    result = _shell_execute_w(
        None,
        verb,
        target,
        parameters,
        working_dir,
        1,
    )
    result_code = int(result or 0)

    if result_code > 32:
        _write_launch_log(f"Jogo iniciado: {launch_path.name}")
        return True

    if result_code in (5, 1223) or ctypes.get_last_error() == 1223:
        _write_launch_log(f"UAC cancelado pelo usuário: {launch_path.name}")
        raise LaunchCancelled("UAC cancelado pelo usuário.")

    _write_launch_log(f"Falha ao iniciar: {launch_path.name}")
    raise LaunchError(f"Não foi possível iniciar o jogo. Código do Windows: {result_code}.")
