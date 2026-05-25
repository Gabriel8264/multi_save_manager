# Desenvolvimento

## Ambiente

Projeto feito para Windows. O caminho atual observado foi:

```text
C:\Users\INFORTECH\PycharmProjects\multi save manager
```

Nota de 2026-05-22: a `.venv` foi reparada usando `C:\Users\INFORTECH\AppData\Local\Python\bin\python.exe` como Python base. O comando `python` do PATH ainda pode cair no alias do Windows/Microsoft Store; prefira `.\.venv\Scripts\python.exe`.

Nota de 2026-05-25: `main.py` tenta relancar o app com `.\.venv\Scripts\python.exe` quando detecta que foi iniciado com outro interpretador. Isso foi adicionado porque o PyCharm chegou a abrir o app sem a dependencia `tkinterdnd2`, quebrando o drag and drop da janela `Gerenciar jogos`.

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
rg "TODO|FIXME|Ã" app_ui core *.py
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

## Build

```powershell
pyinstaller ui.spec
```

Saidas:

- `dist/ui.exe`: executavel esperado.
- `build/`: arquivos intermediarios.

## Cuidados de edicao

- Salve arquivos Python como UTF-8.
- Ha texto visivel com mojibake (`Ã§`, `Ã£`, etc.). Corrigir isso e uma boa tarefa separada.
- Mantenha logica de arquivo em `core/`; a UI deve orquestrar e exibir resultado.
- Operacoes lentas ou destrutivas devem continuar usando `_run_operation`.
- Nao atualize widgets diretamente de threads secundarias.
- Nao introduza dependencias pesadas sem necessidade; o app e desktop simples.

## Drag and drop e janela Gerenciar jogos

O drag and drop de pastas do Explorer depende de `tkinterdnd2` ativo desde a janela raiz. O app usa `app_ui.dnd_support.get_dnd_ctk_base()` para escolher a base correta da `SaveManagerApp` e `enable_tkdnd(...)` para criar o contexto.

Cuidados importantes:

- Se o cursor mostrar icone de bloqueio, primeiro confirme que `.\.venv\Scripts\python.exe` consegue importar `tkinterdnd2`.
- Nao rode o app como administrador para testar DnD vindo do Explorer normal; niveis diferentes de privilegio podem bloquear drop no Windows.
- Na janela `Gerenciar jogos`, evite `grab_set`, `-topmost`, overlays globais, modalidade pesada e `focus_force()`. Esses recursos podem interferir no foco ou no DnD.
- A janela `Gerenciar jogos` deve nascer oculta, estabilizar layout/scroll/DnD e so depois aparecer. Isso evita o usuario ver a janela sendo desenhada.
- Ao registrar DnD, use o widget visivel sob o cursor e tambem seus filhos reais. CustomTkinter costuma criar widgets internos que podem interceptar o mouse.
- Callbacks de `DropEnter` e `DropPosition` precisam retornar explicitamente uma acao aceita, como `COPY`; caso contrario o Explorer pode mostrar o cursor proibido mesmo com bindings ativos.
- O botao `Selecionar pasta` deve continuar existindo como fallback robusto quando DnD nao estiver disponivel.

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
