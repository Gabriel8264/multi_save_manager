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
- `auth_enabled` fica `false` por padrao em configs antigas e passa para `true` quando a autenticação local é ativada.
- `manager_mode_enabled` prepara um modo administrativo futuro. Atualmente nao bloqueia nem libera telas.
- `current_user_id` aponta para o usuario ativo local. O padrao e `default_user`.
- `users` guarda apenas dados públicos do usuário ativo/registrado para compatibilidade com permissões. Senhas não ficam em `config.json`.
- `permission_profiles` prepara permissoes futuras. Atualmente essas permissoes nao bloqueiam funcionalidades.
- `local_user` fica preservado por compatibilidade com a etapa anterior. Nao guarda senha.
- Cada chave em `jogos` e um nome de jogo.
- Cada valor e uma lista de diretorios.
- Caminhos sao normalizados por `core.path_resolver.normalizar_caminho_salvo`.
- Duplicatas sao removidas durante validacao/migracao.

Compatibilidade: ativar o multiusuário local não deve apagar nem reconstruir a chave `jogos`. Jogos, caminhos de save e demais campos já existentes em `config.json` devem continuar acessíveis depois da criação do primeiro usuário.

## `data/users.json`

Arquivo local de credenciais. Ele é separado de `config.json` para não misturar senha/hash com a configuração histórica de jogos.

```json
{
  "schema_version": 1,
  "users": {
    "default_user": {
      "id": "default_user",
      "username": "Gabriel",
      "display_name": "Gabriel",
      "role": "manager",
      "permission_profile": "manager",
      "password": {
        "algorithm": "pbkdf2_sha256",
        "iterations": 220000,
        "salt": "hexadecimal",
        "hash": "hexadecimal"
      }
    }
  }
}
```

Regras:

- A senha nunca deve ser salva em texto puro.
- O primeiro usuário criado usa `default_user` para preservar compatibilidade com `Profiles/` legado.
- Usuários seguintes recebem ids derivados do nome de usuário, com sufixo quando necessário.
- A tela de login não lista usuários cadastrados; o login é sempre manual por usuário e senha.

## `data/session.json`

Sessão local persistente.

```json
{
  "active": true,
  "user_id": "default_user",
  "username": "Gabriel"
}
```

Regras:

- Se `active` for `true` e o usuário existir em `data/users.json`, o app abre direto no usuário salvo.
- Ao usar `Sair` ou `Trocar usuário`, o arquivo é regravado como sessão inativa.
- Depois de logout, o usuário precisa digitar usuário e senha novamente.

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
      "banner_path": "C:\\Imagens\\Nome do Jogo\\banner.jpg",
      "executable_path": "C:\\Jogos\\Nome do Jogo\\Jogo.exe",
      "launch_arguments": "-vr \"perfil alto\"",
      "launch_as_admin": false
    }
  }
}
```

Regras atuais:

- As chaves em `games` devem bater com os nomes ja cadastrados em `config.json`.
- `cover_path` e `banner_path` sao opcionais.
- `executable_path` é opcional e aceita `.exe` ou `.bat`.
- `launch_arguments` é opcional e preserva espaços/aspas como digitado.
- `launch_as_admin` força elevação via UAC apenas para o processo iniciado quando `true`.
- Quando nao ha imagem valida, a interface mostra um placeholder leve com iniciais do jogo.
- A janela `Gerenciar jogos` edita caminhos de save e configuração de inicialização. Capas/banners continuam metadados opcionais preparados para a biblioteca visual.

Compatibilidade: `game_library.json` continua opcional. Jogos antigos sem campos de inicialização usam fallback seguro e não quebram a biblioteca.

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

### Ativação da autenticação local

Antes de ativar `auth_enabled` pela primeira vez, `core.local_auth` cria um backup leve de metadados em:

```text
data/
  auth_migration_backups/
    <YYYYMMDD_HHMMSS>/
      config.json
      settings.json
      profile_state.json
      game_library.json
      manifest.json
```

Esse backup preserva os arquivos que descrevem jogos, favoritos, recentes, biblioteca visual, inicialização e estado de perfis. Ele não copia pastas reais de save nem move `Profiles/`, porque a ativação do login local não altera esses dados.

O `manifest.json` registra que dados futuros como mods, configurações de mods, coleções e perfis de inicialização estão reservados para migrações posteriores.

### Troca entre `single_user` e `multi_user`

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
