from dataclasses import dataclass
from pathlib import Path

from .launch_manager import launch_config_to_dict, validate_launch_config
from .validators import validate_game_name, validate_save_paths


@dataclass(frozen=True)
class GameEditorSavePayload:
    current_name: str | None
    new_name: str
    save_paths: tuple[str, ...]
    launch_config: dict


def build_game_editor_signature(
    current_name,
    new_name,
    save_paths,
    executable_path,
    launch_arguments,
    launch_as_admin,
):
    return (
        current_name,
        str(new_name or "").strip(),
        tuple(save_paths or ()),
        str(executable_path or ""),
        str(launch_arguments or ""),
        bool(launch_as_admin),
    )


def prepare_launch_config(executable_path="", launch_arguments="", launch_as_admin=False):
    launch_config = validate_launch_config(
        {
            "executable_path": str(executable_path or ""),
            "launch_arguments": str(launch_arguments or ""),
            "launch_as_admin": bool(launch_as_admin),
        }
    )
    return launch_config_to_dict(launch_config)


def prepare_launch_file_path(file_path):
    validate_launch_config({"executable_path": file_path})
    return str(Path(file_path))


def prepare_game_editor_save_payload(
    current_name,
    new_name,
    save_paths,
    launch_config=None,
):
    validated_name = validate_game_name(new_name)
    validated_paths = tuple(validate_save_paths(save_paths))
    validated_launch_config = prepare_launch_config(**(launch_config or {}))

    return GameEditorSavePayload(
        current_name=current_name,
        new_name=validated_name,
        save_paths=validated_paths,
        launch_config=validated_launch_config,
    )
