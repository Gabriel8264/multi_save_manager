import threading
import os
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

from app_ui.dialogs import PromptDialog
from app_ui.dnd_support import enable_tkdnd, get_dnd_ctk_base
from app_ui.game_manager_window import GameManagerWindow
from app_ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    APP_BACKGROUND,
    BORDER_COLOR,
    ERROR_COLOR,
    SIDEBAR_COLOR,
    SUCCESS_COLOR,
    SURFACE_PRIMARY,
    SURFACE_SECONDARY,
    SURFACE_TERTIARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
    apply_theme,
)
from app_ui.widgets import BusyOverlay, GameLibraryCard, GameLibraryListItem, ProfileCard
from core.config_manager import obter_diretorios_jogo
from core.game_manager import (
    alternar_favorito_jogo,
    excluir_jogo_com_dados,
    jogo_eh_favorito,
    listar_jogos_biblioteca,
    listar_jogos_recentes_biblioteca,
    listar_nomes_jogos,
    salvar_jogo,
)
from core.runtime_checks import (
    coletar_alertas_pre_troca,
    contar_arquivos_em_diretorios,
)
from core.save_manager import (
    aplicar_perfil,
    criar_perfil,
    excluir_perfil,
    exportar_saves_do_jogo,
    fazer_backup,
    limpar_saves_do_jogo,
    listar_perfis,
    obter_perfil_ativo,
    renomear_perfil,
)
from core.settings_manager import (
    definir_tema,
    obter_tema,
    registrar_recente,
)
from core.validators import validate_profile_name


