import json
from dataclasses import dataclass
from pathlib import Path

from .config_manager import (
    adicionar_jogo,
    atualizar_jogo,
    excluir_jogo,
    listar_jogos,
    obter_diretorios_jogo,
)
from .save_manager import (
    excluir_jogo_dos_perfis,
    renomear_jogo_em_perfis,
    validar_renomeacao_jogo_em_perfis,
)
from .settings_manager import (
    alternar_favorito,
    eh_favorito,
    limpar_favoritos_orfaos,
    limpar_recentes_orfaos,
    remover_jogo_dos_favoritos,
    remover_jogo_dos_recentes,
    renomear_jogo_nos_favoritos,
    renomear_jogo_nos_recentes,
)
from .validators import validate_game_name, validate_save_paths

LIBRARY_FILE = Path("game_library.json")


@dataclass(frozen=True)
class GameLibraryItem:
    name: str
    save_paths: tuple[str, ...]
    favorite: bool = False
    cover_path: str = ""
    banner_path: str = ""


def _carregar_metadados_biblioteca():
    if not LIBRARY_FILE.exists():
        return {}

    try:
        with LIBRARY_FILE.open("r", encoding="utf-8") as arquivo:
            data = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}

    jogos = data.get("games", {})
    if not isinstance(jogos, dict):
        return {}

    return jogos


def _obter_metadados_jogo(jogo, metadados=None):
    metadados = metadados if metadados is not None else _carregar_metadados_biblioteca()
    dados_jogo = metadados.get(jogo, {})
    if not isinstance(dados_jogo, dict):
        return {"cover_path": "", "banner_path": ""}

    return {
        "cover_path": str(dados_jogo.get("cover_path") or ""),
        "banner_path": str(dados_jogo.get("banner_path") or ""),
    }


def listar_jogos_biblioteca(query=""):
    nomes_jogos = listar_jogos()
    favoritos = set(limpar_favoritos_orfaos(nomes_jogos))
    metadados = _carregar_metadados_biblioteca()
    termo = query.strip().lower()
    jogos = []

    for nome in nomes_jogos:
        if termo and termo not in nome.lower():
            continue

        dados_visuais = _obter_metadados_jogo(nome, metadados)
        jogos.append(
            GameLibraryItem(
                name=nome,
                save_paths=tuple(obter_diretorios_jogo(nome)),
                favorite=nome in favoritos,
                cover_path=dados_visuais["cover_path"],
                banner_path=dados_visuais["banner_path"],
            )
        )

    return sorted(jogos, key=lambda jogo: (not jogo.favorite, jogo.name.lower()))


def listar_nomes_jogos(query=""):
    return [jogo.name for jogo in listar_jogos_biblioteca(query)]


def listar_jogos_recentes_biblioteca():
    jogos = {jogo.name: jogo for jogo in listar_jogos_biblioteca("")}
    recentes = limpar_recentes_orfaos(jogos.keys())
    return [jogos[nome] for nome in recentes if nome in jogos]


def jogo_eh_favorito(jogo):
    return eh_favorito(jogo)


def alternar_favorito_jogo(jogo):
    return alternar_favorito(jogo)


def salvar_jogo(nome_atual, novo_nome, diretorios):
    novo_nome = validate_game_name(novo_nome)
    diretorios = validate_save_paths(diretorios)

    if not nome_atual:
        return adicionar_jogo(novo_nome, diretorios)

    nome_atual = validate_game_name(nome_atual)
    jogos = listar_jogos()
    if nome_atual not in jogos:
        raise FileNotFoundError("Jogo não encontrado.")

    if nome_atual != novo_nome and novo_nome in jogos:
        raise FileExistsError("Já existe um jogo com esse nome.")

    diretorios_anteriores = obter_diretorios_jogo(nome_atual)

    if nome_atual != novo_nome:
        validar_renomeacao_jogo_em_perfis(nome_atual, novo_nome)

    atualizado = atualizar_jogo(nome_atual, novo_nome, diretorios)

    try:
        if nome_atual != novo_nome:
            renomear_jogo_em_perfis(nome_atual, novo_nome)
            renomear_jogo_nos_favoritos(nome_atual, novo_nome)
            renomear_jogo_nos_recentes(nome_atual, novo_nome)
    except Exception:
        if nome_atual != novo_nome:
            try:
                renomear_jogo_em_perfis(novo_nome, nome_atual)
            except Exception:
                pass
            try:
                renomear_jogo_nos_favoritos(novo_nome, nome_atual)
            except Exception:
                pass
            try:
                renomear_jogo_nos_recentes(novo_nome, nome_atual)
            except Exception:
                pass
            try:
                atualizar_jogo(novo_nome, nome_atual, diretorios_anteriores)
            except Exception:
                pass
        raise

    return atualizado


def excluir_jogo_com_dados(jogo, progress_callback=None):
    excluir_jogo_dos_perfis(jogo, progress_callback=progress_callback)
    remover_jogo_dos_favoritos(jogo)
    remover_jogo_dos_recentes(jogo)
    return excluir_jogo(jogo)
