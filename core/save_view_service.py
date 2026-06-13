from dataclasses import dataclass

from .save_manager import (
    aplicar_perfil,
    criar_perfil,
    excluir_perfil,
    exportar_saves_do_jogo,
    fazer_backup,
    limpar_saves_do_jogo,
    listar_perfis,
    obter_perfil_ativo,
    renomear_perfil,
)


@dataclass(frozen=True)
class ProfileListItem:
    name: str
    active: bool = False


@dataclass(frozen=True)
class SaveProfilesView:
    game: str
    profiles: tuple[str, ...]
    filtered_profiles: tuple[ProfileListItem, ...]
    active_profile: str | None
    selected_profile: str | None
    count_text: str
    empty_message: str

    @property
    def is_empty(self):
        return not self.filtered_profiles


def get_profile_count(game):
    return len(listar_perfis(game))


def get_active_save_profile(game):
    return obter_perfil_ativo(game)


def get_save_profiles_view(game, query="", selected_profile=None):
    if not game:
        return SaveProfilesView(
            game="",
            profiles=(),
            filtered_profiles=(),
            active_profile=None,
            selected_profile=None,
            count_text="0 perfis",
            empty_message="Cadastre um jogo para começar a criar perfis.",
        )

    profiles = tuple(listar_perfis(game))
    active_profile = obter_perfil_ativo(game)
    search = str(query or "").strip().lower()
    filtered_names = tuple(profile for profile in profiles if search in profile.lower())
    resolved_selection = (
        selected_profile
        if selected_profile in profiles
        else active_profile if active_profile in profiles else None
    )

    return SaveProfilesView(
        game=game,
        profiles=profiles,
        filtered_profiles=tuple(
            ProfileListItem(name=profile, active=profile == active_profile)
            for profile in filtered_names
        ),
        active_profile=active_profile,
        selected_profile=resolved_selection,
        count_text=f"{len(filtered_names)} perfil(is)",
        empty_message="Nenhum perfil encontrado com esse filtro.",
    )


def activate_save_profile(game, profile_name, progress_callback=None):
    return aplicar_perfil(game, profile_name, progress_callback=progress_callback)


def create_save_profile(game, profile_name, progress_callback=None):
    return criar_perfil(game, profile_name, progress_callback=progress_callback)


def rename_save_profile(game, current_name, new_name):
    return renomear_perfil(game, current_name, new_name)


def delete_save_profile(game, profile_name, progress_callback=None):
    return excluir_perfil(game, profile_name, progress_callback=progress_callback)


def clear_current_save(game, progress_callback=None):
    return limpar_saves_do_jogo(game, progress_callback=progress_callback)


def save_active_profile_snapshot(game, progress_callback=None):
    active_profile = obter_perfil_ativo(game)
    if not active_profile:
        raise ValueError("Nenhum perfil ativo para receber o save atual.")
    return fazer_backup(game, active_profile, progress_callback=progress_callback)


def export_current_save(game, destination_folder, progress_callback=None):
    return exportar_saves_do_jogo(game, destination_folder, progress_callback=progress_callback)


__all__ = [
    "ProfileListItem",
    "SaveProfilesView",
    "activate_save_profile",
    "clear_current_save",
    "create_save_profile",
    "delete_save_profile",
    "export_current_save",
    "get_active_save_profile",
    "get_profile_count",
    "get_save_profiles_view",
    "rename_save_profile",
    "save_active_profile_snapshot",
]
