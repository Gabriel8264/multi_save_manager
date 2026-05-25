import json
from pathlib import Path

from .path_resolver import normalizar_caminho_salvo
from .validators import validate_game_name, validate_save_paths

CONFIG_FILE = Path("config.json")
APP_MODE_SINGLE_USER = "single_user"
APP_MODE_MULTI_USER = "multi_user"
LEGACY_APP_MODE_ALIASES = {
    "individual": APP_MODE_SINGLE_USER,
    "lan_house": APP_MODE_MULTI_USER,
}
VALID_APP_MODES = {APP_MODE_SINGLE_USER, APP_MODE_MULTI_USER}
DEFAULT_CURRENT_USER_ID = "default_user"
DEFAULT_PERMISSIONS = {
    "edit_games": True,
    "edit_save_paths": True,
    "delete_profiles": True,
    "access_advanced_settings": True,
    "manage_users": True,
}
PLAYER_PERMISSIONS = {
    "edit_games": False,
    "edit_save_paths": False,
    "delete_profiles": False,
    "access_advanced_settings": False,
    "manage_users": False,
}
DEFAULT_LOCAL_USER = {
    "id": DEFAULT_CURRENT_USER_ID,
    "display_name": "Usuario local",
    "role": "manager",
    "permission_profile": "manager",
}
DEFAULT_CONFIG = {
    "app_mode": APP_MODE_SINGLE_USER,
    "auth_enabled": False,
    "manager_mode_enabled": False,
    "current_user_id": DEFAULT_CURRENT_USER_ID,
    "local_user": DEFAULT_LOCAL_USER.copy(),
    "users": {
        DEFAULT_CURRENT_USER_ID: DEFAULT_LOCAL_USER.copy(),
    },
    "permission_profiles": {
        "manager": DEFAULT_PERMISSIONS.copy(),
        "player": PLAYER_PERMISSIONS.copy(),
    },
    "jogos": {},
}


def _criar_config_padrao():
    config = DEFAULT_CONFIG.copy()
    config["local_user"] = DEFAULT_LOCAL_USER.copy()
    config["users"] = {DEFAULT_CURRENT_USER_ID: DEFAULT_LOCAL_USER.copy()}
    config["permission_profiles"] = {
        "manager": DEFAULT_PERMISSIONS.copy(),
        "player": PLAYER_PERMISSIONS.copy(),
    }
    config["jogos"] = {}
    return config