class SaveManagerApp(get_dnd_ctk_base()):
    def __init__(self):
        apply_theme(obter_tema())
        super().__init__()

        self.title("Multiple Save Manager")
        self.geometry("1280x780")
        self.minsize(1000, 680)
        self.configure(fg_color=APP_BACKGROUND)

        self.busy = False
        self.selected_profile = None
        self.current_game = ""
        self.sidebar_selected_game = ""
        self.collection_selected_game = ""
        self.current_page = "home"
        self.game_tool_mode = "overview"
        self.game_manager = None
        self._game_manager_open_after = None
        self._game_manager_initial_game = None
        self._compact_layout = False
        self._compact_header = False
        self._compact_game_controls = False
        self._library_grid_columns = 0
        self._library_grid_refresh_after = None
        self.library_cards = {}
        self.home_library_cards = {}
        self.library_filter = "all"
        self.collection_cards = {}
        self.collection_filter = "all"
        self._collection_grid_columns = 0
        self.library_mode = "collection"
        self._page_built = {}

        self.dnd_context = enable_tkdnd(self)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_content()
        self.busy_overlay = BusyOverlay(self)

        self._load_games(initial=True)
        self._refresh_theme_switch()
        self.bind("<Configure>", self._on_resize)
        self.after(0, self._maximize_on_startup)

    def _build_header(self):
        self.header = ctk.CTkFrame(
            self,
            fg_color=APP_BACKGROUND,
            corner_radius=0,
        )
        self.header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=0)
        self.header.grid_columnconfigure(2, weight=0)

        title_block = ctk.CTkFrame(self.header, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w", padx=(0, 14), pady=2)

        self.title_label = ctk.CTkLabel(
            title_block,
            text="Universal Gamer",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            title_block,
            text="Launcher de saves e biblioteca",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w")
        self.subtitle_label.configure(text="Launcher de saves e biblioteca")

        self.settings_button = ctk.CTkButton(
            self.header,
            text="Config",
            width=74,
            height=32,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.settings_button.grid(row=0, column=1, sticky="e", padx=6, pady=4)

        self.theme_switch = ctk.CTkSwitch(
            self.header,
            text="Dark",
            command=self._toggle_theme,
            text_color=TEXT_PRIMARY,
        )
        self.theme_switch.grid(row=0, column=2, sticky="e", padx=(6, 0), pady=4)

    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(6, 14))
        self.content.grid_columnconfigure(0, weight=0)
        self.content.grid_columnconfigure(1, weight=4)
        self.content.grid_columnconfigure(2, weight=3)
        self.content.grid_rowconfigure(0, weight=1)

        self.nav_rail = ctk.CTkFrame(
            self.content,
            fg_color=SIDEBAR_COLOR,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
            width=200,
        )
        self.nav_rail.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.nav_rail.grid_propagate(False)
        self.nav_rail.grid_columnconfigure(0, weight=1)
        self.nav_rail.grid_rowconfigure(5, weight=1)
        self._build_navigation()

        self.left_panel = ctk.CTkFrame(
            self.content,
            fg_color=SURFACE_PRIMARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.left_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(0, weight=2)
        self.left_panel.grid_rowconfigure(3, weight=1)

        self.sidebar = ctk.CTkFrame(
            self.content,
            fg_color=SURFACE_PRIMARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.sidebar.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        self.page_host = ctk.CTkFrame(self.content, fg_color="transparent")
        self.page_host.grid(row=0, column=1, columnspan=2, sticky="nsew")
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.left_panel.grid_forget()
        self.sidebar.grid_forget()

        self._build_pages()

    def _build_navigation(self):
        nav_items = [
            ("home", "Home"),
            ("library", "Biblioteca"),
            ("saves", "Saves"),
            ("mods", "Mods"),
            ("settings", "Config"),
        ]
        self.nav_buttons = {}
        for index, (page_name, label) in enumerate(nav_items):
            active = page_name == self.current_page
            button = ctk.CTkButton(
                self.nav_rail,
                text=label,
                height=32,
                fg_color=ACCENT_COLOR if active else SURFACE_SECONDARY,
                hover_color=SURFACE_TERTIARY,
                text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                border_width=1,
                border_color=ACCENT_COLOR if active else SURFACE_SECONDARY,
                command=lambda page=page_name: self._navigate(page),
            )
            button.grid(row=index, column=0, sticky="ew", padx=8, pady=(10 if index == 0 else 4, 0))
            self.nav_buttons[page_name] = button

    def _build_pages(self):
        self.pages = {}
        for page_name in ("home", "library", "game"):
            page = ctk.CTkFrame(self.page_host, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(0, weight=1)
            self.pages[page_name] = page

        self._build_home_page()
        self._build_library_page()
        self._build_game_page()
        self._show_page("home")

    def _navigate(self, page_name):
        if page_name == "saves":
            if not self.current_game:
                self._set_status("Abra um jogo antes de acessar os saves.", "info")
                page_name = "library"
            else:
                self.game_tool_mode = "saves"
                page_name = "game"

        if page_name in {"mods", "settings"}:
            self._set_status(f"Página '{page_name}' preparada para uma etapa futura.", "info")
            return

        if page_name == "game" and not self.current_game:
            self._set_status("Selecione um jogo na biblioteca primeiro.", "info")
            page_name = "library"

        self._show_page(page_name)
        if page_name == "library" and hasattr(self, "library_game_page"):
            self._show_library_collection()

    def _show_page(self, page_name):
        self.current_page = page_name
        for name, button in getattr(self, "nav_buttons", {}).items():
            active = name == page_name or (
                page_name == "game"
                and self.game_tool_mode == "saves"
                and name == "saves"
            )
            button.configure(
                fg_color=ACCENT_COLOR if active else SURFACE_SECONDARY,
                text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                border_width=1,
                border_color=ACCENT_COLOR if active else SURFACE_SECONDARY,
            )

        self.pages[page_name].tkraise()
        if page_name == "game":
            self._sync_game_page_mode()
        self._sync_sidebar_context_highlight()
        self._sync_library_navigation_area(page_name)
        if page_name == "home":
            self._refresh_home_shelves()

    def _sync_sidebar_context_highlight(self):
        target_game = self.current_game if self.current_page == "game" else ""
        self._set_sidebar_selected_game(target_game)

    def _sync_library_navigation_area(self, page_name):
        if not hasattr(self, "library_list_panel"):
            return

        self.nav_rail.configure(width=200)
        self.library_list_panel.grid()

    def _build_home_page(self):
        if self._page_built.get("home"):
            return

        page = self.pages["home"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        hero = ctk.CTkFrame(page, fg_color=SURFACE_PRIMARY, corner_radius=14, border_width=1, border_color=BORDER_COLOR)
        hero.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        hero.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hero,
            text="Continuar jogando",
            font=("Segoe UI Bold", 28),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))

        self.home_current_game = ctk.CTkLabel(
            hero,
            text="Escolha um jogo na biblioteca para preparar seus saves.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.home_current_game.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        shelf = ctk.CTkFrame(page, fg_color=SURFACE_PRIMARY, corner_radius=14, border_width=1, border_color=BORDER_COLOR)
        shelf.grid(row=1, column=0, sticky="nsew")
        shelf.grid_columnconfigure(0, weight=1)
        shelf.grid_rowconfigure(1, weight=1)
        shelf.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            shelf,
            text="Favoritos",
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        self.home_favorites_frame = ctk.CTkScrollableFrame(
            shelf,
            orientation="horizontal",
            height=148,
            fg_color=SURFACE_SECONDARY,
            corner_radius=12,
            border_width=0,
        )
        self.home_favorites_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            shelf,
            text="Recentes",
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))
        self.home_recents_frame = ctk.CTkScrollableFrame(
            shelf,
            orientation="horizontal",
            height=148,
            fg_color=SURFACE_SECONDARY,
            corner_radius=12,
            border_width=0,
        )
        self.home_recents_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        self._page_built["home"] = True

    def _build_library_page(self):
        if self._page_built.get("library"):
            return

        page = self.pages["library"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        self.game_card = ctk.CTkFrame(
            page,
            fg_color=APP_BACKGROUND,
            corner_radius=0,
            border_width=0,
            border_color=APP_BACKGROUND,
        )
        self.game_card.grid(row=0, column=0, sticky="nsew")
        self.game_card.grid_columnconfigure(0, weight=1)
        self.game_card.grid_rowconfigure(0, weight=1)

        self.library_list_panel = ctk.CTkFrame(self.nav_rail, fg_color="transparent")
        self.library_list_panel.grid(row=5, column=0, sticky="nsew", padx=6, pady=(10, 6))
        self.library_list_panel.grid_columnconfigure(0, weight=1)
        self.library_list_panel.grid_rowconfigure(2, weight=1)

        self.library_top = ctk.CTkFrame(self.library_list_panel, fg_color="transparent")
        self.library_top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.library_top.grid_columnconfigure(0, weight=1)
        self.library_top.grid_columnconfigure(1, weight=0)
        self.library_top.grid_columnconfigure(2, weight=0)

        title_block = ctk.CTkFrame(self.library_top, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        title_block.grid_columnconfigure(0, weight=1)

        self.library_title = ctk.CTkLabel(
            title_block,
            text="Jogos",
            font=("Segoe UI Bold", 13),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.library_title.grid(row=0, column=0, sticky="ew")

        self.library_meta = ctk.CTkLabel(
            title_block,
            text="Acesso rápido",
            font=("Segoe UI", 9),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.library_meta.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.library_filter_frame = ctk.CTkFrame(self.library_top, fg_color="transparent")
        self.library_filter_frame.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.library_filter_frame.grid_columnconfigure(0, weight=0)
        self.library_filter_frame.grid_columnconfigure(1, weight=0)

        self.library_all_filter_button = ctk.CTkButton(
            self.library_filter_frame,
            text="Todos",
            width=54,
            height=24,
            command=lambda: self._set_library_filter("all"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.library_all_filter_button.grid(row=0, column=0, sticky="e")

        self.library_favorites_filter_button = ctk.CTkButton(
            self.library_filter_frame,
            text="Favoritos",
            width=68,
            height=24,
            command=lambda: self._set_library_filter("favorites"),
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.library_favorites_filter_button.grid(row=0, column=1, sticky="e", padx=(4, 0))

        self.favorite_button = ctk.CTkButton(
            self.library_top,
            text="[ ]",
            width=44,
            height=30,
            command=self._toggle_favorite_game,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )

        self.manage_games_button = ctk.CTkButton(
            self.library_top,
            text="Gerenciar jogos",
            width=138,
            height=30,
            command=self._open_game_manager,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )

        self.library_search = ctk.CTkEntry(
            self.library_list_panel,
            placeholder_text="Buscar jogo...",
            height=30,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.library_search.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.library_search.bind("<KeyRelease>", lambda _event: self._refresh_game_selector())

        self.game_library_frame = ctk.CTkScrollableFrame(
            self.library_list_panel,
            fg_color="transparent",
            corner_radius=10,
            border_width=0,
        )
        self.game_library_frame.grid(row=2, column=0, sticky="nsew")
        self.game_library_frame.grid_columnconfigure(0, weight=1)
        self.game_library_frame.bind("<Configure>", self._on_library_grid_resize)

        self.game_paths_label = ctk.CTkLabel(self.game_card, text="")
        self.game_selector = None
        self._build_library_game_context()
        self._page_built["library"] = True

    def _build_library_game_context(self):
        self.library_game_page = ctk.CTkFrame(
            self.game_card,
            fg_color=APP_BACKGROUND,
            corner_radius=0,
            border_width=0,
        )
        self.library_game_page.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.library_game_page.grid_columnconfigure(0, weight=1)
        self.library_game_page.grid_rowconfigure(1, weight=1)

        collection_top = ctk.CTkFrame(self.library_game_page, fg_color="transparent")
        collection_top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        collection_top.grid_columnconfigure(0, weight=1)

        title_stack = ctk.CTkFrame(collection_top, fg_color="transparent")
        title_stack.grid(row=0, column=0, sticky="ew", padx=(2, 12))
        title_stack.grid_columnconfigure(0, weight=1)

        self.library_game_context_label = ctk.CTkLabel(
            title_stack,
            text="Biblioteca",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.library_game_context_label.grid(row=0, column=0, sticky="ew")

        self.collection_meta_label = ctk.CTkLabel(
            title_stack,
            text="Coleção completa",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.collection_meta_label.grid(row=1, column=0, sticky="ew", pady=(1, 0))

        self.collection_search = ctk.CTkEntry(
            collection_top,
            placeholder_text="Buscar na coleção...",
            width=230,
            height=32,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.collection_search.grid(row=0, column=1, rowspan=2, sticky="e", padx=(0, 8))
        self.collection_search.bind("<KeyRelease>", lambda _event: self._refresh_collection_grid())

        self.collection_filter_frame = ctk.CTkFrame(collection_top, fg_color="transparent")
        self.collection_filter_frame.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 8))

        self.collection_all_filter_button = ctk.CTkButton(
            self.collection_filter_frame,
            text="Todos",
            width=62,
            height=30,
            command=lambda: self._set_collection_filter("all"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.collection_all_filter_button.grid(row=0, column=0, sticky="e")

        self.collection_favorites_filter_button = ctk.CTkButton(
            self.collection_filter_frame,
            text="Favoritos",
            width=84,
            height=30,
            command=lambda: self._set_collection_filter("favorites"),
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.collection_favorites_filter_button.grid(row=0, column=1, sticky="e", padx=(5, 0))

        self.collection_grid_frame = ctk.CTkScrollableFrame(
            self.library_game_page,
            fg_color=APP_BACKGROUND,
            corner_radius=0,
            border_width=0,
        )
        self.collection_grid_frame.grid(row=1, column=0, sticky="nsew")
        self.collection_grid_frame.bind("<Configure>", self._on_collection_grid_resize)
        self._refresh_collection_grid()

    def _build_library_stat_card(self, master, row, column, title, value):
        card = ctk.CTkFrame(
            master,
            fg_color="transparent",
            corner_radius=10,
            border_width=0,
        )
        card.grid(row=row, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 1))
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=("Segoe UI Semibold", 13),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        value_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        return value_label

    def _build_game_page(self):
        if self._page_built.get("game"):
            return

        page = self.pages["game"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(page, fg_color=SURFACE_PRIMARY, corner_radius=18, border_width=1, border_color=BORDER_COLOR)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_rowconfigure(4, weight=1)

        self._build_game_hub()
        self._build_game_overview()
        self._build_profile_area()
        self._page_built["game"] = True

    def _build_game_hub(self):
        self.selected_card = ctk.CTkFrame(
            self.left_panel,
            fg_color=SURFACE_SECONDARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.selected_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 14))
        self.selected_card.grid_columnconfigure(0, weight=2)
        self.selected_card.grid_columnconfigure(1, weight=1)
        self.selected_card.grid_columnconfigure(2, weight=0)
        self.selected_card.grid_columnconfigure(3, weight=0)
        self.selected_card.grid_columnconfigure(4, weight=0)
        self.selected_card.grid_columnconfigure(5, weight=0)

        self.game_panel_title = ctk.CTkLabel(
            self.selected_card,
            text="Nenhum jogo",
            font=("Segoe UI Bold", 24),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.game_panel_title.grid(row=0, column=0, sticky="ew", padx=(16, 10), pady=(12, 2))

        self.selected_value = ctk.CTkLabel(
            self.selected_card,
            text="Perfil: nenhum",
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.selected_value.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 12))

        self.selected_hint = ctk.CTkLabel(
            self.selected_card,
            text="",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.selected_hint.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 12))

        self.play_button = ctk.CTkButton(
            self.selected_card,
            text="Jogar",
            command=self._play_current_game_placeholder,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.play_button.grid(row=0, column=2, rowspan=2, sticky="ew", padx=5, pady=12)

        self.quick_save_button = ctk.CTkButton(
            self.selected_card,
            text="Saves",
            command=self._show_game_saves,
            height=34,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.quick_save_button.grid(row=0, column=3, rowspan=2, sticky="ew", padx=5, pady=12)

        self.load_profile_button = ctk.CTkButton(
            self.selected_card,
            text="Abrir pastas",
            command=self._open_current_game_paths,
            height=34,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.load_profile_button.grid(row=0, column=4, rowspan=2, sticky="ew", padx=5, pady=12)

        self.more_actions_button = ctk.CTkButton(
            self.selected_card,
            text="Gerenciar jogo",
            command=self._open_current_game_in_manager,
            height=34,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.more_actions_button.grid(row=0, column=5, rowspan=2, sticky="ew", padx=(5, 14), pady=12)

        self.game_banner_label = ctk.CTkLabel(self.left_panel, text="")
        self.game_panel_meta = ctk.CTkLabel(self.left_panel, text="")
        self.status_message = ctk.CTkLabel(self.left_panel, text="")
        self.progress_bar = ctk.CTkProgressBar(self.left_panel)
        self.progress_bar.set(0)

    def _build_game_overview(self):
        self.game_overview = ctk.CTkFrame(
            self.left_panel,
            fg_color=SURFACE_SECONDARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.game_overview.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.game_overview.grid_columnconfigure(0, weight=1)
        self.game_overview.grid_columnconfigure(1, weight=1)

        self.game_context_title = ctk.CTkLabel(
            self.game_overview,
            text="Contexto do jogo",
            font=("Segoe UI Bold", 20),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.game_context_title.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 6))

        self.game_context_summary = ctk.CTkLabel(
            self.game_overview,
            text="Abra um jogo pela Coleção ou pela lista rápida para ver ações e ferramentas.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=760,
        )
        self.game_context_summary.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 14))

        self.game_context_status = self._build_game_context_tile(
            self.game_overview,
            2,
            0,
            "Status",
            "Nenhum jogo aberto.",
        )
        self.game_context_saves = self._build_game_context_tile(
            self.game_overview,
            2,
            1,
            "Saves",
            "Perfis e backups ficam em uma seção própria.",
        )
        self.game_context_tools = self._build_game_context_tile(
            self.game_overview,
            3,
            0,
            "Ferramentas",
            "Mods, backups, diretórios e opções de execução entram aqui futuramente.",
        )
        self.game_context_paths = self._build_game_context_tile(
            self.game_overview,
            3,
            1,
            "Diretórios",
            "Pastas de save vinculadas ao jogo.",
        )

    def _build_game_context_tile(self, master, row, column, title, value):
        tile = ctk.CTkFrame(
            master,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        tile.grid(row=row, column=column, sticky="nsew", padx=(18 if column == 0 else 8, 18 if column == 1 else 8), pady=(0, 12))
        tile.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tile,
            text=title,
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        value_label = ctk.CTkLabel(
            tile,
            text=value,
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=360,
        )
        value_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        return value_label

    def _build_game_controls(self):
        self.game_card = ctk.CTkFrame(
            self.left_panel,
            fg_color=SURFACE_SECONDARY,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.game_card.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 12))
        self.game_card.grid_columnconfigure(0, weight=1)
        self.game_card.grid_columnconfigure(1, weight=1)
        self.game_card.grid_columnconfigure(2, weight=0)
        self.game_card.grid_columnconfigure(3, weight=0)

        self.game_search = ctk.CTkEntry(
            self.game_card,
            placeholder_text="Buscar jogo...",
            height=40,
            corner_radius=12,
            fg_color=SURFACE_PRIMARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.game_search.grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=(18, 12))
        self.game_search.bind("<KeyRelease>", lambda _event: self._refresh_game_selector())

        self.game_selector = ctk.CTkOptionMenu(
            self.game_card,
            values=[""],
            command=self._on_game_selected,
            height=40,
            fg_color=ACCENT_COLOR,
            button_color=ACCENT_HOVER,
            button_hover_color=ACCENT_HOVER,
        )
        self.game_selector.grid(row=0, column=1, sticky="ew", padx=8, pady=(18, 12))

        self.favorite_button = ctk.CTkButton(
            self.game_card,
            text="[ ]",
            width=46,
            command=self._toggle_favorite_game,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_SECONDARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.favorite_button.grid(row=0, column=2, padx=8, pady=(18, 12))

        self.manage_games_button = ctk.CTkButton(
            self.game_card,
            text="Gerenciar jogos",
            command=self._open_game_manager,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_SECONDARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.manage_games_button.grid(row=0, column=3, padx=(8, 18), pady=(18, 12))

        self.library_title = ctk.CTkLabel(
            self.game_card,
            text="Biblioteca",
            font=("Segoe UI Semibold", 15),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.library_title.grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 8))

        self.library_meta = ctk.CTkLabel(
            self.game_card,
            text="Selecione um jogo para gerenciar seus saves.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="e",
        )
        self.library_meta.grid(row=1, column=2, columnspan=2, sticky="e", padx=18, pady=(0, 8))

        self.game_library_frame = ctk.CTkScrollableFrame(
            self.game_card,
            height=178,
            orientation="horizontal",
            fg_color=SURFACE_PRIMARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.game_library_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 12))
        self.game_library_frame.grid_rowconfigure(0, weight=1)

        self.game_paths_label = ctk.CTkLabel(
            self.game_card,
            text="Nenhum jogo selecionado.",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
        )
        self.game_paths_label.grid(row=3, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 18))

    def _build_profile_area(self):
        self.profile_header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.profile_header.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.profile_header.grid_columnconfigure(0, weight=1)
        self.profile_header.grid_columnconfigure(1, weight=0)
        self.profile_header.grid_columnconfigure(2, weight=0)
        self.profile_header.grid_columnconfigure(3, weight=0)

        self.profile_title = ctk.CTkLabel(
            self.profile_header,
            text="Saves do jogo",
            font=("Segoe UI Bold", 20),
            text_color=TEXT_PRIMARY,
        )
        self.profile_title.grid(row=0, column=0, sticky="w")

        self.profile_count_label = ctk.CTkLabel(
            self.profile_header,
            text="0 perfis",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
        )
        self.profile_count_label.grid(row=0, column=1, sticky="e")

        self.save_profile_button = ctk.CTkButton(
            self.profile_header,
            text="Salvar perfil ativo",
            command=self._save_current_profile_snapshot,
            width=132,
            height=30,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.save_profile_button.grid(row=0, column=2, sticky="e", padx=(10, 0))

        self.profile_more_actions_button = ctk.CTkButton(
            self.profile_header,
            text="Mais ações",
            command=self._toggle_more_actions,
            width=96,
            height=30,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.profile_more_actions_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

        self.profile_search = ctk.CTkEntry(
            self.left_panel,
            placeholder_text="Buscar save/perfil...",
            height=36,
            corner_radius=12,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.profile_search.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.profile_search.bind("<KeyRelease>", lambda _event: self._refresh_profiles())

        self.profile_list = ctk.CTkScrollableFrame(
            self.left_panel,
            fg_color=SURFACE_SECONDARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.profile_list.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.profile_list.grid_columnconfigure(0, weight=1)
        self._bind_profile_mousewheel()

    def _build_sidebar(self):
        self.selected_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=SURFACE_SECONDARY,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.selected_card.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 12))

        self.selected_header = ctk.CTkFrame(self.selected_card, fg_color="transparent")
        self.selected_header.pack(fill="x", padx=18, pady=(18, 8))
        self.selected_header.grid_columnconfigure(0, weight=1)

        self.selected_title = ctk.CTkLabel(
            self.selected_header,
            text="Jogo selecionado",
            font=("Segoe UI Semibold", 13),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.selected_title.grid(row=0, column=0, sticky="w")

        self.game_panel_title = ctk.CTkLabel(
            self.selected_card,
            text="Nenhum jogo",
            font=("Segoe UI Bold", 24),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.game_panel_title.pack(fill="x", padx=18, pady=(0, 8))

        self.game_banner = ctk.CTkFrame(
            self.selected_card,
            height=118,
            fg_color=SURFACE_TERTIARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.game_banner.pack(fill="x", padx=18, pady=(0, 12))
        self.game_banner.pack_propagate(False)

        self.game_banner_label = ctk.CTkLabel(
            self.game_banner,
            text="CAPA",
            font=("Segoe UI Bold", 28),
            text_color=TEXT_SECONDARY,
        )
        self.game_banner_label.pack(expand=True)

        self.game_panel_meta = ctk.CTkLabel(
            self.selected_card,
            text="Biblioteca pronta para capas, banners e atalhos.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
        )
        self.game_panel_meta.pack(fill="x", padx=18, pady=(0, 12))

        self.game_action_row = ctk.CTkFrame(self.selected_card, fg_color="transparent")
        self.game_action_row.pack(fill="x", padx=18, pady=(0, 12))
        self.game_action_row.grid_columnconfigure(0, weight=2)
        self.game_action_row.grid_columnconfigure(1, weight=1)

        self.play_button = ctk.CTkButton(
            self.game_action_row,
            text="Jogar",
            command=self._play_current_game_placeholder,
            height=42,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.play_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.quick_save_button = ctk.CTkButton(
            self.game_action_row,
            text="Salvar",
            command=self._save_current_profile_snapshot,
            height=42,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.quick_save_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.selected_value = ctk.CTkLabel(
            self.selected_card,
            text="Perfil: nenhum",
            font=("Segoe UI Semibold", 13),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
        )
        self.selected_value.pack(fill="x", padx=18, pady=(0, 6))

        self.selected_hint = ctk.CTkLabel(
            self.selected_card,
            text="Os perfis continuam abaixo para troca de saves.",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
        )
        self.selected_hint.pack(fill="x", padx=18, pady=(0, 18))

        self.more_actions_button = ctk.CTkButton(
            self.selected_card,
            text="Mais ações",
            command=self._toggle_more_actions,
            height=36,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.more_actions_button.pack(fill="x", padx=18, pady=(0, 14))

        self.action_card = ctk.CTkFrame(
            self.selected_card,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.action_card.grid_columnconfigure(0, weight=1)

        buttons = [
            ("Adicionar perfil", self._create_profile, ACCENT_COLOR, ACCENT_HOVER, None),
            (
                "Exportar save atual",
                self._export_current_save,
                ("#0f766e", "#0f766e"),
                ("#115e59", "#134e4a"),
                ("#ecfeff", "#ecfeff"),
            ),
            (
                "Renomear perfil",
                self._rename_profile,
                ("#d97706", "#b45309"),
                ("#b45309", "#92400e"),
                ("#fff7ed", "#fff7ed"),
            ),
            (
                "Excluir perfil",
                self._delete_profile,
                ("#ef4444", "#dc2626"),
                ("#dc2626", "#b91c1c"),
                None,
            ),
            (
                "Limpar save atual",
                self._clear_current_save,
                ("#7c3aed", "#6d28d9"),
                ("#6d28d9", "#5b21b6"),
                None,
            ),
        ]

        for row, (text, command, fg_color, hover_color, text_color) in enumerate(buttons):
            button = ctk.CTkButton(
                self.action_card,
                text=text,
                command=command,
                fg_color=fg_color,
                hover_color=hover_color,
                height=40,
            )
            if text_color:
                button.configure(text_color=text_color)
            button.grid(
                row=row,
                column=0,
                sticky="ew",
                padx=10,
                pady=(10 if row == 0 else 6, 10 if row == len(buttons) - 1 else 0),
            )
        self.more_actions_visible = False

        self.status_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=SURFACE_SECONDARY,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.status_card.grid(row=1, column=0, sticky="ew", padx=22, pady=12)

        self.status_title = ctk.CTkLabel(
            self.status_card,
            text="Atividade",
            font=("Segoe UI Semibold", 16),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.status_title.pack(fill="x", padx=18, pady=(18, 6))

        self.status_message = ctk.CTkLabel(
            self.status_card,
            text="Selecione um perfil para começar.",
            font=("Segoe UI", 13),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=320,
        )
        self.status_message.pack(fill="x", padx=18, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.status_card)
        self.progress_bar.pack(fill="x", padx=18, pady=(0, 18))
        self.progress_bar.set(0)

        self.tips_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=SURFACE_SECONDARY,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.tips_card.grid(row=3, column=0, sticky="nsew", padx=22, pady=(12, 22))
        self.tips_card.grid_columnconfigure(0, weight=1)

        self.tips_title = ctk.CTkLabel(
            self.tips_card,
            text="Guia",
            font=("Segoe UI Semibold", 16),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.tips_title.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        self.tip_labels = []
        tip_lines = [
            "Escolha um jogo na biblioteca para ver seus perfis.",
            "Favoritos ficam em destaque para acesso rápido.",
            "O app protege a troca de saves quando detecta risco.",
            "Capas, banners e atalho de jogo já têm espaço reservado.",
        ]

        for index, text in enumerate(tip_lines, start=1):
            label = ctk.CTkLabel(
                self.tips_card,
                text=f"- {text}",
                font=("Segoe UI", 12),
                text_color=TEXT_SECONDARY,
                justify="left",
                anchor="w",
                wraplength=520,
            )
            label.grid(row=index, column=0, sticky="ew", padx=18, pady=6)
            self.tip_labels.append(label)

        self._update_sidebar_wraplengths()

    def _refresh_theme_switch(self):
        if obter_tema() == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()

    def _toggle_theme(self):
        theme_name = "dark" if self.theme_switch.get() else "light"
        definir_tema(theme_name)
        apply_theme(theme_name)
        self._set_status(f"Tema '{theme_name}' aplicado e salvo.", "success")

    def _toggle_more_actions(self):
        return self._open_more_actions_modal()

    def _open_more_actions_modal(self):
        if hasattr(self, "more_actions_modal") and self.more_actions_modal.winfo_exists():
            self.more_actions_modal.lift()
            self.more_actions_modal.focus_force()
            return

        modal = ctk.CTkToplevel(self)
        self.more_actions_modal = modal
        modal.title("Mais ações")
        modal.geometry("380x430")
        modal.resizable(False, False)
        modal.transient(self)
        modal.configure(fg_color=SURFACE_SECONDARY)
        modal.grid_columnconfigure(0, weight=1)
        modal.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            modal,
            text="Ações do save",
            font=("Segoe UI Bold", 20),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))

        actions_frame = ctk.CTkScrollableFrame(
            modal,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        actions_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 14))
        actions_frame.grid_columnconfigure(0, weight=1)

        actions = [
            ("Adicionar perfil", self._create_profile, ACCENT_COLOR, ACCENT_HOVER, None),
            ("Exportar save atual", self._export_current_save, ("#0f766e", "#0f766e"), ("#115e59", "#134e4a"), ("#ecfeff", "#ecfeff")),
            ("Renomear perfil", self._rename_profile, ("#d97706", "#b45309"), ("#b45309", "#92400e"), ("#fff7ed", "#fff7ed")),
            ("Excluir perfil", self._delete_profile, ("#ef4444", "#dc2626"), ("#dc2626", "#b91c1c"), None),
            ("Limpar save atual", self._clear_current_save, ("#7c3aed", "#6d28d9"), ("#6d28d9", "#5b21b6"), None),
        ]

        for row, (text, command, fg_color, hover_color, text_color) in enumerate(actions):
            def run_action(callback=command):
                if modal.winfo_exists():
                    modal.destroy()
                callback()

            button = ctk.CTkButton(
                actions_frame,
                text=text,
                command=run_action,
                fg_color=fg_color,
                hover_color=hover_color,
                height=42,
            )
            if text_color:
                button.configure(text_color=text_color)
            button.grid(row=row, column=0, sticky="ew", padx=12, pady=(12 if row == 0 else 8, 0))

        ctk.CTkButton(
            modal,
            text="Fechar",
            command=modal.destroy,
            height=36,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        ).grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))

        modal.update_idletasks()
        x = self.winfo_x() + max(0, (self.winfo_width() - modal.winfo_width()) // 2)
        y = self.winfo_y() + max(0, (self.winfo_height() - modal.winfo_height()) // 2)
        modal.geometry(f"+{x}+{y}")
        modal.grab_set()

    def _load_selected_profile(self):
        if not self.selected_profile:
            self._set_status("Selecione um perfil para carregar.", "info")
            return
        self._activate_profile(self.selected_profile)

    def _get_sorted_games(self, query=""):
        return listar_nomes_jogos(query)

    def _get_library_query(self):
        return self.library_search.get().strip() if hasattr(self, "library_search") else ""

    def _load_games(self, initial=False):
        ordered_games = self._get_sorted_games("")
        if self.current_game not in ordered_games:
            self.current_game = ""
        if self.sidebar_selected_game not in ordered_games:
            self.sidebar_selected_game = ""
        if self.collection_selected_game not in ordered_games:
            self.collection_selected_game = ""
        self._refresh_game_selector()
        if self.current_page == "game" and self.game_tool_mode == "saves":
            self._refresh_profiles()
        self._refresh_home_shelves()

    def _refresh_game_selector(self):
        query = self._get_library_query()
        ordered_games = self._get_sorted_games(query)
        all_games = self._get_sorted_games("")
        values = ordered_games or all_games or [""]
        has_selector = bool(getattr(self, "game_selector", None))
        if has_selector:
            self.game_selector.configure(values=values)

        if values == [""]:
            self.current_game = ""
            if has_selector:
                self.game_selector.set("")
        else:
            if has_selector:
                self.game_selector.set(self.current_game if self.current_game in values else values[0])

        if self.sidebar_selected_game not in all_games:
            self.sidebar_selected_game = ""
        if self.collection_selected_game not in all_games:
            self.collection_selected_game = ""

        self._update_current_game_details()
        self._refresh_game_library_cards(query)
        if self.current_page == "game" and self.game_tool_mode == "saves":
            self._refresh_profiles()
        self._refresh_quick_actions()

    def _get_library_grid_columns(self, width=None):
        return 1

    def _on_library_grid_resize(self, event=None):
        if not hasattr(self, "game_library_frame"):
            return

        columns = self._get_library_grid_columns(event.width if event else None)
        if columns == self._library_grid_columns:
            return

        self._library_grid_columns = columns
        if self._library_grid_refresh_after:
            try:
                self.after_cancel(self._library_grid_refresh_after)
            except Exception:
                pass
        query = self._get_library_query()
        def refresh_grid():
            self._library_grid_refresh_after = None
            self._refresh_game_library_cards(query)

        self._library_grid_refresh_after = self.after(80, refresh_grid)

    def _refresh_game_library_cards(self, query=""):
        for widget in self.game_library_frame.winfo_children():
            widget.destroy()
        self.library_cards = {}
        all_filtered_games = listar_jogos_biblioteca(query)
        games = [
            game for game in all_filtered_games
            if self.library_filter == "all" or game.favorite
        ]
        total_games = len(listar_jogos_biblioteca(""))
        favorite_total = len([game for game in listar_jogos_biblioteca("") if game.favorite])
        self.library_meta.configure(
            text=(
                f"{len(games)} favorito(s)"
                if self.library_filter == "favorites"
                else (f"{len(games)} de {total_games} jogo(s)" if query else f"{total_games} jogo(s) na coleção")
            )
        )
        self._update_library_filter_buttons(favorite_total)
        if not games:
            empty_state = ctk.CTkFrame(
                self.game_library_frame,
                fg_color="transparent",
            )
            empty_state.grid(row=0, column=0, sticky="nsew", padx=24, pady=28)
            ctk.CTkLabel(
                empty_state,
                text=(
                    "Nenhum favorito ainda"
                    if self.library_filter == "favorites"
                    else ("Biblioteca vazia" if not query else "Nenhum jogo encontrado")
                ),
                font=("Segoe UI Bold", 22),
                text_color=TEXT_PRIMARY,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                empty_state,
                text=(
                    "Marque uma estrela nos cards para fixar jogos aqui."
                    if self.library_filter == "favorites"
                    else ("Cadastre jogos para montar sua coleção." if not query else "Tente outro termo de busca.")
                ),
                font=("Segoe UI", 13),
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).grid(row=1, column=0, sticky="w", pady=(6, 14))
            if not query and self.library_filter == "all":
                ctk.CTkButton(
                    empty_state,
                    text="Gerenciar jogos",
                    command=self._open_game_manager,
                    width=140,
                    height=38,
                    fg_color=ACCENT_COLOR,
                    hover_color=ACCENT_HOVER,
                ).grid(row=2, column=0, sticky="w")
            return

        for index, game in enumerate(games):
            profile_count = len(listar_perfis(game.name))
            card = GameLibraryListItem(
                self.game_library_frame,
                game=game,
                selected=game.name == self.sidebar_selected_game,
                on_select=self._select_game_from_card,
                on_open=self._open_game_from_card,
                on_favorite=self._toggle_favorite_from_card,
                profile_count=profile_count,
            )
            card.grid(row=index, column=0, sticky="ew", padx=3, pady=(4 if index == 0 else 2, 2))
            self.library_cards[game.name] = card

    def _get_collection_query(self):
        return self.collection_search.get().strip() if hasattr(self, "collection_search") else ""

    def _get_collection_grid_columns(self, width=None):
        if width is None and hasattr(self, "collection_grid_frame"):
            width = self.collection_grid_frame.winfo_width()
        width = width or 900
        return max(4, min(8, int(max(width - 16, 560) // 154)))

    def _on_collection_grid_resize(self, event=None):
        if not hasattr(self, "collection_grid_frame"):
            return

        columns = self._get_collection_grid_columns(event.width if event else None)
        if columns == self._collection_grid_columns:
            return

        self._collection_grid_columns = columns
        self._refresh_collection_grid()

    def _refresh_library_collection(self):
        self._refresh_game_selector()
        self._refresh_collection_grid()

    def _refresh_collection_grid(self):
        if not hasattr(self, "collection_grid_frame"):
            return

        for widget in self.collection_grid_frame.winfo_children():
            widget.destroy()
        self.collection_cards = {}

        query = self._get_collection_query()
        all_games = listar_jogos_biblioteca(query)
        games = [
            game for game in all_games
            if self.collection_filter == "all" or game.favorite
        ]
        total_games = len(listar_jogos_biblioteca(""))
        favorite_total = len([game for game in listar_jogos_biblioteca("") if game.favorite])
        self.collection_meta_label.configure(
            text=(
                f"{len(games)} favorito(s)"
                if self.collection_filter == "favorites"
                else (f"{len(games)} de {total_games} jogo(s)" if query else f"{total_games} jogo(s)")
            )
        )
        self._update_collection_filter_buttons(favorite_total)

        if not games:
            empty = ctk.CTkFrame(self.collection_grid_frame, fg_color="transparent")
            empty.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            ctk.CTkLabel(
                empty,
                text="Nenhum jogo encontrado" if query else "Biblioteca vazia",
                font=("Segoe UI Bold", 18),
                text_color=TEXT_PRIMARY,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                empty,
                text="Cadastre jogos em Gerenciar jogos para montar sua coleção.",
                font=("Segoe UI", 12),
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).grid(row=1, column=0, sticky="w", pady=(4, 10))
            ctk.CTkButton(
                empty,
                text="Gerenciar jogos",
                command=self._open_game_manager,
                width=130,
                height=32,
                fg_color=ACCENT_COLOR,
                hover_color=ACCENT_HOVER,
            ).grid(row=2, column=0, sticky="w")
            return

        columns = self._get_collection_grid_columns()
        self._collection_grid_columns = columns
        for column in range(columns):
            self.collection_grid_frame.grid_columnconfigure(column, weight=0)

        for index, game in enumerate(games):
            row = index // columns
            column = index % columns
            card = GameLibraryCard(
                self.collection_grid_frame,
                game=game,
                selected=game.name == self.collection_selected_game,
                on_select=self._select_game_from_collection,
                on_open=self._open_game_from_collection,
                on_favorite=self._toggle_favorite_from_card,
                profile_count=len(listar_perfis(game.name)),
            )
            card.grid(row=row, column=column, sticky="nw", padx=6, pady=8)
            self.collection_cards[game.name] = card

    def _set_collection_filter(self, filter_name):
        if filter_name not in {"all", "favorites"} or filter_name == self.collection_filter:
            return

        self.collection_filter = filter_name
        self._update_collection_filter_buttons()
        self._refresh_collection_grid()

    def _update_collection_filter_buttons(self, favorite_total=None):
        if not hasattr(self, "collection_all_filter_button"):
            return

        self.collection_all_filter_button.configure(
            fg_color=ACCENT_COLOR if self.collection_filter == "all" else SURFACE_SECONDARY,
            hover_color=ACCENT_HOVER if self.collection_filter == "all" else SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY if self.collection_filter == "all" else TEXT_SECONDARY,
        )
        self.collection_favorites_filter_button.configure(
            text="Favoritos" if favorite_total is None else f"Favoritos {favorite_total}",
            fg_color=ACCENT_COLOR if self.collection_filter == "favorites" else SURFACE_SECONDARY,
            hover_color=ACCENT_HOVER if self.collection_filter == "favorites" else SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY if self.collection_filter == "favorites" else TEXT_SECONDARY,
        )

    def _select_game_from_collection(self, selected_game):
        if self.busy:
            return

        self._set_collection_selected_game(selected_game)

    def _open_game_from_collection(self, selected_game):
        if self.busy:
            return

        self._open_game_context(selected_game, select_collection=True)

    def _refresh_home_shelves(self):
        if not hasattr(self, "home_favorites_frame") or not hasattr(self, "home_recents_frame"):
            return

        for frame in (self.home_favorites_frame, self.home_recents_frame):
            for widget in frame.winfo_children():
                widget.destroy()
        self.home_library_cards = {}

        all_games = listar_jogos_biblioteca("")
        favorites = [game for game in all_games if game.favorite][:8]
        recents = listar_jogos_recentes_biblioteca()[:8]

        self._populate_home_shelf(self.home_favorites_frame, favorites, "Nenhum favorito ainda.")
        self._populate_home_shelf(self.home_recents_frame, recents, "Nenhum jogo recente ainda.")

    def _populate_home_shelf(self, frame, games, empty_text):
        if not games:
            ctk.CTkLabel(
                frame,
                text=empty_text,
                font=("Segoe UI", 13),
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=16, pady=18)
            return

        for index, game in enumerate(games):
            card = GameLibraryCard(
                frame,
                game=game,
                selected=game.name == self.current_game,
                on_select=self._open_game_from_home,
                on_open=self._open_game_from_home,
                on_favorite=self._toggle_favorite_from_card,
                profile_count=len(listar_perfis(game.name)),
                compact=True,
            )
            card.grid(row=0, column=index, sticky="ns", padx=(12 if index == 0 else 0, 12), pady=12)
            self.home_library_cards[game.name] = card

    def _open_game_from_home(self, selected_game):
        if self.busy:
            return

        self._open_game_context(selected_game, select_collection=False)

    def _set_library_filter(self, filter_name):
        if filter_name not in {"all", "favorites"} or filter_name == self.library_filter:
            return

        self.library_filter = filter_name
        self._update_library_filter_buttons()
        self._refresh_game_library_cards(self._get_library_query())

    def _update_library_filter_buttons(self, favorite_total=None):
        if not hasattr(self, "library_all_filter_button"):
            return

        self.library_all_filter_button.configure(
            fg_color=ACCENT_COLOR if self.library_filter == "all" else SURFACE_SECONDARY,
            hover_color=ACCENT_HOVER if self.library_filter == "all" else SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY if self.library_filter == "all" else TEXT_SECONDARY,
        )
        self.library_favorites_filter_button.configure(
            text="Favoritos" if favorite_total is None else f"Favoritos {favorite_total}",
            fg_color=ACCENT_COLOR if self.library_filter == "favorites" else SURFACE_SECONDARY,
            hover_color=ACCENT_HOVER if self.library_filter == "favorites" else SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY if self.library_filter == "favorites" else TEXT_SECONDARY,
        )

    def _select_game_from_card(self, selected_game):
        if self.busy:
            return

        self._open_game_context(selected_game, select_collection=False)

    def _open_game_from_card(self, selected_game):
        if self.busy:
            return

        self._open_game_context(selected_game, select_collection=False)

    def _set_sidebar_selected_game(self, selected_game):
        previous_game = self.sidebar_selected_game
        self.sidebar_selected_game = selected_game
        self._update_card_selection(self.library_cards, previous_game, selected_game)

    def _set_collection_selected_game(self, selected_game):
        previous_game = self.collection_selected_game
        self.collection_selected_game = selected_game
        self._update_card_selection(self.collection_cards, previous_game, selected_game)

    def _update_card_selection(self, cards, previous_game, selected_game):
        if previous_game and previous_game != selected_game:
            previous_card = cards.get(previous_game)
            if previous_card and previous_card.winfo_exists():
                previous_card.set_selected(False)

        selected_card = cards.get(selected_game)
        if selected_card and selected_card.winfo_exists():
            selected_card.set_selected(True)

    def _set_active_game(self, selected_game, record_recent=True):
        if not selected_game:
            return

        changed = selected_game != self.current_game
        self.current_game = selected_game
        if record_recent:
            registrar_recente(selected_game)
        if changed:
            self.selected_profile = None

        self._update_current_game_details()
        if self.game_tool_mode == "saves":
            self._refresh_profiles()
        self._refresh_home_shelves_if_visible()
        self._set_status(f"Jogo atual alterado para '{selected_game}'.", "info")

    def _refresh_home_shelves_if_visible(self):
        if self.current_page == "home":
            self._refresh_home_shelves()

    def _show_library_collection(self):
        self.library_mode = "collection"
        self.library_title.configure(text="Jogos")
        if hasattr(self, "library_game_context_label"):
            self.library_game_context_label.configure(text="Biblioteca")
        query = self._get_library_query()
        self._refresh_game_library_cards(query)
        self._refresh_collection_grid()

    def _show_library_game_context(self):
        if not self.current_game:
            return

        self.library_mode = "game"
        registrar_recente(self.current_game)
        self._refresh_home_shelves_if_visible()
        self.game_tool_mode = "overview"
        self._show_page("game")

    def _open_game_context(self, selected_game, select_collection=False):
        if self.busy or not selected_game:
            return

        if select_collection:
            self._set_collection_selected_game(selected_game)
        self.game_tool_mode = "overview"
        self._set_active_game(selected_game)
        self._show_page("game")

    def _show_game_overview(self):
        if not self.current_game:
            self._set_status("Abra um jogo pela Coleção primeiro.", "info")
            self._show_page("library")
            return

        self.game_tool_mode = "overview"
        self._show_page("game")

    def _show_game_saves(self):
        if not self.current_game:
            self._set_status("Abra um jogo antes de acessar os saves.", "info")
            self._show_page("library")
            return

        self.game_tool_mode = "saves"
        self._show_page("game")

    def _sync_game_page_mode(self):
        if not hasattr(self, "game_overview"):
            return

        showing_saves = self.game_tool_mode == "saves"
        if showing_saves:
            self.game_overview.grid_remove()
            self.profile_header.grid()
            self.profile_search.grid()
            self.profile_list.grid()
            self._refresh_profiles()
        else:
            self.profile_header.grid_remove()
            self.profile_search.grid_remove()
            self.profile_list.grid_remove()
            self.game_overview.grid()

        self._refresh_game_panel()
        self._refresh_quick_actions()

    def _refresh_library_game_context(self):
        if self.current_game and self.current_page == "game":
            self._refresh_game_panel()

    def _refresh_library_empty_context(self):
        return

    def _open_current_game_paths(self):
        if not self.current_game:
            return

        opened = 0
        registrar_recente(self.current_game)
        self._refresh_home_shelves_if_visible()
        for raw_path in obter_diretorios_jogo(self.current_game):
            path = Path(raw_path)
            if path.is_dir():
                os.startfile(path)
                opened += 1

        if opened:
            self._set_status(f"{opened} pasta(s) de '{self.current_game}' abertas.", "success")
        else:
            self._set_status("Nenhuma pasta válida para abrir.", "warning")

    def _open_current_game_in_manager(self):
        if not self.current_game:
            return

        self._game_manager_initial_game = self.current_game
        self._open_game_manager()

    def _open_library_manage_action(self):
        if self.current_game:
            self._open_current_game_in_manager()
        else:
            self._open_game_manager()

    def _update_current_game_details(self):
        if not self.current_game:
            if hasattr(self, "game_paths_label"):
                self.game_paths_label.configure(text="")
            if hasattr(self, "favorite_button"):
                self.favorite_button.configure(text="[ ]", state="disabled")
            if hasattr(self, "library_meta"):
                self.library_meta.configure(text="Acesso rápido")
            self._refresh_game_panel()
            return

        if hasattr(self, "favorite_button"):
            self.favorite_button.configure(
                text="[*]" if jogo_eh_favorito(self.current_game) else "[ ]",
                state="normal",
            )
        paths = obter_diretorios_jogo(self.current_game)
        preview = ", ".join(Path(path).name or path for path in paths[:2])
        if len(paths) > 2:
            preview = ", ".join(Path(path).name or path for path in paths[:2])
            preview += f" +{len(paths) - 2}"
        if hasattr(self, "game_paths_label"):
            self.game_paths_label.configure(text="")
        self._refresh_game_panel(paths)

    def _refresh_game_panel(self, paths=None):
        if not self.current_game:
            self.game_panel_title.configure(text="Nenhum jogo")
            self.game_banner_label.configure(text="CAPA")
            self.game_panel_meta.configure(text="Escolha um jogo na Coleção para abrir o contexto.")
            if hasattr(self, "game_context_title"):
                self.game_context_title.configure(text="Contexto do jogo")
                self.game_context_summary.configure(
                    text="Abra um jogo pela Coleção ou pela lista rápida para ver ações e ferramentas."
                )
                self.game_context_status.configure(text="Nenhum jogo aberto.")
                self.game_context_saves.configure(text="Perfis e backups ficam em uma seção própria.")
                self.game_context_tools.configure(text="Mods, backups, diretórios e opções de execução entram aqui futuramente.")
                self.game_context_paths.configure(text="Pastas de save vinculadas ao jogo.")
            if hasattr(self, "home_current_game"):
                self.home_current_game.configure(text="Escolha um jogo na biblioteca para preparar seus saves.")
            self.play_button.configure(state="disabled")
            self.quick_save_button.configure(state="disabled")
            self.load_profile_button.configure(state="disabled")
            self.more_actions_button.configure(state="disabled")
            return

        paths = paths if paths is not None else obter_diretorios_jogo(self.current_game)
        initials = "".join(part[:1] for part in self.current_game.split()[:2]).upper() or "JG"
        self.game_panel_title.configure(text=self.current_game)
        self.game_banner_label.configure(text=initials)
        profile_total = len(listar_perfis(self.current_game))
        active_profile = obter_perfil_ativo(self.current_game)
        self.game_panel_meta.configure(text=f"{profile_total} perfil(is) · {len(paths)} diretório(s)")
        if hasattr(self, "game_context_title"):
            self.game_context_title.configure(text=f"Hub de {self.current_game}")
            self.game_context_summary.configure(
                text="Página contextual do jogo. Use as seções para acessar saves, diretórios, mods e configurações futuras."
            )
            self.game_context_status.configure(
                text=f"Perfil ativo: {active_profile}" if active_profile else "Nenhum perfil ativo no momento."
            )
            self.game_context_saves.configure(text=f"{profile_total} perfil(is) de save cadastrado(s).")
            self.game_context_tools.configure(text="Saves já disponíveis. Mods, backups e launch options preparados para expansão.")
            self.game_context_paths.configure(text=f"{len(paths)} pasta(s) de save vinculada(s).")
        if hasattr(self, "home_current_game"):
            self.home_current_game.configure(text=f"{self.current_game} pronto para gerenciar saves.")
        self.play_button.configure(state="normal")
        self.quick_save_button.configure(state="normal")
        self.load_profile_button.configure(state="normal")
        self.more_actions_button.configure(state="normal")

    def _play_current_game_placeholder(self):
        if not self.current_game:
            return

        self._set_status(
            f"Atalho de execução de '{self.current_game}' preparado para uma etapa futura.",
            "info",
        )

    def _refresh_profiles(self):
        for widget in self.profile_list.winfo_children():
            widget.destroy()

        if not self.current_game:
            self.profile_count_label.configure(text="0 perfis")
            empty = ctk.CTkLabel(
                self.profile_list,
                text="Cadastre um jogo para começar a criar perfis.",
                text_color=TEXT_SECONDARY,
                anchor="w",
                justify="left",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=18, pady=18)
            self._update_selected_profile(None)
            self._bind_profile_mousewheel()
            return

        search = self.profile_search.get().strip().lower()
        profiles = listar_perfis(self.current_game)
        filtered_profiles = [profile for profile in profiles if search in profile.lower()]
        active_profile = obter_perfil_ativo(self.current_game)
        self.profile_count_label.configure(text=f"{len(filtered_profiles)} perfil(is)")

        if self.selected_profile not in profiles:
            self.selected_profile = active_profile if active_profile in profiles else None
        self._update_selected_profile(self.selected_profile)

        if not filtered_profiles:
            empty = ctk.CTkLabel(
                self.profile_list,
                text="Nenhum perfil encontrado com esse filtro.",
                text_color=TEXT_SECONDARY,
                anchor="w",
                justify="left",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=18, pady=18)
            self._bind_profile_mousewheel()
            return

        for index, profile in enumerate(filtered_profiles):
            card = ProfileCard(
                self.profile_list,
                profile_name=profile,
                active=profile == active_profile,
                on_activate=self._activate_profile,
            )
            card.grid(row=index, column=0, sticky="ew", padx=14, pady=10)
        self._bind_profile_mousewheel()

    def _bind_profile_mousewheel(self):
        if not hasattr(self, "profile_list"):
            return

        canvas = getattr(self.profile_list, "_parent_canvas", None)
        if not canvas:
            return

        def on_mousewheel(event):
            canvas.yview_scroll(self._mousewheel_units(event), "units")
            return "break"

        def on_button_4(_event):
            canvas.yview_scroll(-4, "units")
            return "break"

        def on_button_5(_event):
            canvas.yview_scroll(4, "units")
            return "break"

        self._bind_mousewheel_tree(self.profile_list, on_mousewheel, on_button_4, on_button_5)
        self._bind_mousewheel_tree(canvas, on_mousewheel, on_button_4, on_button_5)

    def _mousewheel_units(self, event):
        steps = max(1, abs(getattr(event, "delta", 120)) // 120)
        direction = -1 if event.delta > 0 else 1
        return direction * steps * 4

    def _bind_mousewheel_tree(self, widget, on_mousewheel, on_button_4, on_button_5, visited=None):
        if visited is None:
            visited = set()

        widget_id = str(widget)
        if widget_id in visited:
            return
        visited.add(widget_id)

        try:
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_button_4)
            widget.bind("<Button-5>", on_button_5)
        except Exception:
            return

        for child in getattr(widget, "winfo_children", lambda: [])():
            self._bind_mousewheel_tree(child, on_mousewheel, on_button_4, on_button_5, visited)

        for attr_name in (
            "_canvas",
            "_label",
            "_text_label",
            "_image_label",
            "_parent_canvas",
            "_parent_frame",
        ):
            child = getattr(widget, attr_name, None)
            if child and child is not widget:
                self._bind_mousewheel_tree(child, on_mousewheel, on_button_4, on_button_5, visited)

    def _update_selected_profile(self, profile_name):
        self.selected_profile = profile_name
        self.selected_value.configure(text=f"Perfil: {profile_name}" if profile_name else "Perfil: nenhum")
        self._refresh_quick_actions()

    def _refresh_quick_actions(self):
        active_profile = obter_perfil_ativo(self.current_game) if self.current_game else None
        can_save_now = bool(active_profile and not self.busy)
        if hasattr(self, "save_profile_button"):
            self.save_profile_button.configure(state="normal" if can_save_now else "disabled")
        if active_profile:
            self.selected_hint.configure(text=f"Ativo: {active_profile}")
        else:
            self.selected_hint.configure(text="Crie ou carregue um perfil para ativar salvamento rápido.")

    def _on_game_selected(self, selected_game):
        if self.busy:
            return
        self._set_active_game(selected_game)

    def _toggle_favorite_game(self):
        if not self.current_game:
            return

        favorite = alternar_favorito_jogo(self.current_game)
        self._sync_favorite_visual(self.current_game, favorite)
        self._refresh_home_shelves_if_visible()
        self._set_status(
            f"Jogo '{self.current_game}' {'favoritado' if favorite else 'removido dos favoritos'}.",
            "success",
        )

    def _toggle_favorite_from_card(self, game_name):
        if self.busy:
            return

        favorite = alternar_favorito_jogo(game_name)
        self._sync_favorite_visual(game_name, favorite)
        self._refresh_home_shelves_if_visible()

        if self.library_filter == "favorites" and not favorite:
            self._refresh_game_library_cards(self._get_library_query())
        if self.collection_filter == "favorites" and not favorite:
            self._refresh_collection_grid()

        self._set_status(
            f"Jogo '{game_name}' {'favoritado' if favorite else 'removido dos favoritos'}.",
            "success",
        )

    def _sync_favorite_visual(self, game_name, favorite):
        card = self.library_cards.get(game_name)
        if card and card.winfo_exists():
            card.set_favorite(favorite)

        home_card = self.home_library_cards.get(game_name)
        if home_card and home_card.winfo_exists():
            home_card.set_favorite(favorite)

        collection_card = self.collection_cards.get(game_name)
        if collection_card and collection_card.winfo_exists():
            collection_card.set_favorite(favorite)

        favorite_total = len([game for game in listar_jogos_biblioteca("") if game.favorite])
        self._update_library_filter_buttons(favorite_total)
        self._update_collection_filter_buttons(favorite_total)

    def _open_game_manager(self):
        if self.busy:
            return

        if self.game_manager and self.game_manager.winfo_exists():
            if self._game_manager_initial_game:
                self.game_manager.refresh(selected_game=self._game_manager_initial_game)
                self._game_manager_initial_game = None
            self.game_manager.lift()
            self.game_manager.focus_set()
            return

        if self._game_manager_open_after is not None:
            return

        self._game_manager_open_after = self.after(80, self._create_game_manager)

    def _create_game_manager(self):
        self._game_manager_open_after = None

        if self.busy:
            return

        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.lift()
            self.game_manager.focus_set()
            return

        self.game_manager = GameManagerWindow(
            self,
            dnd_context=self.dnd_context,
            list_games=lambda: self._get_sorted_games(""),
            get_paths_for_game=obter_diretorios_jogo,
            on_save=self._save_game_from_manager,
            on_delete=self._delete_game_from_manager,
        )
        if self._game_manager_initial_game:
            self.game_manager.refresh(selected_game=self._game_manager_initial_game)
            self._game_manager_initial_game = None

    def _ask_profile_name(self, title, initial_value=""):
        dialog = PromptDialog(
            self,
            title=title,
            label="Nome do perfil",
            initial_value=initial_value,
            validator=validate_profile_name,
        )
        return dialog.get_result()

    def _set_status(self, message, level="info"):
        colors = {
            "info": TEXT_SECONDARY,
            "success": SUCCESS_COLOR,
            "warning": WARNING_COLOR,
            "error": ERROR_COLOR,
        }
        self.status_message.configure(text=message, text_color=colors.get(level, TEXT_SECONDARY))

    def _start_busy(self, message):
        self.busy = True
        self.progress_bar.set(0)
        self._set_status(message, "warning")
        self.busy_overlay.show(message)
        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.set_interaction_enabled(False)
        self._refresh_quick_actions()

    def _update_progress(self, value, message):
        self.progress_bar.set(value)
        self.busy_overlay.set_progress(value, message)
        self._set_status(message, "warning")

    def _stop_busy(self):
        self.busy = False
        self.busy_overlay.hide()
        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.set_interaction_enabled(True)
        self._refresh_quick_actions()

    def _run_operation(self, start_message, success_message, worker, on_success=None, on_error=None):
        if self.busy:
            return

        self._start_busy(start_message)

        def progress_callback(value, message):
            self.after(0, lambda: self._update_progress(value, message))

        def task():
            try:
                result = worker(progress_callback)
            except Exception as error:
                self.after(0, lambda: self._finish_operation(False, f"Erro: {error}", None, on_success, on_error))
                return
            self.after(0, lambda: self._finish_operation(True, success_message, result, on_success, on_error))

        threading.Thread(target=task, daemon=True).start()

    def _finish_operation(self, success, message, result, on_success, on_error):
        self._stop_busy()
        self.progress_bar.set(1 if success else 0)
        self._set_status(message, "success" if success else "error")

        if success and on_success:
            on_success(result)
        elif not success and on_error:
            on_error(message)

    def _confirm_runtime_warnings(self, action_label, overwrite=False):
        if not self.current_game:
            return False

        warnings = coletar_alertas_pre_troca(self.current_game, obter_diretorios_jogo(self.current_game))
        messages = [f"Deseja continuar com a ação '{action_label}' no jogo '{self.current_game}'?"]

        if overwrite:
            file_count = contar_arquivos_em_diretorios(obter_diretorios_jogo(self.current_game))
            if file_count > 0:
                messages.append(f"Os {file_count} arquivo(s) atuais de save podem ser substituídos.")

        if warnings:
            messages.append("Alertas detectados:")
            messages.extend(f"- {warning}" for warning in warnings)

        return messagebox.askyesno("Confirmar operação", "\n\n".join(messages), parent=self)

    def _activate_profile(self, profile_name):
        if not self.current_game or self.busy:
            return

        active_profile = obter_perfil_ativo(self.current_game)
        if profile_name == active_profile:
            self._update_selected_profile(profile_name)
            self._set_status(f"O perfil '{profile_name}' já está ativo.", "info")
            return

        self._update_selected_profile(profile_name)
        self._run_operation(
            "Trocando os arquivos de save...",
            f"Perfil '{profile_name}' carregado com sucesso.",
            lambda progress: aplicar_perfil(self.current_game, profile_name, progress_callback=progress),
            on_success=lambda _result: self._refresh_profiles(),
        )

    def _create_profile(self):
        if not self.current_game:
            self._set_status("Cadastre um jogo antes de criar perfis.", "error")
            return

        profile_name = self._ask_profile_name("Novo perfil")
        if not profile_name:
            return

        if not self._confirm_runtime_warnings("criar perfil"):
            return

        self._run_operation(
            "Criando novo perfil a partir dos saves atuais...",
            f"Perfil '{profile_name}' criado com sucesso.",
            lambda progress: criar_perfil(self.current_game, profile_name, progress_callback=progress),
            on_success=lambda _result: self._after_profile_saved(profile_name),
        )

    def _after_profile_saved(self, profile_name):
        self._update_selected_profile(profile_name)
        self._refresh_profiles()

    def _rename_profile(self):
        if not self.selected_profile:
            self._set_status("Selecione um perfil antes de renomear.", "error")
            return

        current_name = self.selected_profile
        new_name = self._ask_profile_name("Renomear perfil", initial_value=current_name)
        if not new_name:
            return

        self._run_operation(
            "Renomeando perfil...",
            f"Perfil renomeado para '{new_name}'.",
            lambda _progress: renomear_perfil(self.current_game, current_name, new_name),
            on_success=lambda _result: self._after_profile_saved(new_name),
        )

    def _delete_profile(self):
        if not self.selected_profile:
            self._set_status("Selecione um perfil antes de excluir.", "error")
            return

        confirmed = messagebox.askyesno(
            "Excluir perfil",
            (
                f"Deseja excluir o perfil '{self.selected_profile}'?\n\n"
                "Todos os arquivos associados a ele serão removidos."
            ),
            parent=self,
        )
        if not confirmed:
            return

        profile_name = self.selected_profile
        self._run_operation(
            "Excluindo perfil...",
            f"Perfil '{profile_name}' excluído com sucesso.",
            lambda progress: excluir_perfil(self.current_game, profile_name, progress_callback=progress),
            on_success=lambda _result: self._after_profile_deleted(),
        )

    def _after_profile_deleted(self):
        self._update_selected_profile(None)
        self._refresh_profiles()

    def _clear_current_save(self):
        if not self.current_game:
            self._set_status("Selecione um jogo antes de limpar o save.", "error")
            return

        if not self._confirm_runtime_warnings("limpar save"):
            return

        confirmed = messagebox.askyesno(
            "Limpar save atual",
            (
                f"Deseja limpar somente as pastas de save configuradas para '{self.current_game}' no PC?\n\n"
                "Os backups e perfis salvos dentro do programa não serão apagados.\n\n"
                "Essa ação não pode ser desfeita."
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._run_operation(
            "Limpando as pastas de save...",
            f"Pastas de save de '{self.current_game}' limpas. Backups do programa preservados.",
            lambda progress: limpar_saves_do_jogo(self.current_game, progress_callback=progress),
            on_success=lambda _result: self._refresh_profiles(),
        )

    def _save_current_profile_snapshot(self):
        if not self.current_game:
            self._set_status("Selecione um jogo antes de salvar o save atual.", "error")
            return

        active_profile = obter_perfil_ativo(self.current_game)
        if not active_profile:
            self._set_status("Nenhum perfil ativo para receber o save atual.", "error")
            return

        confirmed = messagebox.askyesno(
            "Salvar save atual",
            (
                f"Deseja salvar o estado atual dos saves no perfil ativo '{active_profile}'?\n\n"
                "Isso atualiza o backup desse perfil com os arquivos que estão nas pastas do jogo agora."
            ),
            parent=self,
        )
        if not confirmed:
            return

        self._run_operation(
            "Salvando o save atual no perfil ativo...",
            f"Save atual salvo no perfil '{active_profile}'.",
            lambda progress: fazer_backup(self.current_game, active_profile, progress_callback=progress),
            on_success=lambda _result: self._refresh_profiles(),
        )

    def _export_current_save(self):
        if not self.current_game:
            self._set_status("Selecione um jogo antes de exportar o save atual.", "error")
            return

        destination_folder = filedialog.askdirectory(
            parent=self,
            title="Escolha a pasta de destino para exportar o save atual",
            mustexist=True,
        )
        if not destination_folder:
            return

        self._run_operation(
            "Exportando o save atual...",
            "Save atual exportado com sucesso.",
            lambda progress: exportar_saves_do_jogo(
                self.current_game,
                destination_folder,
                progress_callback=progress,
            ),
            on_success=self._after_save_exported,
        )

    def _after_save_exported(self, export_path):
        self._set_status(f"Save atual exportado para: {export_path}", "success")

    def _save_game_from_manager(self, current_name, new_name, paths):
        self._run_operation(
            "Salvando configuração do jogo...",
            f"Jogo '{new_name}' salvo com sucesso.",
            lambda _progress: salvar_jogo(current_name, new_name, paths),
            on_success=lambda result: self._after_game_saved(result),
            on_error=lambda message: self._show_game_manager_error("Salvar jogo", message),
        )

    def _after_game_saved(self, game_name):
        self.current_game = game_name
        if self.current_page == "game":
            self.sidebar_selected_game = game_name
        self.selected_profile = None
        self._refresh_game_selector()
        self._refresh_collection_grid()
        if self.current_page == "game" and self.game_tool_mode == "saves":
            self._refresh_profiles()
        self._refresh_home_shelves()
        self._sync_sidebar_context_highlight()
        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.refresh(selected_game=game_name)

    def _delete_game_from_manager(self, game_name):
        self._run_operation(
            "Excluindo jogo e seus perfis...",
            f"Jogo '{game_name}' excluído com sucesso.",
            lambda progress: excluir_jogo_com_dados(game_name, progress_callback=progress),
            on_success=lambda _result: self._after_game_deleted(),
            on_error=lambda message: self._show_game_manager_error("Excluir jogo", message),
        )

    def _after_game_deleted(self):
        games = self._get_sorted_games("")
        if self.current_game not in games:
            self.current_game = ""
        if self.sidebar_selected_game not in games:
            self.sidebar_selected_game = ""
        if self.collection_selected_game not in games:
            self.collection_selected_game = ""
        self.selected_profile = None
        self._refresh_game_selector()
        self._refresh_collection_grid()
        if self.current_page == "game" and self.game_tool_mode == "saves":
            self._refresh_profiles()
        self._refresh_home_shelves()
        self._sync_sidebar_context_highlight()
        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.refresh(selected_game=self.current_game or None)

    def _show_game_manager_error(self, title, message):
        if self.game_manager and self.game_manager.winfo_exists():
            self.game_manager.show_error(title, message)
        else:
            messagebox.showerror(title, message, parent=self)

    def _on_resize(self, _event=None):
        if not self.winfo_exists():
            return
        width = self.winfo_width()
        self._apply_main_layout(width < 1120)
        self._apply_header_layout(width < 920)
        self._apply_game_card_layout(width < 1260)
        self._update_sidebar_wraplengths()

    def _apply_main_layout(self, compact):
        if compact == self._compact_layout:
            return

        self._compact_layout = compact

        if compact:
            self.content.grid_columnconfigure(0, weight=0)
            self.content.grid_columnconfigure(1, weight=1)
            self.content.grid_columnconfigure(2, weight=0)
            self.content.grid_rowconfigure(0, weight=1)
            self.content.grid_rowconfigure(1, weight=0)
            self.nav_rail.grid_configure(row=0, column=0, rowspan=2, padx=(0, 8), pady=0, sticky="ns")
            self.page_host.grid_configure(row=0, column=1, columnspan=2, padx=0, pady=0, sticky="nsew")
        else:
            self.content.grid_columnconfigure(0, weight=0)
            self.content.grid_columnconfigure(1, weight=4)
            self.content.grid_columnconfigure(2, weight=3)
            self.content.grid_rowconfigure(0, weight=1)
            self.content.grid_rowconfigure(1, weight=0)
            self.nav_rail.grid_configure(row=0, column=0, rowspan=1, padx=(0, 10), pady=0, sticky="ns")
            self.page_host.grid_configure(row=0, column=1, columnspan=2, padx=0, pady=0, sticky="nsew")

    def _apply_header_layout(self, compact):
        if compact == self._compact_header:
            return

        self._compact_header = compact
        if compact:
            self.settings_button.grid_configure(row=1, column=0, sticky="w", padx=0, pady=(6, 0))
            self.theme_switch.grid_configure(row=1, column=2, sticky="e", padx=(8, 0), pady=(6, 0))
        else:
            self.settings_button.grid_configure(row=0, column=1, sticky="e", padx=8, pady=6)
            self.theme_switch.grid_configure(row=0, column=2, sticky="e", padx=(8, 0), pady=6)

    def _apply_game_card_layout(self, compact):
        if not getattr(self, "game_selector", None):
            return

        if compact == self._compact_game_controls:
            return

        self._compact_game_controls = compact

        if compact:
            self.game_search.grid_configure(row=0, column=0, columnspan=4, padx=18, pady=(18, 10), sticky="ew")
            self.game_selector.grid_configure(row=1, column=0, columnspan=2, padx=(18, 8), pady=(0, 10), sticky="ew")
            self.favorite_button.grid_configure(row=1, column=2, padx=8, pady=(0, 10), sticky="ew")
            self.manage_games_button.grid_configure(row=1, column=3, padx=(8, 18), pady=(0, 10), sticky="ew")
            self.library_title.grid_configure(row=2, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="w")
            self.library_meta.grid_configure(row=2, column=2, columnspan=2, padx=18, pady=(0, 8), sticky="e")
            self.game_library_frame.grid_configure(row=3, column=0, columnspan=4, padx=18, pady=(0, 12), sticky="ew")
            self.game_paths_label.grid_configure(row=4, column=0, columnspan=4, padx=18, pady=(0, 18), sticky="ew")
        else:
            self.game_search.grid_configure(row=0, column=0, columnspan=1, padx=(18, 8), pady=(18, 12), sticky="ew")
            self.game_selector.grid_configure(row=0, column=1, columnspan=1, padx=8, pady=(18, 12), sticky="ew")
            self.favorite_button.grid_configure(row=0, column=2, padx=8, pady=(18, 12), sticky="")
            self.manage_games_button.grid_configure(row=0, column=3, padx=(8, 18), pady=(18, 12), sticky="")
            self.library_title.grid_configure(row=1, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="w")
            self.library_meta.grid_configure(row=1, column=2, columnspan=2, padx=18, pady=(0, 8), sticky="e")
            self.game_library_frame.grid_configure(row=2, column=0, columnspan=4, padx=18, pady=(0, 12), sticky="ew")
            self.game_paths_label.grid_configure(row=3, column=0, columnspan=4, padx=18, pady=(0, 18), sticky="ew")

    def _update_sidebar_wraplengths(self):
        if not self.winfo_exists() or not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        sidebar_width = self.sidebar.winfo_width()
        if sidebar_width <= 1:
            return

        wraplength = max(250, sidebar_width - 120)
        for widget_name in ("status_message", "selected_hint"):
            widget = getattr(self, widget_name, None)
            if widget and widget.winfo_exists():
                widget.configure(wraplength=wraplength)
        for label in getattr(self, "tip_labels", []):
            if label.winfo_exists():
                label.configure(wraplength=wraplength)

    def _maximize_on_startup(self):
        try:
            self.state("zoomed")
        except Exception:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            self.geometry(f"{screen_width}x{screen_height}+0+0")


def run_app():
    app = SaveManagerApp()
    app.mainloop()
