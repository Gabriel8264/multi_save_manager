# Arquitetura

## Visao geral

O projeto separa interface grafica e regras de negocio:

- `main.py`: ponto de entrada minimalista.
- `ui.py`: ponto de entrada/exportacao legado para `SaveManagerApp`.
- `app_ui/`: janelas, widgets e tema.
- `core/`: persistencia JSON, validacao, resolucao de caminhos, operacoes de save e checagens de runtime.

Nao ha banco de dados. O estado fica em JSON e os backups ficam em pastas comuns.

## Pacote `core`

### `config_manager.py`

Responsavel por `config.json`.

- Defaults globais: `app_mode`, `auth_enabled`, `manager_mode_enabled`, `current_user_id`, `local_user`, `users`, `permission_profiles` e `jogos`.
- Migra configuracoes antigas que tinham apenas `jogos`, preservando o formato atual dos saves.
- `listar_jogos()`
- `obter_diretorios_jogo(jogo)`
- `adicionar_jogo(nome, diretorios)`
- `atualizar_jogo(nome_atual, novo_nome, diretorios)`
- `excluir_jogo(nome)`

Tambem migra configuracoes antigas normalizando caminhos e removendo entradas invalidas.

### `user_manager.py`

Camada minima para preparar modos futuros, multiusuario e permissoes sem login.

- `obter_usuario_local()`: retorna o usuario padrao local.
- `obter_modo_app()`: retorna `single_user` ou `multi_user`.
- `autenticacao_ativada()`: retorna `False` por padrao.
- `get_current_user_id()`: retorna `default_user` por padrao.
- `get_current_user()`: retorna o usuario atual.
- `is_manager_mode()`: indica se o contexto atual e manager/admin.
- `get_current_permissions()`: retorna flags para `edit_games`, `edit_save_paths`, `delete_profiles`, `access_advanced_settings` e `manage_users`.

Nao ha senha, tela de login ou recuperacao de senha.

### `storage_manager.py`

Centraliza caminhos internos por usuario.

- `get_single_user_root()`: `data/default_user`, base futura do modo `single_user`.
- `get_user_root()`: `data/users/<usuario>`.
- `get_user_profiles_dir()`: pasta de perfis do usuario atual.
- `get_user_saves_dir()`: area futura para saves por usuario.
- `get_user_mods_dir()`: area futura para mods por usuario.
- `get_user_settings_file()`: settings locais do usuario.
- `ensure_user_storage()`: garante a estrutura basica.

Compatibilidade: para `default_user`, se `Profiles/` existir, os perfis continuam vindo de `Profiles/`.

### `mode_migration.py`

Camada dedicada para preparar transicoes futuras entre `single_user` e `multi_user`.

- `backup_before_migration()`: cria backup automatico em `migration_backups/<timestamp>_<reason>/`.
- `migrate_single_to_multi()`: copia dados de `data/default_user` e `Profiles/` para `data/users/<usuario>`, sem apagar origem.
- `migrate_multi_to_single()`: copia dados do usuario principal de `data/users/<usuario>` para `data/default_user`, sem apagar origem.
- `get_primary_user()`: decide qual usuario representa o modo `single_user` ao voltar de `multi_user`.

As migrações marcam `data/migration_state.json` com `restart_required = true`; nenhuma reinicializacao e feita automaticamente.

### `settings_manager.py`

Responsavel por `settings.json`.

- Tema: `obter_tema()`, `definir_tema(theme_name)`.
- Favoritos: `listar_favoritos()`, `alternar_favorito(jogo)`, `eh_favorito(jogo)`.
- Manutencao ao renomear/excluir jogo.

### `game_manager.py`

Camada de aplicacao para biblioteca de jogos. Ela nao muda o formato do `config.json`; apenas centraliza operacoes que antes ficavam na UI.

- `GameLibraryItem`: representacao interna de um jogo com nome, pastas de save e favorito.
- Metadados visuais opcionais: `cover_path` e `banner_path`, lidos de `game_library.json` quando existir.
- `listar_jogos_biblioteca(query)`: lista jogos filtrados e ordenados com favoritos no topo.
- `listar_nomes_jogos(query)`: atalho para a UI que precisa apenas dos nomes.
- `salvar_jogo(nome_atual, novo_nome, diretorios)`: adiciona ou atualiza jogo e propaga renomeacoes para perfis/favoritos.
- `excluir_jogo_com_dados(jogo)`: remove perfis, favoritos e config do jogo.
- `alternar_favorito_jogo(jogo)` e `jogo_eh_favorito(jogo)`: fachada para favoritos.

