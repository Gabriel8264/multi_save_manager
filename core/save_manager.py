import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .config_manager import obter_diretorios_jogo
from .path_resolver import resolver_caminho
from .storage_manager import get_user_profiles_dir
from .validators import ensure_safe_save_directory, validate_profile_name

STATE_FILE = Path("profile_state.json")
RESTORE_BACKUPS_DIR = Path("data") / "restore_backups"


def _emit_progress(callback, progress, message):
    if callback:
        callback(max(0.0, min(progress, 1.0)), message)


def _scale_progress(callback, start, end):
    if not callback:
        return None

    def scaled(progress, message):
        mapped = start + ((end - start) * progress)
        callback(mapped, message)

    return scaled


class ProgressTracker:
    def __init__(self, total_steps, callback):
        self.total_steps = max(total_steps, 1)
        self.current = 0
        self.callback = callback
        _emit_progress(self.callback, 0.0, "Preparando operação...")

    def step(self, message):
        self.current += 1
        _emit_progress(self.callback, self.current / self.total_steps, message)

    def message(self, message):
        _emit_progress(self.callback, self.current / self.total_steps, message)

    def finish(self, message):
        _emit_progress(self.callback, 1.0, message)


def garantir_pasta(caminho):
    Path(caminho).mkdir(parents=True, exist_ok=True)


def _carregar_estado():
    if not STATE_FILE.exists():
        return {"ativo_por_jogo": {}}

    with STATE_FILE.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _salvar_estado(estado):
    with STATE_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(estado, arquivo, ensure_ascii=False, indent=2)


def _setar_perfil_ativo(jogo, perfil):
    estado = _carregar_estado()
    estado.setdefault("ativo_por_jogo", {})[jogo] = perfil
    _salvar_estado(estado)


def limpar_perfil_ativo(jogo):
    estado = _carregar_estado()
    ativos = estado.setdefault("ativo_por_jogo", {})

    if jogo in ativos:
        del ativos[jogo]
        _salvar_estado(estado)


def renomear_jogo_no_estado(nome_atual, novo_nome):
    estado = _carregar_estado()
    ativos = estado.setdefault("ativo_por_jogo", {})

    if nome_atual in ativos:
        ativos[novo_nome] = ativos.pop(nome_atual)
        _salvar_estado(estado)


def obter_perfil_ativo(jogo):
    estado = _carregar_estado()
    return estado.get("ativo_por_jogo", {}).get(jogo)


def _obter_pasta_perfil(perfil, jogo=None):
    perfil_path = get_user_profiles_dir() / perfil
    if jogo is None:
        return perfil_path
    return perfil_path / jogo


def listar_perfis(jogo):
    profiles_dir = get_user_profiles_dir()
    garantir_pasta(profiles_dir)
    perfis = []

    for nome in profiles_dir.iterdir():
        if nome.is_dir() and _obter_pasta_perfil(nome.name, jogo).is_dir():
            perfis.append(nome.name)

    return sorted(perfis, key=str.lower)


def _list_files(root_path):
    root = Path(root_path)
    if not root.exists():
        return []
    return [path.relative_to(root) for path in root.rglob("*") if path.is_file()]


def _list_deletion_steps(root_path):
    root = Path(root_path)
    if not root.exists():
        return []

    items = []
    for current_root, directories, files in os.walk(root, topdown=False):
        current_root_path = Path(current_root)
        for file_name in files:
            items.append(current_root_path / file_name)
        for directory_name in directories:
            items.append(current_root_path / directory_name)
    return items


def _count_sync_steps(source_dirs, target_dirs):
    total = 0
    for source, target in zip(source_dirs, target_dirs):
        total += len(_list_files(source))
        total += len(_list_deletion_steps(target))
    return max(total, 1)


def _remove_tree_contents(root_path, tracker, context_label):
    root = Path(root_path)
    if not root.exists():
        return

    for item in _list_deletion_steps(root):
        if item.is_dir():
            item.rmdir()
        else:
            item.unlink()
        tracker.step(f"{context_label}: removendo {item.name}")


def _copy_tree_contents(source_path, target_path, tracker, context_label):
    source = Path(source_path)
    target = Path(target_path)
    if not source.exists():
        return

    for directory in sorted(path for path in source.rglob("*") if path.is_dir()):
        (target / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)

    for relative_file in _list_files(source):
        source_file = source / relative_file
        target_file = target / relative_file
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)
        tracker.step(f"{context_label}: copiando {relative_file.name}")


