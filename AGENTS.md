# Guia Para Agentes

Este projeto e um app desktop Python/Tkinter para gerenciar saves de jogos. Leia este arquivo antes de explorar o repo: ele existe para reduzir uso de contexto e evitar trabalho repetido.

## Resumo rapido

- Entrada principal: `main.py`, que chama `app_ui.run_app()`.
- Compatibilidade legada: `ui.py` exporta `SaveManagerApp` e tambem roda o app.
- UI: pacote `app_ui/`, com CustomTkinter.
- Regras de negocio e arquivos: pacote `core/`.
- Biblioteca/orquestracao de jogos: `core/game_manager.py`.
- Modo/usuario atual e permissoes: `core/user_manager.py`, alimentado por `app_mode`, `auth_enabled`, `manager_mode_enabled`, `current_user_id`, `users` e `permission_profiles` em `config.json`.
- Login local manual e sessao persistente: `core/local_auth.py`. Credenciais ficam em `data/users.json` com hash PBKDF2 + salt; sessao ativa fica em `data/session.json`.
- Caminhos internos por usuario: `core/storage_manager.py`; `default_user` preserva `Profiles/` quando existir.
- Migração futura entre `single_user` e `multi_user`: `core/mode_migration.py`. As funções sempre fazem backup em `migration_backups/` antes de alterar modo.
- Modal interno de cadastro de jogos: `app_ui/game_manager_window.py`; `app_ui/game_manager.py` e apenas um shim de compatibilidade.
- Dados locais do usuario: `config.json`, `settings.json`, `profile_state.json`, `Profiles/`, `data/users.json`, `data/session.json`.
- Metadados visuais opcionais da biblioteca: `game_library.json`.
- Backup antes da primeira ativacao de auth local: `data/auth_migration_backups/`.
- Build existente: `ui.spec` para PyInstaller.
- `git` nao estava disponivel neste terminal em 2026-05-22.
- A `.venv` foi reparada em 2026-05-22 usando `C:\Users\INFORTECH\AppData\Local\Python\bin\python.exe` como Python base. O alias `python` do Windows/Microsoft Store ainda pode falhar; prefira sempre `.\.venv\Scripts\python.exe` neste projeto.
- `main.py` tenta relancar o app com `.\.venv\Scripts\python.exe` quando detecta outro interpretador. Isso evita o bug em que o PyCharm abre sem `tkinterdnd2` e o drag and drop fica bloqueado.

## Comandos uteis

Rodar o app:

```powershell
.\.venv\Scripts\python.exe main.py
```

Se a `.venv` voltar a quebrar, recrie com uma instalacao real do Python:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Verificar sintaxe/importacao basica:

```powershell
.\.venv\Scripts\python.exe -m compileall app_ui core main.py ui.py
```

Build com PyInstaller:

```powershell
pyinstaller ui.spec
```

Listar arquivos rapidamente:

```powershell
rg --files
```

## Arquitetura em uma tela

`app_ui.app.SaveManagerApp` coordena a janela principal. Ele chama funcoes puras/procedurais do `core` para ler configuracoes, validar caminhos, criar backups, carregar perfis, exportar saves e limpar pastas. Operacoes lentas rodam em `threading.Thread` e retornam progresso para a UI via `after(...)`.

Fluxo principal de troca de perfil:

1. UI chama `aplicar_perfil(jogo, perfil_destino)`.
2. Se houver perfil ativo diferente, `fazer_backup` salva o perfil atual.
3. `carregar_perfil` limpa as pastas reais de save e copia os arquivos do perfil escolhido.
4. `profile_state.json` e atualizado com o perfil ativo.

## Pontos de cuidado

- Nunca apague ou sobrescreva `Profiles/`, `config.json`, `settings.json` ou `profile_state.json` sem pedido explicito.
- Nunca apague ou sobrescreva `game_library.json` sem pedido explicito; ele pode conter capas/banners locais.
- Nunca apague `data/users.json` ou `data/session.json` sem pedido explicito; isso afeta login/sessao local.
- Nao mova `Profiles/` para `data/users/default_user/profiles` automaticamente sem pedido explicito; o fallback atual preserva os perfis existentes.
- A primeira ativacao de multiusuario local deve preservar jogos, favoritos, recentes, executaveis, argumentos, caminhos de save e biblioteca visual. Se adaptar estrutura de dados, crie backup antes.
- O app manipula pastas de save reais do usuario. Prefira testar com diretorios temporarios.
- `core.validators.ensure_safe_save_directory` impede que uma pasta de save aponte para arquivos internos do app.
- Historicamente alguns textos visiveis tiveram mojibake. Ao editar UI, corrija texto quebrado com cuidado e salve como UTF-8.
- `tkinterdnd2` e opcional: se falhar, `app_ui.dnd_support.enable_tkdnd` retorna `None` e a UI desativa drag and drop.
- Drag and drop no Windows depende do processo estar no mesmo nivel de privilegio do Explorer. Se o app rodar como administrador e o Explorer nao, o cursor pode mostrar bloqueio mesmo com `tkinterdnd2` correto.
- `Gerenciar jogos` e sensivel a DnD/autosave. Ele nao deve abrir como `CTkToplevel`; o fluxo atual e um modal interno (`CTkFrame`) em overlay dentro da janela principal.
- O overlay de `Gerenciar jogos` fecha ao clicar fora, pelo `X` interno ou por `Esc`. Clique dentro do painel nao deve fechar o modal.
- `Gerenciar jogos` nao possui botao `Salvar alteracoes`; usa autosave com debounce para texto e salvamento imediato para acoes diretas como executavel, admin e diretorios.
- Evite `grab_set`, `WindowStaysOnTopHint`, `-topmost`, modalidade pesada ou `focus_force()` nesse fluxo.
- Ao mexer no DnD, registre o widget visivel e filhos reais que ficam sob o cursor. Os callbacks de `DropEnter` e `DropPosition` precisam retornar acao aceita (`COPY`/copy); apenas executar logica interna nao basta para o Explorer aceitar o drop.
- `os.startfile` em `PathListEditor` e especifico de Windows.

