import os
import re
from pathlib import Path, PureWindowsPath

USER_HOME_PATTERN = re.compile(
    r"^(?P<drive>[A-Za-z]:)[\\/]+Users[\\/]+(?P<user>[^\\/]+)(?P<suffix>(?:[\\/].*)?)$"
)


def _map_foreign_user_home(caminho):
    current_home = Path(os.environ["USERPROFILE"])
    match = USER_HOME_PATTERN.match(caminho)
    if not match:
        return caminho

    drive = match.group("drive")
    suffix = match.group("suffix") or ""
    current_home_str = str(current_home)

    if not current_home_str.lower().startswith(drive.lower()):
        return caminho

    suffix_parts = PureWindowsPath(suffix.lstrip("\\/")).parts
    candidate = current_home.joinpath(*suffix_parts)
    if candidate.exists():
        return str(candidate)

    return caminho


def resolver_caminho(caminho):
    expanded = caminho.replace("{USERPROFILE}", os.environ["USERPROFILE"])
    expanded = os.path.expandvars(expanded)
    expanded = os.path.expanduser(expanded)
    expanded = _map_foreign_user_home(expanded)
    return str(Path(expanded))


def normalizar_caminho_salvo(caminho):
    return str(Path(resolver_caminho(caminho)))
