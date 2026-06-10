# Multiple Save Manager

Aplicativo desktop em Python para gerenciar multiplos perfis de save por jogo. Ele cadastra um ou mais diretorios de save para cada jogo, cria backups por perfil e permite alternar entre perfis com avisos antes de sobrescrever arquivos.

## Como executar

No Windows, a partir da raiz do projeto:

```powershell
.\.venv\Scripts\python.exe main.py
```

Alternativa, se o ambiente virtual nao estiver disponivel:

```powershell
python main.py
```

## Dependencias

As dependencias diretas conhecidas ficam em `requirements.txt`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`tkinter` vem com a maioria das instalacoes Python no Windows. O recurso de arrastar e soltar importa o modulo `tkinterdnd2`; se ele falhar, o app continua abrindo sem drag and drop.

Verificacao rapida do ambiente:

```powershell
.\.venv\Scripts\python.exe -c "import customtkinter, tkinterdnd2, PIL; print('ok')"
```

No PyCharm, use o interpretador `.\.venv\Scripts\python.exe`. Usar outro Python pode abrir o app sem `tkinterdnd2` e fazer o arrastar pastas mostrar o cursor proibido do Windows.

## Como usar

1. Abra o app.
2. Na primeira execução, crie o primeiro usuário local.
3. Nas próximas execuções, se a sessão ainda estiver ativa, o app entra direto no último usuário.
4. Clique em `Gerenciar jogos`.
5. Cadastre o nome do jogo e uma pasta de save por linha.
6. As alteracoes do cadastro de jogos sao salvas automaticamente; nao existe mais botao `Salvar alteracoes` nesse fluxo.
7. Crie um perfil para capturar o save atual.
8. Clique em outro perfil para carregar aquele conjunto de saves.
9. Use `Salvar agora` para atualizar o backup do perfil ativo com o estado atual do jogo.

## Dados locais

O app grava dados na propria pasta do projeto:

- `config.json`: modo do app, usuario local padrao, jogos cadastrados e suas pastas de save.
- `settings.json`: tema e favoritos.
- `profile_state.json`: perfil ativo por jogo.
- `game_library.json`: metadados visuais opcionais, como capa/banner por jogo.
- `Profiles/`: backups dos saves, organizados por perfil e jogo.
- `data/users.json`: usuários locais, com senha em hash PBKDF2 + salt.
- `data/session.json`: sessão local ativa; quando o usuário sai, ela é limpa.
- `data/auth_migration_backups/`: backup de metadados criado antes de ativar autenticação local pela primeira vez.
- `data/default_user/`: estrutura futura para modo `single_user`.
- `data/users/default_user/`: estrutura futura por usuario para perfis, saves, mods e settings locais.
- `migration_backups/`: backups automaticos criados antes de migrações de modo.

Esses arquivos sao dados do usuario. Trate-os como locais e nao como codigo.

Compatibilidade: a primeira ativação do multiusuário local não move nem apaga jogos, favoritos, executáveis, argumentos, caminhos de save, biblioteca visual ou perfis existentes. O primeiro usuário usa `default_user` para preservar o fallback legado de `Profiles/`.

## Build Windows

O arquivo `ui.spec` indica um build com PyInstaller:

```powershell
pyinstaller ui.spec
```

O executavel gerado fica em `dist/`. A pasta `build/` contem artefatos intermediarios.

## Documentacao tecnica

- `AGENTS.md`: contexto curto para agentes trabalharem sem redescobrir o projeto.
- `docs/ARCHITECTURE.md`: mapa dos modulos e fluxo de dados.
- `docs/DEVELOPMENT.md`: comandos, verificacoes, dependencias e cuidados com DnD/autosave do modal `Gerenciar jogos`.
- `docs/DATA_FORMATS.md`: formatos dos arquivos JSON e layout dos perfis.
