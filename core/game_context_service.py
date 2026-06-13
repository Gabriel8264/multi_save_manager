import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config_manager import obter_diretorios_jogo
from .game_manager import obter_launch_config_jogo
from .launch_manager import has_valid_launch_config
from .save_manager import listar_perfis, obter_perfil_ativo
from .settings_manager import registrar_recente


@dataclass(frozen=True)
class GameContextSummary:
    name: str
    save_paths: tuple[str, ...]
    profile_total: int
    active_profile: str | None
    launch_config: dict
    can_launch: bool
    initials: str


@dataclass(frozen=True)
class OpenGameDirectoriesResult:
    game: str
    opened_count: int
    opened_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]


def get_game_initials(game_name: str) -> str:
    return "".join(part[:1] for part in game_name.split()[:2]).upper() or "JG"


def get_game_context_summary(game_name: str) -> GameContextSummary:
    save_paths = tuple(obter_diretorios_jogo(game_name))
    launch_config = obter_launch_config_jogo(game_name)
    profiles = listar_perfis(game_name)

    return GameContextSummary(
        name=game_name,
        save_paths=save_paths,
        profile_total=len(profiles),
        active_profile=obter_perfil_ativo(game_name),
        launch_config=launch_config,
        can_launch=has_valid_launch_config(launch_config),
        initials=get_game_initials(game_name),
    )


def _open_path_with_system(path: Path) -> None:
    os.startfile(path)


def open_game_save_directories(
    game_name: str,
    opener: Callable[[Path], None] | None = None,
) -> OpenGameDirectoriesResult:
    opener = opener or _open_path_with_system
    opened_paths = []
    missing_paths = []

    registrar_recente(game_name)

    for raw_path in obter_diretorios_jogo(game_name):
        path = Path(raw_path)
        if path.is_dir():
            opener(path)
            opened_paths.append(str(path))
        else:
            missing_paths.append(str(path))

    return OpenGameDirectoriesResult(
        game=game_name,
        opened_count=len(opened_paths),
        opened_paths=tuple(opened_paths),
        missing_paths=tuple(missing_paths),
    )
