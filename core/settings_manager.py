import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")
MAX_RECENT_GAMES = 12
DEFAULT_SETTINGS = {
    "ui_theme": "dark",
    "favorite_games": [],
    "recent_games": [],
}


def carregar_configuracoes():
    if not SETTINGS_FILE.exists():
        salvar_configuracoes(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    with SETTINGS_FILE.open("r", encoding="utf-8") as arquivo:
        data = json.load(arquivo)

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    merged["favorite_games"] = list(dict.fromkeys(merged.get("favorite_games", [])))
    merged["recent_games"] = list(dict.fromkeys(merged.get("recent_games", [])))[:MAX_RECENT_GAMES]
    return merged


def salvar_configuracoes(config):
    with SETTINGS_FILE.open("w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)


def obter_tema():
    return carregar_configuracoes().get("ui_theme", "dark")


def definir_tema(theme_name):
    if theme_name not in {"dark", "light"}:
        raise ValueError("Tema inválido.")

    config = carregar_configuracoes()
    config["ui_theme"] = theme_name
    salvar_configuracoes(config)
    return theme_name


def listar_favoritos():
    return carregar_configuracoes().get("favorite_games", [])


def listar_recentes():
    return carregar_configuracoes().get("recent_games", [])


def limpar_favoritos_orfaos(jogos_validos):
    jogos_validos = set(jogos_validos)
    config = carregar_configuracoes()
    favoritos = config.setdefault("favorite_games", [])
    favoritos_filtrados = [jogo for jogo in favoritos if jogo in jogos_validos]

    if favoritos_filtrados != favoritos:
        config["favorite_games"] = favoritos_filtrados
        salvar_configuracoes(config)

    return favoritos_filtrados


def limpar_recentes_orfaos(jogos_validos):
    jogos_validos = set(jogos_validos)
    config = carregar_configuracoes()
    recentes = config.setdefault("recent_games", [])
    recentes_filtrados = [jogo for jogo in recentes if jogo in jogos_validos][:MAX_RECENT_GAMES]

    if recentes_filtrados != recentes:
        config["recent_games"] = recentes_filtrados
        salvar_configuracoes(config)

    return recentes_filtrados


def alternar_favorito(jogo):
    config = carregar_configuracoes()
    favoritos = config.setdefault("favorite_games", [])

    if jogo in favoritos:
        favoritos.remove(jogo)
        favorito = False
    else:
        favoritos.append(jogo)
        favoritos.sort(key=str.lower)
        favorito = True

    salvar_configuracoes(config)
    return favorito


def registrar_recente(jogo):
    config = carregar_configuracoes()
    recentes = [nome for nome in config.setdefault("recent_games", []) if nome != jogo]
    recentes.insert(0, jogo)
    config["recent_games"] = recentes[:MAX_RECENT_GAMES]
    salvar_configuracoes(config)
    return config["recent_games"]


def eh_favorito(jogo):
    return jogo in listar_favoritos()


def remover_jogo_dos_favoritos(jogo):
    config = carregar_configuracoes()
    favoritos = config.setdefault("favorite_games", [])

    if jogo in favoritos:
        favoritos.remove(jogo)
        salvar_configuracoes(config)


def remover_jogo_dos_recentes(jogo):
    config = carregar_configuracoes()
    recentes = config.setdefault("recent_games", [])

    if jogo in recentes:
        recentes.remove(jogo)
        salvar_configuracoes(config)


def renomear_jogo_nos_favoritos(nome_atual, novo_nome):
    config = carregar_configuracoes()
    favoritos = config.setdefault("favorite_games", [])

    if nome_atual in favoritos:
        favoritos.remove(nome_atual)
        if novo_nome not in favoritos:
            favoritos.append(novo_nome)
            favoritos.sort(key=str.lower)
        salvar_configuracoes(config)


def renomear_jogo_nos_recentes(nome_atual, novo_nome):
    config = carregar_configuracoes()
    recentes = config.setdefault("recent_games", [])

    if nome_atual in recentes:
        recentes = [novo_nome if jogo == nome_atual else jogo for jogo in recentes]
        config["recent_games"] = list(dict.fromkeys(recentes))[:MAX_RECENT_GAMES]
        salvar_configuracoes(config)