def _copy_tree_contents_without_progress(source_path, target_path):
    source = Path(source_path)
    target = Path(target_path)
    if not source.exists():
        return

    for directory in sorted(path for path in source.rglob("*") if path.is_dir()):
        (target / directory.relative_to(source)).mkdir(parents=True, exist_ok=True)

    for relative_file in _list_files(source):
        source_file = source / relative_file
        target_file = target / relative_file
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)


def _replace_tree_contents(source_path, target_path, tracker, context_label):
    target = Path(target_path)
    garantir_pasta(target)
    _remove_tree_contents(target, tracker, context_label)
    _copy_tree_contents(source_path, target, tracker, context_label)


def _validate_complete_profile_paths(profile_paths):
    missing = [
        f"pasta_{index}"
        for index, profile_path in enumerate(profile_paths)
        if not profile_path.is_dir()
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            "Perfil incompleto. Nada foi alterado nos saves reais. "
            f"Pastas ausentes: {missing_text}."
        )


def _backup_current_save_paths(save_paths):
    RESTORE_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_root = RESTORE_BACKUPS_DIR / f"msm_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    backup_root.mkdir(parents=True, exist_ok=False)
    backup_paths = []

    try:
        for index, save_path in enumerate(save_paths):
            backup_path = backup_root / f"pasta_{index}"
            backup_path.mkdir(parents=True, exist_ok=True)
            if save_path.exists():
                _copy_tree_contents_without_progress(save_path, backup_path)
            backup_paths.append(backup_path)
    except Exception:
        shutil.rmtree(backup_root, ignore_errors=True)
        raise

    return backup_root, backup_paths


def _restore_save_backups(save_paths, backup_paths):
    rollback_tracker = ProgressTracker(1, None)
    for save_path, backup_path in zip(save_paths, backup_paths):
        _replace_tree_contents(backup_path, save_path, rollback_tracker, "Rollback")


def _resolver_diretorios(paths):
    resolved_paths = [Path(resolver_caminho(path)) for path in paths]
    for path in resolved_paths:
        ensure_safe_save_directory(path)
    return resolved_paths


def _criar_nome_exportacao(jogo):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_game_name = "".join(char if char not in '<>:"/\\|?*' else "_" for char in jogo).strip()
    return f"{safe_game_name or 'save'}_{timestamp}"


def fazer_backup(jogo, perfil, progress_callback=None):
    perfil = validate_profile_name(perfil)
    save_paths = _resolver_diretorios(obter_diretorios_jogo(jogo))
    profile_paths = [
        _obter_pasta_perfil(perfil, jogo) / f"pasta_{index}"
        for index in range(len(save_paths))
    ]

    tracker = ProgressTracker(_count_sync_steps(save_paths, profile_paths), progress_callback)
    tracker.message("Salvando o estado atual dos saves...")

    for index, (save_path, profile_path) in enumerate(zip(save_paths, profile_paths), start=1):
        garantir_pasta(profile_path)
        _remove_tree_contents(profile_path, tracker, f"Backup {index}")
        _copy_tree_contents(save_path, profile_path, tracker, f"Backup {index}")

    tracker.finish(f"Backup do perfil '{perfil}' concluído.")
    return perfil


def carregar_perfil(jogo, perfil, progress_callback=None):
    perfil = validate_profile_name(perfil)

    if perfil not in listar_perfis(jogo):
        raise FileNotFoundError("Perfil não encontrado.")

    save_paths = _resolver_diretorios(obter_diretorios_jogo(jogo))
    profile_paths = [
        _obter_pasta_perfil(perfil, jogo) / f"pasta_{index}"
        for index in range(len(save_paths))
    ]
    _validate_complete_profile_paths(profile_paths)

    backup_root, backup_paths = _backup_current_save_paths(save_paths)
    total_steps = _count_sync_steps(profile_paths, save_paths)
    total_steps += _count_sync_steps(save_paths, backup_paths)
    tracker = ProgressTracker(total_steps, progress_callback)
    tracker.message("Carregando perfil selecionado...")

    try:
        for index, (profile_path, save_path) in enumerate(zip(profile_paths, save_paths), start=1):
            _replace_tree_contents(profile_path, save_path, tracker, f"Perfil {index}")
    except Exception as restore_error:
        try:
            _restore_save_backups(save_paths, backup_paths)
        except Exception as rollback_error:
            raise RuntimeError(
                "Falha ao carregar o perfil e a recuperacao automatica tambem falhou. "
                f"Backup temporario preservado em: {backup_root}"
            ) from rollback_error
        raise RuntimeError(
            "Falha ao carregar o perfil. Os saves reais foram restaurados a partir "
            "do backup temporario."
        ) from restore_error
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)

    _setar_perfil_ativo(jogo, perfil)
    tracker.finish(f"Perfil '{perfil}' carregado com sucesso.")
    return perfil


