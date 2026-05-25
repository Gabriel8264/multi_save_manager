import csv
import ctypes
import os
import subprocess
from pathlib import Path

from .path_resolver import resolver_caminho

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
LOCK_ERRORS = {5, 32, 33}


def _normalize_process_token(value):
    return "".join(character.lower() for character in value if character.isalnum())


def _build_process_candidates(game_name):
    normalized = _normalize_process_token(game_name)
    candidates = {normalized}
    for token in game_name.replace("-", " ").split():
        normalized_token = _normalize_process_token(token)
        if len(normalized_token) >= 4:
            candidates.add(normalized_token)
    return {candidate for candidate in candidates if candidate}


def listar_processos():
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    processos = []
    for row in csv.reader(result.stdout.splitlines()):
        if row:
            processos.append(row[0])
    return processos


def detectar_jogo_aberto(game_name):
    candidatos = _build_process_candidates(game_name)
    encontrados = []

    for processo in listar_processos():
        normalized_process = _normalize_process_token(processo)
        if any(candidate in normalized_process for candidate in candidatos):
            encontrados.append(processo)

    return sorted(set(encontrados), key=str.lower)


def _try_open_exclusive(file_path):
    create_file = ctypes.windll.kernel32.CreateFileW
    close_handle = ctypes.windll.kernel32.CloseHandle

    handle = create_file(
        str(file_path),
        GENERIC_READ,
        0,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )

    if handle == INVALID_HANDLE_VALUE:
        error_code = ctypes.GetLastError()
        return False, error_code

    close_handle(handle)
    return True, 0


def detectar_arquivos_em_uso(diretorios, limit=5, max_scan=400):
    encontrados = []
    scanned = 0

    for raw_path in diretorios:
        directory = Path(resolver_caminho(raw_path))
        if not directory.exists():
            continue

        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                file_path = Path(root) / file_name
                scanned += 1

                ok, error_code = _try_open_exclusive(file_path)
                if not ok and error_code in LOCK_ERRORS:
                    encontrados.append(str(file_path))
                    if len(encontrados) >= limit:
                        return encontrados

                if scanned >= max_scan:
                    return encontrados

    return encontrados


def coletar_alertas_pre_troca(game_name, diretorios):
    warnings = []
    processos = detectar_jogo_aberto(game_name)
    arquivos_bloqueados = detectar_arquivos_em_uso(diretorios)

    if processos:
        warnings.append(
            "Possível jogo aberto: " + ", ".join(processos[:4])
        )

    if arquivos_bloqueados:
        exemplos = ", ".join(Path(path).name for path in arquivos_bloqueados[:3])
        warnings.append(
            "Possíveis arquivos em uso: "
            + exemplos
            + ". Feche o jogo ou os apps que estejam usando esses saves."
        )

    return warnings


def contar_arquivos_em_diretorios(diretorios):
    total = 0

    for raw_path in diretorios:
        directory = Path(resolver_caminho(raw_path))
        if not directory.exists():
            continue

        for _root, _dirs, files in os.walk(directory):
            total += len(files)

    return total
