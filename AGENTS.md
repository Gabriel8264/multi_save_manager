# Guia Para Agentes

Este projeto e um app desktop Python/Tkinter para gerenciar saves de jogos. Leia este arquivo antes de explorar o repo: ele existe para reduzir uso de contexto e evitar trabalho repetido.

## Resumo rapido

- Entrada principal: `main.py`, que chama `app_ui.run_app()`.
- Compatibilidade legada: `ui.py` exporta `SaveManagerApp` e tambem roda o app.
- UI: pacote `app_ui/`, com CustomTkinter.
- Regras de negocio e arquivos: pacote `core/`.
- Biblioteca/orquestracao de jogos: `core/game_manager.py`.
- Modo/usuario local sem login: `core/user_manager.py`, alimentado por `app_mode`, `auth_enabled`, `manager_mode_enabled`, `current_user_id`, `users` e `permission_profiles` em `config.json`.
- Caminhos internos por usuario: `core/storage_manager.py`; `default_user` preserva `Profiles/` quando existir.
- Migração futura entre `single_user` e `multi_user`: `core/mode_migration.py`. As funções sempre fazem backup em `migration_backups/` antes de alterar modo.
- Janela de cadastro de jogos: `app_ui/game_manager_window.py`; `app_ui/game_manager.py` e apenas um shim de compatibilidade.
- Dados locais do usuario: `config.json`, `settings.json`, `profile_state.json`, `Profiles/`.
- Metadados visuais opcionais da biblioteca: `game_library.json`.
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
- Nao mova `Profiles/` para `data/users/default_user/profiles` automaticamente sem pedido explicito; o fallback atual preserva os perfis existentes.
- O app manipula pastas de save reais do usuario. Prefira testar com diretorios temporarios.
- `core.validators.ensure_safe_save_directory` impede que uma pasta de save aponte para arquivos internos do app.
- Existem textos com mojibake, por exemplo `configuraÃ§Ã£o`; provavelmente arquivos foram salvos/lidos com codificacao errada em algum momento. Ao editar UI, corrija texto visivel com cuidado e salve como UTF-8.
- `tkinterdnd2` e opcional: se falhar, `app_ui.dnd_support.enable_tkdnd` retorna `None` e a UI desativa drag and drop.
- Drag and drop no Windows depende do processo estar no mesmo nivel de privilegio do Explorer. Se o app rodar como administrador e o Explorer nao, o cursor pode mostrar bloqueio mesmo com `tkinterdnd2` correto.
- A janela `Gerenciar jogos` e sensivel a foco/DnD. Evite `grab_set`, `WindowStaysOnTopHint`, `-topmost`, overlay/modal global ou `focus_force()` nela. A janela deve abrir como `CTkToplevel` normal, nascer oculta, estabilizar layout/DnD e so entao aparecer.
- Ao mexer no DnD, registre o widget visivel e filhos reais que ficam sob o cursor. Os callbacks de `DropEnter` e `DropPosition` precisam retornar acao aceita (`COPY`/copy); apenas executar logica interna nao basta para o Explorer aceitar o drop.
- `os.startfile` em `PathListEditor` e especifico de Windows.

## Onde alterar o que

- Nova regra de validacao: `core/validators.py`.
- Mudanca no formato de config de jogos: `core/config_manager.py`.
- Mudancas futuras de modo `single_user`/`multi_user` ou usuario local: `core/user_manager.py` e defaults de `core/config_manager.py`.
- Mudancas futuras de armazenamento multiusuario: `core/storage_manager.py`.
- Mudancas futuras de troca de modo ou migração de dados: `core/mode_migration.py`.
- Operacoes de biblioteca de jogos, favoritos e manutencao ao renomear/excluir jogo: `core/game_manager.py`.
- Mudanca em favoritos/tema: `core/settings_manager.py`.
- Troca, backup, exclusao ou exportacao de saves: `core/save_manager.py`.
- Avisos antes de trocar saves: `core/runtime_checks.py`.
- Layout principal: `app_ui/app.py`.
- Janela de cadastro de jogos: `app_ui/game_manager_window.py`.
- Componentes reutilizaveis: `app_ui/widgets.py`.
- Paleta/tema: `app_ui/theme.py`.

## Checklist antes de finalizar mudancas

1. Rode `compileall`.
2. Se mexeu em operacoes de arquivo, teste com pastas temporarias, nao com saves reais.
3. Se mexeu na UI, abra o app e confira pelo menos: janela principal, gerenciador de jogos, criacao/validacao de perfil.
4. Confira se nao criou dados locais desnecessarios em `Profiles/` ou JSONs de configuracao.
