# Desenvolvimento

## Ambiente

Projeto feito para Windows. O caminho atual observado foi:

```text
C:\Users\INFORTECH\PycharmProjects\multi save manager
```

Nota de 2026-05-22: a `.venv` foi reparada usando `C:\Users\INFORTECH\AppData\Local\Python\bin\python.exe` como Python base. O comando `python` do PATH ainda pode cair no alias do Windows/Microsoft Store; prefira `.\.venv\Scripts\python.exe`.

Nota de 2026-05-25: `main.py` tenta relancar o app com `.\.venv\Scripts\python.exe` quando detecta que foi iniciado com outro interpretador. Isso foi adicionado porque o PyCharm chegou a abrir o app sem a dependencia `tkinterdnd2`, quebrando o drag and drop do fluxo `Gerenciar jogos`.

Use PowerShell na raiz do projeto.

## Instalar dependencias

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dependencias diretas:

- `customtkinter`: interface.
- `tkinterdnd2`: arrastar e soltar opcional; fornece o modulo `tkinterdnd2`.
- `Pillow`: suporte a imagens/capas usadas pela biblioteca visual.
- `pyinstaller`: build do executavel.

Depois de instalar, confirme que o interpretador correto enxerga as dependencias:

```powershell
.\.venv\Scripts\python.exe -c "import customtkinter, tkinterdnd2, PIL; print('ok')"
```

No PyCharm, a configuracao de execucao deve usar a `.venv` do projeto. Se o PyCharm insistir em outro Python, o relancamento em `main.py` deve corrigir na abertura normal do app, mas a configuracao ideal continua sendo apontar para:

```text
.\.venv\Scripts\python.exe
```

## Rodar

```powershell
.\.venv\Scripts\python.exe main.py
```

Se nao existir `.venv`:

```powershell
python main.py
```

## Verificacoes rapidas

Compilar todos os modulos principais:

```powershell
.\.venv\Scripts\python.exe -m compileall app_ui core main.py ui.py
```

Buscar TODOs ou textos problematicos:

```powershell
rg "TODO|FIXME|mojibake" app_ui core *.py
```

Listar arquivos do repo:

```powershell
rg --files
```

## Teste manual seguro

Para testar sem mexer em saves reais:

1. Crie uma pasta temporaria fora do projeto, por exemplo `%TEMP%\msm-save-a`.
2. Coloque arquivos falsos dentro dela.
3. Cadastre um jogo de teste apontando para essa pasta.
4. Crie dois perfis.
5. Altere arquivos falsos entre um perfil e outro.
6. Carregue perfis e confirme se os arquivos foram trocados corretamente.

Evite usar a propria raiz do projeto como pasta de save. O validador bloqueia os caminhos internos principais, mas testes com pasta temporaria reduzem risco.

## Teste seguro de autenticação local

A autenticação local usa arquivos na pasta do projeto:

- `data/users.json`
- `data/session.json`
- `data/auth_migration_backups/`

Para testar criação/login sem tocar nos dados reais do projeto, rode um teste isolado em uma pasta temporária e importe o pacote do repo:

```powershell
$tmp = Join-Path $PWD ".codex_tmp\auth_test"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
```

Depois execute um script que faça `os.chdir($tmp)` antes de importar `core.local_auth`. Isso força `config.json`, `settings.json`, `game_library.json`, `data/users.json` e `data/session.json` a serem criados dentro da pasta temporária.

Cuidados:

- Não apague `data/users.json` ou `data/session.json` reais sem pedido explícito.
- Não desative `auth_enabled` manualmente para testar migração sem antes fazer backup.
- Se for testar preservação de dados antigos, simule `config.json`, `settings.json` e `game_library.json` temporários.
- A primeira ativação de autenticação deve criar backup em `data/auth_migration_backups/` e preservar jogos, favoritos, recentes, inicialização e biblioteca visual.

## Build

```powershell
pyinstaller ui.spec
```

Saidas:

- `dist/ui.exe`: executavel esperado.
- `build/`: arquivos intermediarios.

## Cuidados de edicao

- Salve arquivos Python como UTF-8.
- Historicamente alguns textos visiveis tiveram mojibake. Ao editar UI, corrija texto quebrado com cuidado e salve como UTF-8.
- Mantenha logica de arquivo em `core/`; a UI deve orquestrar e exibir resultado.
- Operacoes lentas ou destrutivas devem continuar usando `_run_operation`.
- Nao atualize widgets diretamente de threads secundarias.
- Nao introduza dependencias pesadas sem necessidade; o app e desktop simples.

## Drag and drop e modal Gerenciar jogos

O drag and drop de pastas do Explorer depende de `tkinterdnd2` ativo desde a janela raiz. O app usa `app_ui.dnd_support.get_dnd_ctk_base()` para escolher a base correta da `SaveManagerApp` e `enable_tkdnd(...)` para criar o contexto.

Cuidados importantes:

