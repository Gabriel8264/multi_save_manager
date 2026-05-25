from pathlib import Path

from .path_resolver import normalizar_caminho_salvo, resolver_caminho

INVALID_NAME_CHARS = set('\\/:*?"<>|')
PROTECTED_APP_PATHS = [
    Path("Profiles"),
    Path("data"),
    Path("profile_state.json"),
    Path("config.json"),
    Path("settings.json"),
]


def _validate_name(value, field_label):
    name = value.strip()
    if not name:
        raise ValueError(f"Informe {field_label}.")

    invalid = sorted(INVALID_NAME_CHARS.intersection(name))
    if invalid:
        chars = " ".join(invalid)
        raise ValueError(
            f"{field_label.capitalize()} contém caracteres inválidos: {chars}."
        )

    return name


def validate_profile_name(value):
    return _validate_name(value, "um nome de perfil")


def validate_game_name(value):
    return _validate_name(value, "o nome do jogo")


def _paths_overlap(path_a, path_b):
    return path_a == path_b or path_a in path_b.parents or path_b in path_a.parents


def ensure_safe_save_directory(path_value):
    candidate = Path(path_value)
    protected_paths = [(Path.cwd() / path).resolve() for path in PROTECTED_APP_PATHS]

    for protected in protected_paths:
        if _paths_overlap(candidate.resolve(), protected):
            raise ValueError(
                "Esse caminho interfere com os arquivos internos do app. "
                "Escolha apenas a pasta de save do jogo no PC."
            )


def validate_save_path(value):
    raw_path = value.strip().strip('"').strip("'")
    if not raw_path:
        raise ValueError("Caminho vazio. Informe uma pasta existente.")

    resolved = Path(resolver_caminho(raw_path))
    if not resolved.exists():
        raise ValueError(
            f"O caminho '{raw_path}' não existe. Selecione uma pasta válida."
        )

    if not resolved.is_dir():
        raise ValueError(
            f"O caminho '{raw_path}' não é uma pasta. Escolha um diretório de save."
        )

    ensure_safe_save_directory(resolved)
    return normalizar_caminho_salvo(str(resolved))


def validate_save_paths(paths):
    cleaned_paths = []
    errors = []

    for index, path in enumerate(paths, start=1):
        stripped = path.strip()
        if not stripped:
            continue

        try:
            normalized = validate_save_path(stripped)
        except ValueError as error:
            errors.append(f"Linha {index}: {error}")
            continue

        if normalized not in cleaned_paths:
            cleaned_paths.append(normalized)

    if errors:
        raise ValueError("\n".join(errors))

    if not cleaned_paths:
        raise ValueError("Informe ao menos um diretório de save.")

    return cleaned_paths


def collect_save_path_errors(paths):
    errors = []
    for index, path in enumerate(paths, start=1):
        stripped = path.strip()
        if not stripped:
            continue

        try:
            validate_save_path(stripped)
        except ValueError as error:
            errors.append(f"Linha {index}: {error}")

    if not [path for path in paths if path.strip()]:
        errors.append("Informe ao menos um diretório de save.")

    return errors
