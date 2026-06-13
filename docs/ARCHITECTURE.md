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

### `local_auth.py`

Autenticação local simples e manual, sem conta online.

- `create_local_user(username, password)`: cria usuário em `data/users.json`.
- `authenticate_local_user(username, password)`: valida usuário/senha.
- `create_session(user)`: grava sessão ativa em `data/session.json`.
- `get_active_session()`: valida sessão persistente e sincroniza `current_user_id`.
- `clear_session()`: remove a sessão ativa para exigir login manual.

Senhas usam PBKDF2-SHA256 com salt. O primeiro usuário criado usa `default_user` para preservar compatibilidade com `Profiles/` legado e jogos existentes.

Antes da primeira ativação de autenticação, o módulo cria backup leve dos metadados em `data/auth_migration_backups/<timestamp>/`, incluindo `config.json`, `settings.json`, `profile_state.json` e `game_library.json` quando existirem. Ele não move nem apaga jogos, perfis, saves ou biblioteca visual.

### `user_manager.py`

Camada minima para expor usuário atual, modo e permissões para o restante do app.

- `obter_usuario_local()`: retorna o usuario padrao local.
- `obter_modo_app()`: retorna `single_user` ou `multi_user`.
- `autenticacao_ativada()`: reflete `auth_enabled` do `config.json`.
- `get_current_user_id()`: retorna `default_user` por padrao.
- `get_current_user()`: retorna o usuario atual.
- `is_manager_mode()`: indica se o contexto atual e manager/admin.
- `get_current_permissions()`: retorna flags para `edit_games`, `edit_save_paths`, `delete_profiles`, `access_advanced_settings` e `manage_users`.

Senha e sessão ficam em `core.local_auth`; `user_manager.py` não valida credenciais e não conhece senha.

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
- Configuração de inicialização opcional: `executable_path`, `launch_arguments` e `launch_as_admin`, também em `game_library.json`.
- `listar_jogos_biblioteca(query)`: lista jogos filtrados e ordenados com favoritos no topo.
- `listar_nomes_jogos(query)`: atalho para a UI que precisa apenas dos nomes.
- `salvar_jogo(nome_atual, novo_nome, diretorios)`: adiciona ou atualiza jogo e propaga renomeacoes para perfis/favoritos.
- `excluir_jogo_com_dados(jogo)`: remove perfis, favoritos e config do jogo.
- `alternar_favorito_jogo(jogo)` e `jogo_eh_favorito(jogo)`: fachada para favoritos.

### `game_context_service.py`

Camada de servico independente da UI para montar o contexto rapido de um jogo. Ela existe para evitar que telas CustomTkinter precisem combinar diretamente config, perfis, recentes e launch.

- `get_game_context_summary(jogo)`: retorna caminhos de save, total de perfis, perfil ativo, config de inicializacao, estado de launch valido e iniciais visuais.
- `open_game_save_directories(jogo)`: registra o jogo como recente, abre apenas diretorios existentes e retorna contadores/caminhos abertos ou ausentes.

Essa camada nao importa CustomTkinter, tkinter nem widgets. Uma futura UI em PySide6 pode chamar as mesmas funcoes sem duplicar regras de negocio.

### `game_editor_service.py`

Camada de servico independente da UI para preparar salvamentos do editor `Gerenciar jogos`.

- `build_game_editor_signature(...)`: gera a assinatura usada pelo autosave para detectar mudancas reais.
- `prepare_launch_file_path(caminho)`: valida se o arquivo de inicializacao selecionado e `.exe` ou `.bat` e devolve o caminho normalizado para persistencia.
- `prepare_game_editor_save_payload(...)`: valida nome, diretorios de save e configuracao de inicializacao antes de chamar a camada de persistencia.

A tela continua responsavel por campos, mensagens, foco, botoes e drag and drop. O servico apenas valida e prepara payloads para reduzir acoplamento com CustomTkinter.

### `collection_view_service.py`

Camada de servico independente da UI para preparar dados da tela `Coleções`.

- `get_collections_overview()`: lista colecoes do usuario atual e devolve titulo, texto de resumo e cards com contagem de jogos.
- `get_open_collection_view(collection_id)`: resolve uma colecao aberta, associa seus `game_ids` aos jogos globais e informa jogos ausentes.
- `create_collection(nome)`: fachada para criar colecao usando as validacoes de `collections_manager.py`.

A UI continua responsavel por cards, botoes, modal de criacao e mensagens visuais. O servico concentra leitura, validacao, criacao e preparacao dos dados renderizados.

### `save_view_service.py`

Camada de servico independente da UI para preparar dados e acoes da area de Saves/Perfis.

- `get_save_profiles_view(jogo, query, selected_profile)`: lista perfis, aplica filtro, identifica perfil ativo, resolve selecao atual e devolve dados prontos para renderizacao.
- `get_profile_count(jogo)` e `get_active_save_profile(jogo)`: atalhos para resumos do contexto do jogo.
- `activate_save_profile(...)`, `create_save_profile(...)`, `rename_save_profile(...)`, `delete_save_profile(...)`: fachadas para operacoes de perfil.
- `save_active_profile_snapshot(...)`, `clear_current_save(...)`, `export_current_save(...)`: fachadas para acoes sobre o save atual.

A tela continua responsavel por layout, cards, botoes, progresso, confirmacoes e mensagens. O servico centraliza leitura, regras de perfil ativo e chamadas ao `save_manager.py`.

### `launch_manager.py`

Camada de inicialização de jogos.

- Aceita `.exe` e `.bat`.
- Preserva argumentos como digitados.
- Usa a pasta do arquivo como working directory.
- Quando `launch_as_admin` é `true`, usa ShellExecuteW com verbo `runas` para pedir elevação/UAC apenas ao processo iniciado.
- Mantém logs mínimos: jogo iniciado, falha ao iniciar e UAC cancelado.

