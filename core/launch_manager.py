import ctypes
import subprocess
from dataclasses import dataclass
from pathlib import Path


VALID_LAUNCH_EXTENSIONS = {".exe", ".bat"}


class LaunchError(RuntimeError):
    pass


class LaunchCancelled(LaunchError):
    pass


@dataclass(frozen=True)
class LaunchConfig:
    executable_path: str = ""
    launch_arguments: str = ""
    launch_as_admin: bool = False


def normalize_launch_config(config=None):
    config = config or {}
    return LaunchConfig(
        executable_path=str(config.get("executable_path") or "").strip(),
        launch_arguments=str(config.get("launch_arguments") or ""),
        launch_as_admin=bool(config.get("launch_as_admin", False)),
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


def _build_bat_command(launch_path, arguments):
    command = subprocess.list2cmdline(["cmd.exe", "/c", "call", str(launch_path)])
    if arguments:
        command = f"{command} {arguments}"
    return command


def _build_exe_command(launch_path, arguments):
    command = subprocess.list2cmdline([str(launch_path)])
    if arguments:
        command = f"{command} {arguments}"
    return command


def launch_game(config=None):
    config = validate_launch_config(config)
    if not config.executable_path:
        raise LaunchError("Configure um arquivo de inicialização antes de jogar.")

    launch_path = Path(config.executable_path)
    working_dir = str(launch_path.parent)
    suffix = launch_path.suffix.lower()

    if config.launch_as_admin:
        return _shell_execute("runas", launch_path, config.launch_arguments, working_dir, suffix)

    return _shell_execute("open", launch_path, config.launch_arguments, working_dir, suffix)


def _shell_execute(verb, launch_path, arguments, working_dir, suffix):
    if suffix == ".bat":
        target = "cmd.exe"
        parameters = f'/c call {subprocess.list2cmdline([str(launch_path)])}'
        if arguments:
            parameters = f"{parameters} {arguments}"
    else:
        target = str(launch_path)
        parameters = arguments

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        verb,
        target,
        parameters,
        working_dir,
        1,
    )
    if result > 32:
        return True
    if result in (5, 1223):
        raise LaunchCancelled("Inicialização cancelada pelo usuário.")
    raise LaunchError(f"Não foi possível iniciar o jogo. Código do Windows: {result}.")
