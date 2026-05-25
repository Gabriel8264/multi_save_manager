import json
import shutil
from datetime import datetime
from pathlib import Path

from .config_manager import (
    DEFAULT_CURRENT_USER_ID,
    DEFAULT_LOCAL_USER,
    carregar_config,
    salvar_config,
)
from .storage_manager import (
    DATA_DIR,
    LEGACY_PROFILES_DIR,
    SINGLE_USER_DIR,
    USERS_DIR,
)

MIGRATION_BACKUPS_DIR = Path("migration_backups")
MIGRATION_STATE_FILE = DATA_DIR / "migration_state.json"
USER_SUBDIRS = ("profiles", "saves", "mods")


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _ensure_user_tree(user_root):
    user_root.mkdir(parents=True, exist_ok=True)
    for subdir in USER_SUBDIRS:
        (user_root / subdir).mkdir(parents=True, exist_ok=True)

    settings_file = user_root / "settings.json"
    if not settings_file.exists():
        _write_json(settings_file, {"schema_version": 1})


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as arquivo:
        json.dump(data, arquivo, ensure_ascii=False, indent=2)


def _copy_missing(source, destination):
    source = Path(source)
    destination = Path(destination)

    if not source.exists():
        return

    if source.is_file():
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return

    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        _copy_missing(item, destination / item.name)


def _copy_backup_item(source, backup_root):
    source = Path(source)
    if not source.exists():
        return False

    destination = backup_root / source.name
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return True


def _mark_restart_required(from_mode, to_mode, backup_path):
    _write_json(
        MIGRATION_STATE_FILE,
        {
            "restart_required": True,
            "from_mode": from_mode,
            "to_mode": to_mode,
            "backup_path": str(backup_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


def backup_before_migration(reason="mode_migration"):
    backup_root = MIGRATION_BACKUPS_DIR / f"{_timestamp()}_{reason}"
    backup_root.mkdir(parents=True, exist_ok=True)

    items = [
        Path("config.json"),
        Path("settings.json"),
        Path("profile_state.json"),
        Path("game_library.json"),
        LEGACY_PROFILES_DIR,
        DATA_DIR,
    ]

    copied = []
    missing = []
    for item in items:
        if _copy_backup_item(item, backup_root):
            copied.append(str(item))
        else:
            missing.append(str(item))

    _write_json(
        backup_root / "manifest.json",
        {
            "reason": reason,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "copied": copied,
            "missing": missing,
        },
    )
    return backup_root


def get_primary_user(preferred_user_id=None):
    config = carregar_config()
    users = config.get("users", {})

    if preferred_user_id and preferred_user_id in users:
        return preferred_user_id

    current_user_id = config.get("current_user_id")
    if current_user_id and current_user_id in users:
        return current_user_id

    if DEFAULT_CURRENT_USER_ID in users:
        return DEFAULT_CURRENT_USER_ID

    if users:
        return sorted(users.keys(), key=str.lower)[0]

    return DEFAULT_CURRENT_USER_ID


def migrate_single_to_multi(primary_user_id=None):
    config = carregar_config()
    from_mode = config.get("app_mode", "single_user")
    selected_user_id = primary_user_id or get_primary_user()
    backup_path = backup_before_migration("single_to_multi")

    users = config.setdefault("users", {})
    if selected_user_id not in users:
        user_data = DEFAULT_LOCAL_USER.copy()
        user_data["id"] = selected_user_id
        users[selected_user_id] = user_data

    target_root = USERS_DIR / selected_user_id
    _ensure_user_tree(target_root)

    if SINGLE_USER_DIR.exists():
        _copy_missing(SINGLE_USER_DIR, target_root)

    if LEGACY_PROFILES_DIR.exists():
        _copy_missing(LEGACY_PROFILES_DIR, target_root / "profiles")

    config["app_mode"] = "multi_user"
    config["current_user_id"] = selected_user_id
    salvar_config(config)
    _mark_restart_required(from_mode, "multi_user", backup_path)
    return {
        "from_mode": from_mode,
        "to_mode": "multi_user",
        "primary_user_id": selected_user_id,
        "backup_path": str(backup_path),
        "restart_required": True,
    }


def migrate_multi_to_single(primary_user_id=None):
    config = carregar_config()
    from_mode = config.get("app_mode", "single_user")
    selected_user_id = get_primary_user(primary_user_id)
    backup_path = backup_before_migration("multi_to_single")

    source_root = USERS_DIR / selected_user_id
    _ensure_user_tree(source_root)
    _ensure_user_tree(SINGLE_USER_DIR)
    _copy_missing(source_root, SINGLE_USER_DIR)

    config["app_mode"] = "single_user"
    config["current_user_id"] = selected_user_id
    salvar_config(config)
    _mark_restart_required(from_mode, "single_user", backup_path)
    return {
        "from_mode": from_mode,
        "to_mode": "single_user",
        "primary_user_id": selected_user_id,
        "backup_path": str(backup_path),
        "restart_required": True,
    }