def _migrar_config(config):
    jogos = config.setdefault("jogos", {})
    migrated = False

    app_mode = config.get("app_mode")
    if app_mode in LEGACY_APP_MODE_ALIASES:
        config["app_mode"] = LEGACY_APP_MODE_ALIASES[app_mode]
        migrated = True
    elif app_mode not in VALID_APP_MODES:
        config["app_mode"] = DEFAULT_CONFIG["app_mode"]
        migrated = True

    if not isinstance(config.get("auth_enabled"), bool):
        config["auth_enabled"] = DEFAULT_CONFIG["auth_enabled"]
        migrated = True

    if not isinstance(config.get("manager_mode_enabled"), bool):
        config["manager_mode_enabled"] = DEFAULT_CONFIG["manager_mode_enabled"]
        migrated = True

    if not config.get("current_user_id"):
        config["current_user_id"] = DEFAULT_CURRENT_USER_ID
        migrated = True

    local_user = config.get("local_user")
    if not isinstance(local_user, dict):
        config["local_user"] = DEFAULT_LOCAL_USER.copy()
        migrated = True
    else:
        for key, value in DEFAULT_LOCAL_USER.items():
            if not local_user.get(key):
                local_user[key] = value
                migrated = True

    users = config.get("users")
    if not isinstance(users, dict):
        users = {}
        config["users"] = users
        migrated = True

    current_user_id = str(config.get("current_user_id") or DEFAULT_CURRENT_USER_ID)
    if current_user_id not in users:
        users[current_user_id] = config.get("local_user", DEFAULT_LOCAL_USER.copy()).copy()
        users[current_user_id]["id"] = current_user_id
        migrated = True

    default_user = users.setdefault(DEFAULT_CURRENT_USER_ID, DEFAULT_LOCAL_USER.copy())
    for key, value in DEFAULT_LOCAL_USER.items():
        if not default_user.get(key):
            default_user[key] = value
            migrated = True

    permission_profiles = config.get("permission_profiles")
    if not isinstance(permission_profiles, dict):
        permission_profiles = {}
        config["permission_profiles"] = permission_profiles
        migrated = True

    for profile_name, defaults in {
        "manager": DEFAULT_PERMISSIONS,
        "player": PLAYER_PERMISSIONS,
    }.items():
        profile = permission_profiles.setdefault(profile_name, {})
        if not isinstance(profile, dict):
            permission_profiles[profile_name] = defaults.copy()
            migrated = True
            continue

        for permission, value in defaults.items():
            if not isinstance(profile.get(permission), bool):
                profile[permission] = value
                migrated = True

    for nome, diretorios in list(jogos.items()):
        if not isinstance(diretorios, list):
            jogos[nome] = []
            migrated = True
            continue

        normalized = []
        for diretorio in diretorios:
            if not isinstance(diretorio, str):
                migrated = True
                continue

            normalizado = normalizar_caminho_salvo(diretorio)
            if normalizado not in normalized:
                normalized.append(normalizado)

            if normalizado != diretorio:
                migrated = True

        if normalized != diretorios:
            jogos[nome] = normalized

    return migrated


def carregar_config():
    if not CONFIG_FILE.exists():
        config = _criar_config_padrao()
        salvar_config(config)
        return config

    with CONFIG_FILE.open("r", encoding="utf-8") as arquivo:
        data = json.load(arquivo)

    if "jogos" not in data or not isinstance(data["jogos"], dict):
        data = _criar_config_padrao()
        salvar_config(data)
        return data

    if _migrar_config(data):
        salvar_config(data)

    return data


def salvar_config(config):
    with CONFIG_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)


def listar_jogos():
    return sorted(carregar_config().get("jogos", {}).keys(), key=str.lower)


def obter_diretorios_jogo(jogo):
    config = carregar_config()
    jogos = config.get("jogos", {})

    if jogo not in jogos:
        raise FileNotFoundError("Jogo não encontrado.")

    return list(jogos[jogo])


def adicionar_jogo(nome, diretorios):
    nome = validate_game_name(nome)
    diretorios = validate_save_paths(diretorios)
    config = carregar_config()
    jogos = config.setdefault("jogos", {})

    if nome in jogos:
        raise FileExistsError("Já existe um jogo com esse nome.")

    jogos[nome] = diretorios
    salvar_config(config)
    return nome


def atualizar_jogo(nome_atual, novo_nome, diretorios):
    nome_atual = validate_game_name(nome_atual)
    novo_nome = validate_game_name(novo_nome)
    diretorios = validate_save_paths(diretorios)
    config = carregar_config()
    jogos = config.setdefault("jogos", {})

    if nome_atual not in jogos:
        raise FileNotFoundError("Jogo não encontrado.")

    if novo_nome != nome_atual and novo_nome in jogos:
        raise FileExistsError("Já existe um jogo com esse nome.")

    itens = []
    for nome, paths in jogos.items():
        if nome == nome_atual:
            itens.append((novo_nome, diretorios))
        else:
            itens.append((nome, paths))

    config["jogos"] = dict(itens)
    salvar_config(config)
    return novo_nome


def excluir_jogo(nome):
    nome = validate_game_name(nome)
    config = carregar_config()
    jogos = config.setdefault("jogos", {})

    if nome not in jogos:
        raise FileNotFoundError("Jogo não encontrado.")

    del jogos[nome]
    salvar_config(config)
    return nome
