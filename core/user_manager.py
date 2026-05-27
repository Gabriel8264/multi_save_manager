from dataclasses import dataclass

from .config_manager import carregar_config


@dataclass(frozen=True)
class LocalUser:
    id: str
    display_name: str
    role: str
    permission_profile: str = "manager"


DEFAULT_PERMISSION_FLAGS = {
    "edit_games": True,
    "edit_save_paths": True,
    "delete_profiles": True,
    "access_advanced_settings": True,
    "manage_users": True,
}


def get_current_user_id():
    return str(carregar_config().get("current_user_id") or "default_user")


def get_current_user():
    config = carregar_config()
    current_user_id = get_current_user_id()
    users = config.get("users", {})
    user_data = users.get(current_user_id) or config.get("local_user", {})

    return LocalUser(
        id=str(user_data.get("id") or current_user_id),
        display_name=str(user_data.get("display_name") or "Usuário local"),
        role=str(user_data.get("role") or "manager"),
        permission_profile=str(user_data.get("permission_profile") or "manager"),
    )


def get_current_permissions():
    config = carregar_config()
    user = get_current_user()
    profiles = config.get("permission_profiles", {})
    permissions = DEFAULT_PERMISSION_FLAGS.copy()
    permissions.update(profiles.get(user.permission_profile, {}))
    return {key: bool(permissions.get(key, False)) for key in DEFAULT_PERMISSION_FLAGS}


def is_manager_mode():
    config = carregar_config()
    return bool(config.get("manager_mode_enabled", False))


def obter_usuario_local():
    return get_current_user()


def obter_modo_app():
    return carregar_config().get("app_mode", "single_user")


def autenticacao_ativada():
    return bool(carregar_config().get("auth_enabled", False))