def criar_perfil(jogo, perfil, progress_callback=None):
    perfil = validate_profile_name(perfil)

    if perfil in listar_perfis(jogo):
        raise FileExistsError("Já existe um perfil com esse nome.")

    fazer_backup(jogo, perfil, progress_callback=progress_callback)
    _setar_perfil_ativo(jogo, perfil)
    return perfil


def aplicar_perfil(jogo, perfil_destino, progress_callback=None):
    perfil_destino = validate_profile_name(perfil_destino)
    perfil_ativo = obter_perfil_ativo(jogo)

    if perfil_destino not in listar_perfis(jogo):
        raise FileNotFoundError("Perfil não encontrado.")

    if perfil_ativo and perfil_ativo != perfil_destino:
        fazer_backup(
            jogo,
            perfil_ativo,
            progress_callback=_scale_progress(progress_callback, 0.0, 0.45),
        )
        carregar_perfil(
            jogo,
            perfil_destino,
            progress_callback=_scale_progress(progress_callback, 0.45, 1.0),
        )
    else:
        carregar_perfil(jogo, perfil_destino, progress_callback=progress_callback)
    return perfil_destino


def renomear_perfil(jogo, nome_atual, novo_nome):
    nome_atual = validate_profile_name(nome_atual)
    novo_nome = validate_profile_name(novo_nome)

    origem = _obter_pasta_perfil(nome_atual, jogo)
    destino = _obter_pasta_perfil(novo_nome, jogo)

    if nome_atual not in listar_perfis(jogo):
        raise FileNotFoundError("Perfil não encontrado.")

    if destino.exists():
        raise FileExistsError("Já existe um perfil com esse nome.")

    garantir_pasta(destino.parent)
    shutil.move(str(origem), str(destino))

    pasta_raiz_antiga = _obter_pasta_perfil(nome_atual)
    if pasta_raiz_antiga.is_dir() and not any(pasta_raiz_antiga.iterdir()):
        pasta_raiz_antiga.rmdir()

    if obter_perfil_ativo(jogo) == nome_atual:
        _setar_perfil_ativo(jogo, novo_nome)

    return novo_nome


def excluir_perfil(jogo, perfil, progress_callback=None):
    perfil = validate_profile_name(perfil)
    pasta_perfil = _obter_pasta_perfil(perfil, jogo)

    if perfil not in listar_perfis(jogo):
        raise FileNotFoundError("Perfil não encontrado.")

    tracker = ProgressTracker(max(len(_list_deletion_steps(pasta_perfil)), 1), progress_callback)
    tracker.message(f"Excluindo arquivos do perfil '{perfil}'...")
    _remove_tree_contents(pasta_perfil, tracker, "Exclusão de perfil")
    if pasta_perfil.exists():
        pasta_perfil.rmdir()

    pasta_raiz = _obter_pasta_perfil(perfil)
    if pasta_raiz.is_dir() and not any(pasta_raiz.iterdir()):
        pasta_raiz.rmdir()

    if obter_perfil_ativo(jogo) == perfil:
        limpar_perfil_ativo(jogo)

    tracker.finish(f"Perfil '{perfil}' excluído com sucesso.")
    return perfil


def validar_renomeacao_jogo_em_perfis(nome_atual, novo_nome):
    profiles_dir = get_user_profiles_dir()
    garantir_pasta(profiles_dir)
    plan = []

    for perfil in profiles_dir.iterdir():
        if not perfil.is_dir():
            continue

        origem = _obter_pasta_perfil(perfil.name, nome_atual)
        destino = _obter_pasta_perfil(perfil.name, novo_nome)

        if not origem.is_dir():
            continue

        if destino.exists():
            raise FileExistsError(
                "Já existe uma pasta de perfis para o novo nome do jogo."
            )

        plan.append((origem, destino))

    return plan


