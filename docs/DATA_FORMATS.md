# Formatos de Dados

## `config.json`

Guarda jogos cadastrados e suas pastas de save.

```json
{
  "app_mode": "single_user",
  "auth_enabled": false,
  "manager_mode_enabled": false,
  "current_user_id": "default_user",
  "local_user": {
    "id": "default_user",
    "display_name": "Usuario local",
    "role": "manager",
    "permission_profile": "manager"
  },
  "users": {
    "default_user": {
      "id": "default_user",
      "display_name": "Usuario local",
      "role": "manager",
      "permission_profile": "manager"
    }
  },
  "permission_profiles": {
    "manager": {
      "edit_games": true,
      "edit_save_paths": true,
      "delete_profiles": true,
      "access_advanced_settings": true,
      "manage_users": true
    },
    "player": {
      "edit_games": false,
      "edit_save_paths": false,
      "delete_profiles": false,
      "access_advanced_settings": false,
      "manage_users": false
    }
  },
  "jogos": {
    "Nome do Jogo": [
      "C:\\Users\\Usuario\\Documents\\Game\\Save",
      "D:\\OutroSave"
    ]
  }
}
```

Regras:

- `app_mode` usa o padrao atual `single_user` ou `multi_user`.
- Valores antigos `individual` e `lan_house` sao aceitos apenas como aliases de migracao para configuracoes legadas.
- `auth_enabled` fica `false` por padrao. Nao ha login implementado ainda.
- `manager_mode_enabled` prepara um modo administrativo futuro. Atualmente nao bloqueia nem libera telas.
- `current_user_id` aponta para o usuario ativo local. O padrao e `default_user`.
- `users` prepara multiusuario sem senha.
- `permission_profiles` prepara permissoes futuras. Atualmente essas permissoes nao bloqueiam funcionalidades.
- `local_user` fica preservado por compatibilidade com a etapa anterior. Nao guarda senha.
- Cada chave em `jogos` e um nome de jogo.
- Cada valor e uma lista de diretorios.
- Caminhos sao normalizados por `core.path_resolver.normalizar_caminho_salvo`.
- Duplicatas sao removidas durante validacao/migracao.

## `settings.json`

Guarda preferencias da UI.

```json
{
  "ui_theme": "dark",
  "favorite_games": ["Nome do Jogo"]
}
```

Valores aceitos para `ui_theme`:

- `dark`
- `light`

## `profile_state.json`

Guarda qual perfil esta ativo por jogo.

```json
{
  "ativo_por_jogo": {
    "Nome do Jogo": "Perfil 1"
  }
}
```

Quando saves reais sao limpos, o perfil ativo daquele jogo e removido porque o estado do disco nao corresponde mais a um backup conhecido.

## `game_library.json`

Arquivo opcional para metadados visuais da futura biblioteca gamer. Ele nao substitui nem altera `config.json`; se nao existir, o app continua usando apenas os jogos cadastrados no formato antigo.

```json
{
  "games": {
    "Nome do Jogo": {
      "cover_path": "C:\\Imagens\\Nome do Jogo\\cover.jpg",
      "banner_path": "C:\\Imagens\\Nome do Jogo\\banner.jpg"
    }
  }
}
```

Regras atuais:

- As chaves em `games` devem bater com os nomes ja cadastrados em `config.json`.
- `cover_path` e `banner_path` sao opcionais.
- Quando nao ha imagem valida, a interface mostra um placeholder leve com iniciais do jogo.
- Ainda nao ha tela para editar esses metadados; o suporte existe apenas para preparar a biblioteca visual.

## Pasta `Profiles/`

Layout:

```text
Profiles/
  Perfil 1/
    Nome do Jogo/
      pasta_0/
      pasta_1/
  Perfil 2/
    Nome do Jogo/
      pasta_0/
```

Cada `pasta_N` corresponde ao indice da pasta de save cadastrada em `config.json` para aquele jogo.

Exemplo:

```json
{
  "jogos": {
    "Jogo": ["C:\\SaveA", "D:\\SaveB"]
  }
}
```

Mapeamento:

- `Profiles/<perfil>/Jogo/pasta_0` copia de/para `C:\SaveA`.
- `Profiles/<perfil>/Jogo/pasta_1` copia de/para `D:\SaveB`.

## Estrutura futura por usuario

Base preparada para `single_user` e `multi_user`:

```text
data/
  default_user/
    profiles/
    saves/
    mods/
    settings.json
  users/
    default_user/
      profiles/
      saves/
      mods/
      settings.json
```

Compatibilidade atual:

- Para `current_user_id = "default_user"`, se a pasta legada `Profiles/` existir, ela continua sendo usada como pasta real de perfis.
- A estrutura em `data/users/default_user/` existe para evolucao futura e nao move os perfis atuais automaticamente.
- A estrutura em `data/default_user/` prepara o modo `single_user`.

## Backups de migracao

Antes de qualquer migracao entre modos, `core.mode_migration.backup_before_migration()` cria:

```text
migration_backups/
  <YYYY-MM-DD_HH-MM-SS>_<reason>/
    config.json
    settings.json
    profile_state.json
    game_library.json
    Profiles/
    data/
    manifest.json
```

Arquivos ausentes sao apenas registrados em `manifest.json`; a migracao nao falha por um arquivo opcional ausente.

## Estado de migracao

Depois de uma migracao preparada, o sistema grava:

```text
data/migration_state.json
```

Esse arquivo contem `restart_required`, `from_mode`, `to_mode`, `backup_path` e `created_at`. Ele prepara uma reinicializacao segura futura, mas hoje nao reinicia o app automaticamente.

## Exportacao

`exportar_saves_do_jogo` cria uma pasta no destino escolhido:

```text
<Jogo>_<YYYY-MM-DD_HH-MM-SS>/
  save_1/
  save_2/
  manifest.json
```

O manifesto registra jogo, horario, origens e destinos copiados.