## Onde alterar o que

- Nova regra de validacao: `core/validators.py`.
- Mudanca no formato de config de jogos: `core/config_manager.py`.
- Mudancas futuras de modo `single_user`/`multi_user` ou usuario local: `core/user_manager.py` e defaults de `core/config_manager.py`.
- Mudancas futuras de login, senha, sessao ou troca de usuario: `core/local_auth.py`.
- Mudancas futuras de armazenamento multiusuario: `core/storage_manager.py`.
- Mudancas futuras de troca de modo ou migração de dados: `core/mode_migration.py`.
- Operacoes de biblioteca de jogos, favoritos e manutencao ao renomear/excluir jogo: `core/game_manager.py`.
- Mudanca em favoritos/tema: `core/settings_manager.py`.
- Troca, backup, exclusao ou exportacao de saves: `core/save_manager.py`.
- Avisos antes de trocar saves: `core/runtime_checks.py`.
- Layout principal: `app_ui/app.py`.
- Modal interno de cadastro de jogos: `app_ui/game_manager_window.py`.
- Infraestrutura atual de modais internos: `SaveManagerApp._build_modal_layer`, `_prepare_modal_layer`, `_create_internal_modal_panel`, `_hide_modal_layer` e o fluxo especial de `Gerenciar jogos` em `app_ui/app.py`. Leia `docs/MODALS.md` antes de mexer em overlay, animação ou z-order.
- Componentes reutilizaveis: `app_ui/widgets.py`.
- Paleta/tema: `app_ui/theme.py`.

## Politica atual da UI

- A navegacao principal usa frames persistentes. Evite destruir/recriar `Home`, `Colecoes`, `GameContext`, `Mods` e `Config`; mostre/oculte frames e atualize textos/listas.
- Todos os modais internos devem reutilizar `modal_layer` em `SaveManagerApp`. Nao crie `CTkToplevel` para fluxos internos como `Gerenciar jogos`, `Criar colecao` e `Mais acoes`.
- Estado atual dos modais: `modal_layer` e filho direto da janela principal e acumula overlay, clique fora e container do modal. Nao existe `ModalRoot` separado com `overlay_dim` e `modal_slot`.
- `Mais acoes` e `Criar colecao` criam paineis temporarios com `_create_internal_modal_panel(...)`.
- `Gerenciar jogos` e pre-construido na inicializacao da UI principal por `_prebuild_game_manager_modal()` e deve ser apenas revelado/escondido. Nao destrua esse widget ao fechar.
- `Gerenciar jogos` possui fundo esmaecido especial com captura da janela via `ImageGrab`/`Canvas`; os demais modais nao usam exatamente o mesmo mecanismo visual.
- A animacao global ativa e apenas de abertura, por `app_ui.widgets.animate_modal_open(...)`; nao ha animacao global de fechamento ativa.
- Para novos modais internos, use `_prepare_modal_layer(...)`, `_create_internal_modal_panel(...)` e `_hide_modal_layer()` em vez de duplicar clique fora e Escape.
- Cards/listas de jogos usam cache persistente. Clique, selecao e favorito devem atualizar apenas o item afetado.
- Quando dados renderizados mudarem profundamente, como nome, capa/banner, caminhos ou contagem de perfis, use uma assinatura de dados e recrie somente o card afetado, nunca a tela inteira.

## Checklist antes de finalizar mudancas

1. Rode `compileall`.
2. Se mexeu em operacoes de arquivo, teste com pastas temporarias, nao com saves reais.
3. Se mexeu na UI, abra o app e confira pelo menos: janela principal, gerenciador de jogos, criacao/validacao de perfil.
4. Confira se nao criou dados locais desnecessarios em `Profiles/` ou JSONs de configuracao.