### `launch_service.py`

Fachada independente da UI para executar uma configuracao de inicializacao e devolver resultado estruturado.

- `execute_launch_config(config)`: valida e executa via `launch_manager.launch_game(...)`, preservando `.exe`, `.bat`, argumentos, working directory e `runas`.
- Retorna `LaunchExecutionResult` com `success`, `cancelled`, `message` e `level`.

A UI do botao `Jogar` nao chama `subprocess`, `os.startfile`, `ShellExecuteW` nem trata excecoes de launch diretamente; ela apenas exibe a mensagem retornada pelo servico.

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

### `path_service.py`

Camada independente da UI para operacoes de caminhos usadas por diretorios de save.

- `validate_save_path_lines(...)`: valida linhas de caminhos e retorna linhas invalidas e caminhos normalizados.
- `append_save_directories(...)`: processa caminhos vindos de DnD/selecao, aceita apenas pastas existentes e evita duplicatas por caminho resolvido.
- `open_save_directories(...)` e `open_save_directory(...)`: abrem pastas pelo mecanismo do sistema, sem expor `os.startfile` para a UI.

A UI continua responsavel por `filedialog`, DnD visual, textbox, cores, feedback e interacao do usuario.

### `runtime_checks.py`

Antes de operacoes perigosas, tenta detectar:

- processo do jogo aberto via `tasklist`;
- arquivos possivelmente bloqueados usando `CreateFileW` exclusivo.

Essas checagens geram avisos, nao bloqueios absolutos.

## Pacote `app_ui`

### `app.py`

Contem `SaveManagerApp`, a janela principal.

Responsabilidades:

- controlar tela de login/criação de usuário antes de montar a UI principal;
- selecionar jogo atual;
- listar, buscar, criar, renomear, excluir e carregar perfis;
- chamar operacoes do `core` em thread;
- mostrar progresso, overlay e status;
- abrir o modal interno `GameManagerWindow`.

A tela de login não lista usuários cadastrados. Se `data/session.json` tiver sessão ativa válida, o app monta a UI principal diretamente. O botão do usuário ativo na navegação permite `Trocar usuário` ou `Sair`, ambos limpando a sessão.

#### Navegacao persistente

A UI principal usa frames persistentes para evitar piscadas e reconstrucoes visiveis. `SaveManagerApp` cria a estrutura principal uma vez e navega com `tkraise()`/atualizacao de estado em vez de destruir e recriar telas.

Frames principais mantidos em memoria:

- Home;
- Colecoes;
- contexto do jogo;
- Mods;
- Config;
- `modal_layer`.

Ao trocar pagina ou jogo, a regra e atualizar dados pontuais: textos, estado ativo, listas, cards afetados e paineis de contexto. Evite `destroy()` em containers estruturais.

#### Camada de modais internos

`SaveManagerApp` possui uma camada interna chamada `modal_layer`, criada por `_build_modal_layer()`.

Funcoes principais:

- `_prepare_modal_layer(close_callback)`;
- `_create_internal_modal_panel(...)`;
- `_hide_modal_layer()`;
- `_handle_modal_background_click(...)`;
- `_handle_modal_escape(...)`.

No estado atual, `modal_layer` acumula as funcoes de overlay, captura de clique fora e container do modal ativo. Nao existe um `ModalRoot` separado com `overlay_dim` e `modal_slot`.

Fluxos como `Mais acoes` e `Criar colecao` criam paineis temporarios como filhos diretos de `modal_layer`. O fluxo `Gerenciar jogos` tambem usa `modal_layer`, mas e uma excecao importante: ele e pre-construido por `_prebuild_game_manager_modal()` e revelado por `_reveal_game_manager_modal()`. Seu fundo esmaecido e especial, baseado em captura da janela com `ImageGrab` e desenho em um `Canvas`.

A animacao generica ativa e apenas de abertura, via `app_ui.widgets.animate_modal_open(...)`. Nao ha animacao global de fechamento no estado atual.

Detalhes completos da infraestrutura estao em `docs/MODALS.md`.

#### Atualizacao granular de cards

Cards de jogos sao cacheados por contexto visual para reduzir rebuild:

- `library_cards`: lista rapida da sidebar;
- `home_shelf_cards`: prateleiras de favoritos/recentes;
- `open_collection_game_cards`: jogos dentro de uma colecao aberta.

Cada card possui uma assinatura dos dados renderizados. Quando nome, favorito, capa/banner, caminhos de save ou contagem de perfis mudam, somente o card afetado e recriado. Mudancas simples, como selecao e favorito, atualizam o widget existente.

### `game_manager_window.py`

Modal interno para cadastrar, editar e excluir jogos. Ele e renderizado dentro de um overlay da janela principal, como um painel sem borda, e usa callbacks recebidos de `SaveManagerApp` para salvar/excluir.

`app_ui/game_manager.py` foi mantido como shim de compatibilidade para importar `GameManagerWindow`.

Cuidados do modal:

- Nao use `CTkToplevel` nesse fluxo; o gerenciador atual e um `CTkFrame` dentro de overlay.
- O overlay escuro bloqueia a interface de fundo e fecha ao clicar fora do painel.
- O botao `X` do painel e a tecla `Esc` fecham o modal.
- Clique dentro do painel nao deve fechar o modal.
- O botao `Salvar alteracoes` foi removido; o cadastro usa autosave.
- Campos de texto usam debounce curto/perda de foco/Enter; acoes diretas, como selecionar executavel, alternar admin e adicionar pastas, salvam imediatamente.
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
