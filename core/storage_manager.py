import json
from pathlib import Path

from .user_manager import get_current_user_id

DATA_DIR = Path("data")
SINGLE_USER_DIR = DATA_DIR / "default_user"
USERS_DIR = DATA_DIR / "users"
LEGACY_PROFILES_DIR = Path("Profiles")


def get_user_root(user_id=None):
    return USERS_DIR / (user_id or get_current_user_id())


def get_single_user_root():
    return SINGLE_USER_DIR


def get_user_profiles_dir(user_id=None):
    current_user_id = user_id or get_current_user_id()
    if current_user_id == "default_user" and LEGACY_PROFILES_DIR.exists():
        return LEGACY_PROFILES_DIR
    return get_user_root(current_user_id) / "profiles"


def get_user_saves_dir(user_id=None):
    return get_user_root(user_id) / "saves"


def get_user_mods_dir(user_id=None):
    return get_user_root(user_id) / "mods"


def get_user_settings_file(user_id=None):
    return get_user_root(user_id) / "settings.json"


def ensure_user_storage(user_id=None):
    root = get_user_root(user_id)
    for path in (
        root,
        root / "profiles",
        root / "saves",
        root / "mods",
    ):
        path.mkdir(parents=True, exist_ok=True)

    settings_file = root / "settings.json"
    if not settings_file.exists():
        with settings_file.open("w", encoding="utf-8") as arquivo:
            json.dump({"schema_version": 1}, arquivo, ensure_ascii=False, indent=2)

    return root
