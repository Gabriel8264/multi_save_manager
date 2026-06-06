import hashlib
import hmac
import json
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path

from .config_manager import (
    APP_MODE_MULTI_USER,
    DEFAULT_CURRENT_USER_ID,
    carregar_config,
    salvar_config,
)
from .storage_manager import ensure_user_storage

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"
SESSION_FILE = DATA_DIR / "session.json"
AUTH_BACKUP_DIR = DATA_DIR / "auth_migration_backups"
PASSWORD_ITERATIONS = 220_000
METADATA_FILES_TO_BACKUP = (
    Path("config.json"),
    Path("settings.json"),
    Path("game_library.json"),
    Path("profile_state.json"),
)


class AuthError(ValueError):
    pass


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_user_store():
    if not USERS_FILE.exists():
        return {"schema_version": 1, "users": {}}

    try:
        with USERS_FILE.open("r", encoding="utf-8") as arquivo:
            data = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "users": {}}

    users = data.get("users")
    if not isinstance(users, dict):
        users = {}

    return {"schema_version": 1, "users": users}


def _save_user_store(store):
    _ensure_data_dir()
    with USERS_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(store, arquivo, ensure_ascii=False, indent=2)


def _backup_existing_metadata_before_auth_change():
    existing_files = [path for path in METADATA_FILES_TO_BACKUP if path.exists()]
    if not existing_files:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = AUTH_BACKUP_DIR / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []
    for source in existing_files:
        destination = backup_dir / source.name
        shutil.copy2(source, destination)
        copied_files.append(source.as_posix())

    manifest = {
        "reason": "Backup antes de ativar autenticação local/multiusuário.",
        "copied_files": copied_files,
        "not_moved": [
            "Profiles/",
            "data/users/",
            "pastas reais de save cadastradas",
        ],
        "future_reserved_data": [
            "mods",
            "mod_settings",
            "collections",
            "launch_profiles",
        ],
    }
    with (backup_dir / "manifest.json").open("w", encoding="utf-8") as arquivo:
        json.dump(manifest, arquivo, ensure_ascii=False, indent=2)

    return backup_dir


def _normalize_username(username):
    username = str(username or "").strip()
    if not username:
        raise AuthError("Informe o usuário.")
    if len(username) > 40:
        raise AuthError("Use um nome de usuário mais curto.")
    if any(char in username for char in "\r\n\t"):
        raise AuthError("O nome de usuário contém caracteres inválidos.")
    return username


def _validate_password(password):
    password = str(password or "")
    if not password:
        raise AuthError("Informe a senha.")
    if len(password) > 256:
        raise AuthError("Use uma senha mais curta.")
    return password


def _make_user_id(username, users):
    if not users:
        return DEFAULT_CURRENT_USER_ID

    base = re.sub(r"[^a-z0-9_]+", "_", username.strip().lower())
    base = re.sub(r"_+", "_", base).strip("_") or "user"
    user_id = base
    suffix = 2
    while user_id in users:
        user_id = f"{base}_{suffix}"
        suffix += 1
    return user_id


def _hash_password(password, salt_hex=None, iterations=PASSWORD_ITERATIONS):
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": salt_hex,
        "hash": digest.hex(),
    }


def has_local_users():
    return bool(_load_user_store().get("users"))


def get_local_user(user_id):
    return _load_user_store().get("users", {}).get(user_id)


def get_local_user_by_username(username):
    username = _normalize_username(username)
    username_key = username.casefold()
    for user in _load_user_store().get("users", {}).values():
        if str(user.get("username", "")).casefold() == username_key:
            return user
    return None


def create_local_user(username, password):
    username = _normalize_username(username)
    password = _validate_password(password)
    store = _load_user_store()
    users = store.setdefault("users", {})

    if get_local_user_by_username(username):
        raise AuthError("Já existe um usuário com esse nome.")

    user_id = _make_user_id(username, users)
    role = "manager" if not users else "player"
    permission_profile = "manager" if role == "manager" else "player"
    user = {
        "id": user_id,
        "username": username,
        "display_name": username,
        "role": role,
        "permission_profile": permission_profile,
        "password": _hash_password(password),
    }
    users[user_id] = user
    _save_user_store(store)
    _sync_config_user(user)
    ensure_user_storage(user_id)
    return user


def authenticate_local_user(username, password):
    password = _validate_password(password)
    user = get_local_user_by_username(username)
    if not user:
        raise AuthError("Usuário ou senha inválidos.")

    password_data = user.get("password", {})
    if password_data.get("algorithm") != "pbkdf2_sha256":
        raise AuthError("Usuário ou senha inválidos.")

    candidate = _hash_password(
        password,
        salt_hex=password_data.get("salt"),
        iterations=int(password_data.get("iterations") or PASSWORD_ITERATIONS),
    )
    if not hmac.compare_digest(candidate["hash"], str(password_data.get("hash") or "")):
        raise AuthError("Usuário ou senha inválidos.")

    _sync_config_user(user)
    ensure_user_storage(user["id"])
    return user


def _sync_config_user(user):
    config = carregar_config()
    if not config.get("auth_enabled"):
        _backup_existing_metadata_before_auth_change()

    user_id = str(user.get("id") or DEFAULT_CURRENT_USER_ID)
    public_user = {
        "id": user_id,
        "display_name": str(user.get("display_name") or user.get("username") or user_id),
        "role": str(user.get("role") or "player"),
        "permission_profile": str(user.get("permission_profile") or "player"),
    }
    # Preserve existing games and library-related files. This sync only changes
    # authentication/session ownership fields needed by the local multi-user base.
    config["auth_enabled"] = True
    config["app_mode"] = APP_MODE_MULTI_USER
    config["current_user_id"] = user_id
    config.setdefault("users", {})[user_id] = public_user
    if user_id == DEFAULT_CURRENT_USER_ID:
        config["local_user"] = public_user.copy()
    salvar_config(config)


def create_session(user):
    _ensure_data_dir()
    session = {
        "active": True,
        "user_id": str(user.get("id") or ""),
        "username": str(user.get("username") or ""),
    }
    with SESSION_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(session, arquivo, ensure_ascii=False, indent=2)
    return session


def get_active_session():
    if not SESSION_FILE.exists():
        return None

    try:
        with SESSION_FILE.open("r", encoding="utf-8") as arquivo:
            session = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return None

    if not session.get("active"):
        return None

    user_id = str(session.get("user_id") or "")
    user = get_local_user(user_id)
    if not user:
        return None

    _sync_config_user(user)
    ensure_user_storage(user_id)
    return session


def clear_session():
    _ensure_data_dir()
    with SESSION_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump({"active": False}, arquivo, ensure_ascii=False, indent=2)