### `save_manager.py`

Modulo mais sensivel: copia e apaga arquivos.

- `fazer_backup(jogo, perfil)`: copia saves reais para a pasta de perfis do usuario atual.
- `carregar_perfil(jogo, perfil)`: limpa pastas reais de save e copia o perfil para elas.
- `criar_perfil(jogo, perfil)`: cria backup inicial e marca como ativo.
- `aplicar_perfil(jogo, perfil_destino)`: salva perfil ativo atual e carrega o destino.
- `limpar_saves_do_jogo(jogo)`: remove conteudo das pastas reais configuradas.
- `exportar_saves_do_jogo(jogo, destino_base)`: copia saves atuais para pasta de exportacao com `manifest.json`.

O progresso e reportado por callbacks no formato `(valor_0_a_1, mensagem)`.

### `validators.py`

Valida nomes de jogos/perfis e caminhos de save.

Caracteres proibidos em nomes:

```text
\ / : * ? " < > |
```

Tambem bloqueia sobreposicao com caminhos internos do app:

- `Profiles`
- `profile_state.json`
- `config.json`
- `settings.json`

### `path_resolver.py`

Expande variaveis de ambiente, `~` e `{USERPROFILE}`. Tambem tenta mapear caminhos `C:\Users\<outro_usuario>\...` para o usuario atual quando a mesma subpasta existe.

### `runtime_checks.py`

Antes de operacoes perigosas, tenta detectar:

- processo do jogo aberto via `tasklist`;
- arquivos possivelmente bloqueados usando `CreateFileW` exclusivo.

Essas checagens geram avisos, nao bloqueios absolutos.

## Pacote `app_ui`

### `app.py`

Contem `SaveManagerApp`, a janela principal.

Responsabilidades:

- selecionar jogo atual;
- listar, buscar, criar, renomear, excluir e carregar perfis;
- chamar operacoes do `core` em thread;
- mostrar progresso, overlay e status;
- abrir `GameManagerWindow`.

### `game_manager_window.py`

Janela para cadastrar, editar e excluir jogos. Usa callbacks recebidos da janela principal para salvar/excluir.

`app_ui/game_manager.py` foi mantido como shim de compatibilidade para importar `GameManagerWindow`.

Cuidados da janela:

- Ela deve se comportar como janela secundaria normal do app, sem overlay escuro, sem `grab_set`, sem `-topmost` global e sem `focus_force()` recorrente.
- Para evitar flicker/desenho visivel ao abrir, a janela nasce oculta, estabiliza layout/scroll/DnD e so depois aparece.
- O drag and drop da area `Diretorios de save` depende de `tkinterdnd2` ativo na raiz e de registros nos widgets visiveis sob o cursor.
- Se o DnD falhar, mantenha `Selecionar pasta` como fallback; nao remova a area visual de arrastar pastas.

### `widgets.py`

Componentes reutilizaveis:

- `ValidatedEntry`
- `PathListEditor`
- `ProfileCard`
- `BusyOverlay`

### `dnd_support.py`

Integra `tkinterdnd2` de forma opcional. Se a dependencia falhar, a aplicacao continua funcionando sem arrastar e soltar.

Pontos importantes:

- `get_dnd_ctk_base()` escolhe a classe base da janela principal com suporte a TkDnD quando disponivel.
- `enable_tkdnd(root)` cria o contexto compartilhado usado pela UI.
- Targets de drop precisam retornar acao aceita em `DropEnter` e `DropPosition`; se o callback nao retornar copy/COPY, o Explorer pode mostrar cursor proibido.
- CustomTkinter cria widgets internos. Ao registrar DnD em componentes compostos, registre tambem filhos reais que podem receber o mouse.

### `theme.py`

Centraliza cores e `apply_theme`.

## Concorrencia

A UI chama `_run_operation(...)`, que:

1. ativa estado ocupado;
2. cria uma thread daemon;
3. executa a funcao de trabalho;
4. agenda atualizacao da UI com `self.after(...)`;
5. desativa o estado ocupado ao terminar.

Toda atualizacao de widget deve acontecer na thread principal via `after`.
