import ctypes
import json
import subprocess
import sys
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

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_TYPE = 18
TOKEN_ELEVATION = 20
TOKEN_INTEGRITY_LEVEL = 25
TOKEN_ELEVATION_TYPE_NAMES = {
    1: "default",
    2: "full",
    3: "limited",
}
INTEGRITY_LEVEL_NAMES = (
    (0x5000, "protected_process"),
    (0x4000, "system"),
    (0x3000, "high"),
    (0x2100, "medium_plus"),
    (0x2000, "medium"),
    (0x1000, "low"),
    (0x0000, "untrusted"),
)
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", wintypes.LPVOID),
        ("Attributes", wintypes.DWORD),
    ]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", SID_AND_ATTRIBUTES)]


class TOKEN_ELEVATION_STRUCT(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_kernel32.GetCurrentProcess.argtypes = []
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.GetCurrentProcessId.argtypes = []
_kernel32.GetCurrentProcessId.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_kernel32.Process32FirstW.restype = wintypes.BOOL
_kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_kernel32.Process32NextW.restype = wintypes.BOOL

_advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_advapi32.OpenProcessToken.restype = wintypes.BOOL
_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL
_advapi32.GetSidSubAuthorityCount.argtypes = [wintypes.LPVOID]
_advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
_advapi32.GetSidSubAuthority.argtypes = [wintypes.LPVOID, wintypes.DWORD]
_advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


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

    launch_path = Path(config.executable_path).resolve()
    working_dir = str(launch_path.parent)
    suffix = launch_path.suffix.lower()

    if config.launch_as_admin:
        return _shell_execute("runas", launch_path, config.launch_arguments, working_dir, suffix)

    return _shell_execute("open", launch_path, config.launch_arguments, working_dir, suffix)


def diagnose_uac_with_notepad():
    notepad_path = Path(r"C:\Windows\System32\notepad.exe")
    if not notepad_path.exists():
        raise LaunchError("Notepad do Windows não encontrado para o teste de UAC.")

    return _shell_execute(
        "runas",
        notepad_path,
        "",
        str(notepad_path.parent),
        notepad_path.suffix.lower(),
        diagnostic_label="uac_notepad_test",
    )


def is_process_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _get_token_information(token, information_class, struct_type):
    data = struct_type()
    size = wintypes.DWORD(ctypes.sizeof(data))
    if not _advapi32.GetTokenInformation(
        token,
        information_class,
        ctypes.byref(data),
        size,
        ctypes.byref(size),
    ):
        return None
    return data


def _get_token_elevation_details(token):
    details = {}

    elevation_type = wintypes.DWORD()
    size = wintypes.DWORD(ctypes.sizeof(elevation_type))
    if _advapi32.GetTokenInformation(
        token,
        TOKEN_ELEVATION_TYPE,
        ctypes.byref(elevation_type),
        size,
        ctypes.byref(size),
    ):
        value = int(elevation_type.value)
        details["token_elevation_type"] = TOKEN_ELEVATION_TYPE_NAMES.get(value, f"unknown:{value}")
        details["token_elevation_type_raw"] = value
    else:
        details["token_elevation_type_error"] = int(ctypes.get_last_error() or 0)

    elevation = _get_token_information(token, TOKEN_ELEVATION, TOKEN_ELEVATION_STRUCT)
    if elevation is not None:
        details["token_is_elevated"] = bool(elevation.TokenIsElevated)
    else:
        details["token_is_elevated_error"] = int(ctypes.get_last_error() or 0)

    return details


def _integrity_name_from_rid(rid):
    for minimum, name in INTEGRITY_LEVEL_NAMES:
        if rid >= minimum:
            return name
    return "unknown"


def _get_integrity_level_details(token):
    required_size = wintypes.DWORD(0)
    _advapi32.GetTokenInformation(token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(required_size))
    if not required_size.value:
        return {"integrity_level_error": int(ctypes.get_last_error() or 0)}

    buffer = ctypes.create_string_buffer(required_size.value)
    if not _advapi32.GetTokenInformation(
        token,
        TOKEN_INTEGRITY_LEVEL,
        buffer,
        required_size,
        ctypes.byref(required_size),
    ):
        return {"integrity_level_error": int(ctypes.get_last_error() or 0)}

    mandatory_label = ctypes.cast(buffer, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
    sid = mandatory_label.Label.Sid
    sub_authority_count = _advapi32.GetSidSubAuthorityCount(sid).contents.value
    rid = _advapi32.GetSidSubAuthority(sid, sub_authority_count - 1).contents.value
    return {
        "integrity_level": _integrity_name_from_rid(int(rid)),
        "integrity_level_rid": int(rid),
    }


def get_parent_process_info():
    current_pid = int(_kernel32.GetCurrentProcessId())
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return {
            "current_pid": current_pid,
            "parent_process_error": int(ctypes.get_last_error() or 0),
        }

    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        found = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if int(entry.th32ProcessID) == current_pid:
                parent_pid = int(entry.th32ParentProcessID)
                return {
                    "current_pid": current_pid,
                    "current_process_name": entry.szExeFile,
                    "parent_pid": parent_pid,
                    "parent_process_name": _find_process_name_in_snapshot(snapshot, parent_pid),
                }
            found = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))

        return {
            "current_pid": current_pid,
            "parent_process_error": "current_process_not_found",
        }
    finally:
        _kernel32.CloseHandle(snapshot)


