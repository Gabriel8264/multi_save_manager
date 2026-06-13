# Infraestrutura de modais

Este documento descreve o estado atual dos modais internos do Universal Gamer.

## Visao geral

A UI principal usa uma camada unica chamada `modal_layer`, criada em `SaveManagerApp._build_modal_layer()` dentro de `app_ui/app.py`.

Estrutura atual:

```text
SaveManagerApp
├─ header
├─ content
│  ├─ nav_rail
│  ├─ page_host
│  └─ paginas persistentes
└─ modal_layer
   └─ modal atual
```

Nao existe atualmente um `ModalRoot` separado com `overlay_dim` e `modal_slot`. O `modal_layer` acumula tres responsabilidades:

- cobrir a janela principal;
- receber clique fora do modal;
- conter o modal ativo.

## Abertura de modal interno

Fluxo generico:

```text
Botao ou acao da UI
↓
funcao especifica do modal
↓
_prepare_modal_layer(close_callback)
↓
_create_internal_modal_panel(...)
↓
montagem dos widgets dentro do painel
↓
_animate_internal_modal_open(modal)
↓
animate_modal_open(...) em app_ui/widgets.py
↓
modal exibido
```

Funcoes principais:

- `SaveManagerApp._prepare_modal_layer(close_callback)`
- `SaveManagerApp._create_internal_modal_panel(...)`
- `SaveManagerApp._animate_internal_modal_open(...)`
- `app_ui.widgets.animate_modal_open(...)`

Ordem de camada:

1. `_prepare_modal_layer()` limpa o conteudo anterior.
2. Registra `_active_modal_close_callback`.
3. Configura `modal_layer` com a cor de overlay.
4. Posiciona `modal_layer` com `place(x=0, y=0, relwidth=1, relheight=1)`.
5. Aplica `modal_layer.lift()`.
6. Cria o painel como filho direto de `modal_layer`.
7. O painel consome clique interno com `bind("<Button-1>", lambda _event: "break")`.
8. A abertura usa `animate_modal_open(...)`.

## Fechamento

Clique fora:

```text
modal_layer recebe <Button-1>
↓
_handle_modal_background_click(...)
↓
_active_modal_close_callback()
↓
funcao especifica de fechamento
↓
_hide_modal_layer()
```

Tecla Esc:

```text
SaveManagerApp recebe <Escape>
↓
_handle_modal_escape(...)
↓
_active_modal_close_callback()
↓
funcao especifica de fechamento
↓
_hide_modal_layer()
```

Fechamento programatico depende do modal:

- `Mais acoes`: destroi `more_actions_modal` e chama `_hide_modal_layer()`.
- `Criar colecao`: destroi `create_collection_modal` e chama `_hide_modal_layer()`.
- `Gerenciar jogos`: autosalva, esconde `game_manager_wrapper` com `place_forget()` e chama `_hide_modal_layer()`.

## Animacao atual

Existe apenas animacao de abertura generica.

Arquivo: `app_ui/widgets.py`

Funcao: `animate_modal_open(...)`

Caracteristicas:

- duracao padrao: `150ms`;
- frames: `7`;
- usa `after(...)`;
- usa `place(...)` para deslocamento vertical leve;
- usa `lift()` durante os frames;
- nao escala widgets reais.

Nao existe animacao global de fechamento ativa no estado atual.

## Modais que usam `modal_layer`

### Mais acoes

Funcao de abertura: `SaveManagerApp._open_more_actions_modal()`

Cria um painel temporario com `_create_internal_modal_panel(...)`.

Fechamento: `SaveManagerApp._close_more_actions_modal()`.

### Criar colecao

Funcao de abertura: `SaveManagerApp._show_create_collection_modal()`

Cria um painel temporario com `_create_internal_modal_panel(...)`.

Fechamento: `SaveManagerApp._close_create_collection_modal()`.

### Gerenciar jogos

Funcoes principais:

- `_prebuild_game_manager_modal()`
- `_open_game_manager()`
- `_reveal_game_manager_modal()`
- `_close_game_manager_modal()`

Esse fluxo e especial:

- o painel e pre-construido quando a UI principal nasce;
- o widget persistente e `game_manager_wrapper`;
- `GameManagerWindow` e filho de `game_manager_wrapper`;
- o fechamento nao destroi o painel, apenas usa `place_forget()`;
- o cadastro usa autosave.

`Gerenciar jogos` tambem cria um fundo esmaecido proprio:

- `_build_game_manager_dim_background()`
- `_draw_game_manager_panel_background()`
- `_handle_game_manager_overlay_click(...)`

Esse fundo usa `ImageGrab`, `ImageEnhance` e `ImageTk` para capturar e escurecer a janela principal. Em seguida, desenha um canvas dentro do `modal_layer`.

## Janelas fora dessa infraestrutura

`app_ui/dialogs.py` define `PromptDialog`, que usa `CTkToplevel`. Ele nao passa por `modal_layer`.

Tambem existem dialogs nativos do Tk/Windows:

- `filedialog`;
- `messagebox`.

## Pontos de risco

- `modal_layer` acumula overlay e container; isso torna z-order mais sensivel.
- `_clear_modal_layer_content()` destroi filhos nao persistentes de `modal_layer`.
- `Gerenciar jogos` depende de `_persistent_modal_widgets` para nao ser destruido.
- `animate_modal_open(...)` usa `after(...)` e pode interagir mal com widgets destruidos antes do fim.
- `Gerenciar jogos` usa `after_idle(...)` para revelar o painel.
- O fundo esmaecido e global apenas para `Gerenciar jogos`; outros modais usam `modal_layer` como fundo escuro simples.
- `PromptDialog` usa `wait_window()` e `focus_force()` no retorno.

## Regras para mudancas futuras

- Nao introduzir animacao de fechamento sem uma flag global de fechamento.
- Nao destruir widgets antes do callback final de qualquer animacao.
- Nao misturar `CTkFrame` opaco como overlay esperando transparencia real.
- Se criar `ModalRoot` novo, migrar todos os modais juntos ou manter compatibilidade clara.
- Nao usar `CTkToplevel` para fluxos internos como `Gerenciar jogos`.
- Sempre rodar `compileall` apos mexer nessa area.