- Se o cursor mostrar icone de bloqueio, primeiro confirme que `.\.venv\Scripts\python.exe` consegue importar `tkinterdnd2`.
- Nao rode o app como administrador para testar DnD vindo do Explorer normal; niveis diferentes de privilegio podem bloquear drop no Windows.
- `Gerenciar jogos` nao deve abrir como `CTkToplevel`; ele e um modal interno (`CTkFrame`) dentro de um overlay criado em `SaveManagerApp`.
- O overlay escuro deve fechar ao clicar fora do painel, e o painel interno deve consumir o clique para nao fechar por engano.
- Evite `grab_set`, `-topmost`, modalidade pesada e `focus_force()` nesse fluxo. Eles podem interferir no foco ou no DnD.
- Ao registrar DnD, use o widget visivel sob o cursor e tambem seus filhos reais. CustomTkinter costuma criar widgets internos que podem interceptar o mouse.
- Callbacks de `DropEnter` e `DropPosition` precisam retornar explicitamente uma acao aceita, como `COPY`; caso contrario o Explorer pode mostrar o cursor proibido mesmo com bindings ativos.
- O botao `Selecionar pasta` deve continuar existindo como fallback robusto quando DnD nao estiver disponivel.

## Autosave do Gerenciar jogos

O fluxo `Gerenciar jogos` nao possui mais botao `Salvar alteracoes`. O salvamento acontece pelo proprio painel:

- nome do jogo e argumentos: debounce curto, perda de foco ou Enter;
- arquivo de inicializacao e remocao do arquivo: imediato;
- alternar `Executar como administrador`: imediato;
- adicionar diretorio por seletor ou drag and drop: imediato;
- editar diretorios manualmente: debounce curto, perda de foco ou fechamento do modal.

Ao alterar esse fluxo:

- nao salve a cada tecla sem debounce;
- nao recrie o painel inteiro apos cada autosave;
- nao considere uma assinatura como salva se o callback de erro retornar falha;
- mantenha o layout estavel: caminhos longos devem ser truncados/limitados visualmente, sem expandir o modal.

## Navegacao, modais e refresh visual

A UI principal prioriza navegacao estavel e sem piscadas. Containers estruturais devem ser criados uma vez e mantidos em memoria.

Ao alterar navegacao:

- nao destrua/recrie paginas principais para trocar de tela;
- use a estrutura persistente de `SaveManagerApp.pages`;
- troque tela com `tkraise()` e atualize dados pontuais;
- mantenha `Home`, `Colecoes`, contexto do jogo, `Mods` e `Config` como frames persistentes.

Ao criar ou alterar modal interno:

- use `SaveManagerApp._prepare_modal_layer(...)` para abrir a camada;
- use `SaveManagerApp._create_internal_modal_panel(...)` para criar o painel visual;
- use `SaveManagerApp._hide_modal_layer()` para fechar/limpar;
- nao duplique manualmente overlay, clique fora ou Escape;
- evite `CTkToplevel` para fluxos internos do launcher.
- consulte `docs/MODALS.md` antes de mexer em overlay, animacao ou z-order.

Modais que usam essa camada atualmente:

- `Gerenciar jogos`;
- `Criar colecao`;
- `Mais acoes`.

Estado atual da infraestrutura:

- existe um `modal_layer` unico, filho direto da janela principal;
- nao existe `ModalRoot` separado com `overlay_dim` e `modal_slot`;
- `Mais acoes` e `Criar colecao` criam paineis temporarios dentro de `modal_layer`;
- `Gerenciar jogos` e pre-construido por `_prebuild_game_manager_modal()` quando a UI principal nasce;
- ao fechar `Gerenciar jogos`, autosalve pendencias e esconda o painel com `place_forget()`/`_hide_modal_layer()`, mas nao destrua o widget;
- a animacao generica ativa e apenas de abertura, por `app_ui.widgets.animate_modal_open(...)`;
- nao ha animacao global de fechamento ativa.

O fundo esmaecido de `Gerenciar jogos` e especial: ele usa captura da janela com `ImageGrab` e desenho em `Canvas`. Nao assuma que os demais modais usam o mesmo mecanismo visual.

Ao atualizar listas/cards de jogos:

- nao reconstrua a lista inteira por clique, selecao ou favorito;
- atualize apenas o card anterior e o novo quando for selecao;
- atualize apenas estrela/estado quando for favorito;
- use assinatura de dados para detectar mudancas profundas;
- recrie somente o card afetado quando mudarem nome, capa/banner, caminhos ou contagem de perfis.

## Dados locais e limpeza

Arquivos/pastas normalmente nao devem entrar em commit:

- `.venv/`
- `.idea/`
- `__pycache__/`
- `build/`
- `dist/`
- `Profiles/`
- `config.json`
- `settings.json`
- `profile_state.json`

Se for preciso compartilhar uma configuracao de exemplo, crie um arquivo separado, como `config.example.json`.