def _find_process_name_in_snapshot(snapshot, pid):
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while found:
        if int(entry.th32ProcessID) == int(pid):
            return entry.szExeFile
        found = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    return ""


def get_process_security_context():
    context = {
        "python_executable": sys.executable,
        "argv0": sys.argv[0] if sys.argv else "",
        "cwd": str(Path.cwd()),
        "is_user_an_admin": is_process_elevated(),
    }
    context.update(get_parent_process_info())

    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(_kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        context["open_process_token_error"] = int(ctypes.get_last_error() or 0)
        return context

    try:
        context.update(_get_token_elevation_details(token))
        context.update(_get_integrity_level_details(token))
    finally:
        _kernel32.CloseHandle(token)

    return context


def _write_launch_log(event, details):
    payload = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        **details,
    }
    try:
        with LAUNCH_LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _run_cli(argv):
    if "--diagnose-process-context" in argv:
        result = get_process_security_context()
        _write_launch_log("process_context", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if "--diagnose-uac-notepad" not in argv:
        return 0

    try:
        result = diagnose_uac_with_notepad()
    except LaunchCancelled as error:
        print(str(error))
        return 2
    except (LaunchError, ValueError, OSError) as error:
        print(str(error))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _shell_execute(verb, launch_path, arguments, working_dir, suffix, diagnostic_label="game_launch"):
    if suffix == ".bat":
        target = "cmd.exe"
        parameters = f'/c call {subprocess.list2cmdline([str(launch_path)])}'
        if arguments:
            parameters = f"{parameters} {arguments}"
    else:
        target = str(launch_path)
        parameters = arguments

    elevated = verb == "runas"
    already_elevated = is_process_elevated()
    diagnostics = {
        "diagnostic": diagnostic_label,
        "executable_path": str(launch_path),
        "arguments": arguments,
        "working_directory": working_dir,
        "file_extension": suffix,
        "file_type": "bat" if suffix == ".bat" else "exe",
        "launch_as_admin": elevated,
        "method": "elevated/runas" if elevated else "normal/open",
        "target": target,
        "parameters": parameters,
        "process_already_elevated": already_elevated,
        "message": (
            "Iniciando com elevação explícita via runas"
            if elevated
            else "Iniciando sem elevação explícita via open"
        ),
    }
    diagnostics.update(get_process_security_context())
    if elevated and already_elevated:
        diagnostics["uac_note"] = (
            "O processo do launcher já está elevado; o Windows pode iniciar o processo elevado sem exibir novo prompt UAC."
        )
    _write_launch_log("attempt", diagnostics)

    result = _shell_execute_w(
        None,
        verb,
        target,
        parameters,
        working_dir,
        1,
    )
    result_code = int(result or 0)
    last_error = ctypes.get_last_error()
    diagnostics["windows_result"] = result_code
    diagnostics["last_error"] = int(last_error or 0)
    if result_code > 32:
        _write_launch_log("success", diagnostics)
        return diagnostics
    if result_code in (5, 1223) or last_error == 1223:
        diagnostics["message"] = "UAC cancelado pelo usuário"
        _write_launch_log("cancelled", diagnostics)
        raise LaunchCancelled("UAC cancelado pelo usuário.")
    _write_launch_log("error", diagnostics)
    raise LaunchError(f"Não foi possível iniciar o jogo. Código do Windows: {result_code}.")


if __name__ == "__main__":
    raise SystemExit(_run_cli(sys.argv[1:]))