def renomear_jogo_em_perfis(nome_atual, novo_nome):
    original_state = _carregar_estado()
    plan = validar_renomeacao_jogo_em_perfis(nome_atual, novo_nome)
    moved = []
    try:
        for origem, destino in plan:
            garantir_pasta(destino.parent)
            shutil.move(str(origem), str(destino))
            moved.append((origem, destino))

        renomear_jogo_no_estado(nome_atual, novo_nome)
    except Exception:
        for origem, destino in reversed(moved):
            if destino.exists() and not origem.exists():
                garantir_pasta(origem.parent)
                shutil.move(str(destino), str(origem))
        _salvar_estado(original_state)
        raise


def excluir_jogo_dos_perfis(jogo, progress_callback=None):
    profiles_dir = get_user_profiles_dir()
    garantir_pasta(profiles_dir)
    pastas = []

    for perfil in profiles_dir.iterdir():
        if perfil.is_dir():
            pasta_jogo = _obter_pasta_perfil(perfil.name, jogo)
            if pasta_jogo.is_dir():
                pastas.append(pasta_jogo)

    total_steps = sum(len(_list_deletion_steps(pasta)) for pasta in pastas) or 1
    tracker = ProgressTracker(total_steps, progress_callback)

    for pasta_jogo in pastas:
        _remove_tree_contents(pasta_jogo, tracker, f"Excluindo {pasta_jogo.parent.name}")
        if pasta_jogo.exists():
            pasta_jogo.rmdir()

        pasta_raiz = pasta_jogo.parent
        if pasta_raiz.is_dir() and not any(pasta_raiz.iterdir()):
            pasta_raiz.rmdir()

    limpar_perfil_ativo(jogo)
    tracker.finish(f"Perfis do jogo '{jogo}' removidos.")


def limpar_saves_do_jogo(jogo, progress_callback=None):
    save_paths = _resolver_diretorios(obter_diretorios_jogo(jogo))
    total_steps = sum(len(_list_deletion_steps(path)) for path in save_paths) or 1
    tracker = ProgressTracker(total_steps, progress_callback)
    tracker.message("Limpando as pastas de save do jogo...")

    for index, save_path in enumerate(save_paths, start=1):
        _remove_tree_contents(save_path, tracker, f"Limpeza {index}")

    # Depois da limpeza, o estado atual do jogo não corresponde mais a nenhum backup carregado.
    limpar_perfil_ativo(jogo)
    tracker.finish(f"Pastas de save de '{jogo}' limpas.")


def exportar_saves_do_jogo(jogo, destino_base, progress_callback=None):
    save_paths = _resolver_diretorios(obter_diretorios_jogo(jogo))
    destino_base_path = Path(destino_base)
    destino_exportacao = destino_base_path / _criar_nome_exportacao(jogo)
    garantir_pasta(destino_exportacao)

    total_steps = sum(len(_list_files(path)) for path in save_paths) + 1
    tracker = ProgressTracker(total_steps, progress_callback)
    tracker.message("Exportando os saves atuais...")

    manifesto = {
        "jogo": jogo,
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
        "origens": [str(path) for path in save_paths],
        "pastas": [],
    }

    for index, save_path in enumerate(save_paths, start=1):
        pasta_destino = destino_exportacao / f"save_{index}"
        garantir_pasta(pasta_destino)
        _copy_tree_contents(save_path, pasta_destino, tracker, f"Exportação {index}")
        manifesto["pastas"].append(
            {
                "indice": index,
                "origem": str(save_path),
                "destino": str(pasta_destino),
            }
        )

    manifesto_path = destino_exportacao / "manifest.json"
    with manifesto_path.open("w", encoding="utf-8") as arquivo:
        json.dump(manifesto, arquivo, ensure_ascii=False, indent=2)
    tracker.step("Finalizando exportação...")

    tracker.finish(f"Save atual exportado para '{destino_exportacao}'.")
    return str(destino_exportacao)


def trocar_perfil(jogo, perfil_atual, perfil_novo):
    fazer_backup(jogo, perfil_atual)
    carregar_perfil(jogo, perfil_novo)
