import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk
from PIL import ImageEnhance, ImageGrab, ImageTk

from app_ui.dialogs import PromptDialog
from app_ui.dnd_support import enable_tkdnd, get_dnd_ctk_base
from app_ui.game_manager_window import GameManagerWindow, MANAGER_MIN_HEIGHT, MANAGER_MIN_WIDTH
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
from app_ui.widgets import (
    BusyOverlay,
    GameLibraryCard,
    GameLibraryListItem,
    ProfileCard,
    animate_modal_close,
    animate_modal_open,
)
from core.config_manager import obter_diretorios_jogo
from core.collection_view_service import (
    CollectionError,
    create_collection,
    get_collections_overview,
    get_open_collection_view,
)
from core.game_manager import (
    alternar_favorito_jogo,
    excluir_jogo_com_dados,
    jogo_eh_favorito,
    listar_jogos_biblioteca,
    listar_jogos_recentes_biblioteca,
    listar_nomes_jogos,
    obter_launch_config_jogo,
    salvar_jogo,
)
from core.game_context_service import get_game_context_summary, open_game_save_directories
from core.launch_service import execute_launch_config
from core.local_auth import (
    AuthError,
    authenticate_local_user,
    clear_session,
    create_local_user,
    create_session,
    get_active_session,
    has_local_users,
)
from core.runtime_checks import (
    coletar_alertas_pre_troca,
    contar_arquivos_em_diretorios,
)
from core.save_view_service import (
    activate_save_profile,
    clear_current_save,
    create_save_profile,
    delete_save_profile,
    export_current_save,
    get_active_save_profile,
    get_profile_count,
    get_save_profiles_view,
    rename_save_profile,
    save_active_profile_snapshot,
)
from core.settings_manager import (
    definir_tema,
    obter_tema,
    registrar_recente,
)
from core.user_manager import get_current_user
from core.validators import validate_profile_name


GAME_MANAGER_OVERLAY_COLOR = "#10141d"
GAME_MANAGER_PANEL_INSET = 12
GAME_MANAGER_PANEL_RADIUS = 24


class SaveManagerApp(get_dnd_ctk_base()):
    def __init__(self):
        apply_theme(obter_tema())
        super().__init__()

        self.title("Multiple Save Manager")
        self.geometry("1280x780")
        self.minsize(1000, 680)
        self.configure(fg_color=APP_BACKGROUND)

        self.auth_frame = None
        self._main_initialized = False
        self._resize_bound = False
        self.dnd_context = None

        if get_active_session():
            self._start_authenticated_app()
        else:
            self._show_auth_screen(create_mode=not has_local_users())

        self.after(0, self._maximize_on_startup)

    def _setup_main_state(self):
        self.busy = False
        self.selected_profile = None
        self.current_game = ""
        self.sidebar_selected_game = ""
        self.collection_selected_game = ""
        self.current_page = "home"
        self.game_tool_mode = "overview"
        self.game_manager = None
        self.game_manager_wrapper = None
        self.game_manager_overlay = None
        self.modal_layer = None
        self._active_modal_close_callback = None
        self._modal_is_closing = False
        self._persistent_modal_widgets = set()
        self._game_manager_overlay_canvas = None
        self._game_manager_overlay_image = None
        self._game_manager_panel_bounds = (0, 0, 0, 0)
        self._game_manager_initial_game = None
        self._compact_layout = False
        self._compact_header = False
        self._compact_game_controls = False
        self._library_grid_columns = 0
        self._library_grid_refresh_after = None
        self.library_cards = {}
        self.library_card_signatures = {}
        self.home_library_cards = {}
        self.home_shelf_cards = {"favorites": {}, "recents": {}}
        self.home_shelf_card_signatures = {"favorites": {}, "recents": {}}
        self.home_shelf_empty_labels = {}
        self.library_filter = "all"
        self.collection_cards = {}
        self.collection_filter = "all"
        self.profile_cards = {}
        self.profile_empty_label = None
        self._collection_grid_columns = 0
        self.library_mode = "collection"
        self.user_collection_cards = {}
        self.collection_empty_card = None
        self.open_collection_back_row = None
        self.open_collection_empty_label = None
        self.open_collection_game_cards = {}
        self.open_collection_game_card_signatures = {}
        self.open_collection_id = ""
        self._page_built = {}

    def _start_authenticated_app(self):
        if self.auth_frame is not None and self.auth_frame.winfo_exists():
            self.auth_frame.destroy()
        self.auth_frame = None

        self._setup_main_state()
        self.dnd_context = enable_tkdnd(self)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_content()
        self.busy_overlay = BusyOverlay(self)

        self._load_games(initial=True)
        self._refresh_theme_switch()
        if not self._resize_bound:
            self.bind("<Configure>", self._on_resize)
            self._resize_bound = True
        self._main_initialized = True

    def _show_auth_screen(self, create_mode=False):
        self._destroy_main_ui()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.auth_frame = ctk.CTkFrame(self, fg_color=APP_BACKGROUND, corner_radius=0)
        self.auth_frame.grid(row=0, column=0, sticky="nsew")
        self.auth_frame.grid_columnconfigure(0, weight=1)
        self.auth_frame.grid_rowconfigure(0, weight=1)

        self.auth_content_frame = ctk.CTkFrame(
            self.auth_frame,
            fg_color=SURFACE_PRIMARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.auth_content_frame.grid(row=0, column=0, sticky="", padx=24, pady=24)
        self.auth_content_frame.grid_columnconfigure(0, weight=1)
        if create_mode:
            self._render_create_user_form(first_user_creation=not has_local_users())
        else:
            self._render_login_form()

    def _clear_auth_content(self):
        for widget in self.auth_content_frame.winfo_children():
            widget.destroy()

    def _build_auth_header(self, title, subtitle):
        ctk.CTkLabel(
            self.auth_content_frame,
            text=title,
            font=("Segoe UI Bold", 24),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 4))

        ctk.CTkLabel(
            self.auth_content_frame,
            text=subtitle,
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 18))

    def _build_auth_entry(self, row, placeholder, show=None):
        entry_options = {}
        if show:
            entry_options["show"] = show
        entry = ctk.CTkEntry(
            self.auth_content_frame,
            placeholder_text=placeholder,
            width=360,
            height=38,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            **entry_options,
        )
        entry.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 10))
        return entry

    def _build_auth_password_entry(self, row, placeholder):
        field_frame = ctk.CTkFrame(self.auth_content_frame, fg_color="transparent")
        field_frame.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 10))
        field_frame.grid_columnconfigure(0, weight=1)
        field_frame.grid_columnconfigure(1, weight=0)

        entry = ctk.CTkEntry(
            field_frame,
            placeholder_text=placeholder,
            height=38,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            show="*",
        )
        entry.grid(row=0, column=0, sticky="ew")
        entry.password_visible = False

        toggle_button = ctk.CTkButton(
            field_frame,
            text="👁",
            width=38,
            height=38,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_COLOR,
            command=lambda: self._toggle_password_visibility(entry, toggle_button),
        )
        toggle_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        return entry

    def _toggle_password_visibility(self, entry, button):
        try:
            cursor_index = entry.index("insert")
        except tk.TclError:
            cursor_index = None

        entry.password_visible = not bool(getattr(entry, "password_visible", False))
        if entry.password_visible:
            entry.configure(show="")
            button.configure(text="👁", text_color=ACCENT_COLOR, border_color=ACCENT_COLOR)
        else:
            entry.configure(show="*")
            button.configure(text="👁", text_color=TEXT_SECONDARY, border_color=BORDER_COLOR)

        entry.focus_set()
        if cursor_index is not None:
            try:
                entry.icursor(cursor_index)
            except tk.TclError:
                pass

    def _build_auth_error_label(self, row):
        self.auth_error_label = ctk.CTkLabel(
            self.auth_content_frame,
            text="",
            font=("Segoe UI", 11),
            text_color=ERROR_COLOR,
            anchor="w",
        )
        self.auth_error_label.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 8))

    def _build_auth_action_row(self, row):
        action_row = ctk.CTkFrame(self.auth_content_frame, fg_color="transparent")
        action_row.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 24))
        action_row.grid_columnconfigure(0, weight=1)
        action_row.grid_columnconfigure(1, weight=1)
        return action_row

    def _render_login_form(self):
        self._clear_auth_content()
        self.current_auth_mode = "login"
        self._build_auth_header("Entrar", "Acesse com usuário e senha locais.")

        self.auth_username_entry = self._build_auth_entry(2, "Usuário")
        self.auth_password_entry = self._build_auth_password_entry(3, "Senha")
        self.auth_password_entry.bind("<Return>", lambda _event: self._submit_login_form())
        self._build_auth_error_label(4)
        action_row = self._build_auth_action_row(5)

        enter_button = ctk.CTkButton(
            action_row,
            text="Entrar",
            command=self._submit_login_form,
            height=36,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        enter_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        create_button = ctk.CTkButton(
            action_row,
            text="Criar usuário",
            command=lambda: self._render_create_user_form(first_user_creation=False),
            height=36,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        create_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.auth_username_entry.focus_set()

    def _render_create_user_form(self, first_user_creation=False):
        self._clear_auth_content()
        self.current_auth_mode = "create"
        title = "Criar primeiro usuário" if first_user_creation else "Criar usuário"
        self._build_auth_header(title, "Cadastre um usuário local para este launcher.")

        self.create_username_entry = self._build_auth_entry(2, "Usuário")
        self.create_password_entry = self._build_auth_password_entry(3, "Senha")
        self.create_confirm_password_entry = self._build_auth_password_entry(4, "Confirmar senha")
        self.create_confirm_password_entry.bind("<Return>", lambda _event: self._submit_create_user_form())
        self._build_auth_error_label(5)
        action_row = self._build_auth_action_row(6)

        create_button = ctk.CTkButton(
            action_row,
            text="Criar",
            command=self._submit_create_user_form,
            height=36,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        create_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        back_button = ctk.CTkButton(
            action_row,
            text="Voltar para login",
            command=self._render_login_form,
            height=36,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        back_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.create_username_entry.focus_set()

    def _submit_login_form(self):
        username = self.auth_username_entry.get() if hasattr(self, "auth_username_entry") else ""
        password = self.auth_password_entry.get() if hasattr(self, "auth_password_entry") else ""
        try:
            user = authenticate_local_user(username, password)
            create_session(user)
        except AuthError as exc:
            self.auth_error_label.configure(text=str(exc))
            return

        self._start_authenticated_app()

    def _submit_create_user_form(self):
        username = self.create_username_entry.get() if hasattr(self, "create_username_entry") else ""
        password = self.create_password_entry.get() if hasattr(self, "create_password_entry") else ""
        confirm_password = (
            self.create_confirm_password_entry.get()
            if hasattr(self, "create_confirm_password_entry")
            else ""
        )
        if password != confirm_password:
            self.auth_error_label.configure(text="As senhas não conferem.")
            return

        try:
            user = create_local_user(username, password)
            create_session(user)
        except AuthError as exc:
            self.auth_error_label.configure(text=str(exc))
            return

        self._start_authenticated_app()

    def _destroy_main_ui(self):
        if getattr(self, "game_manager", None) is not None and self.game_manager.winfo_exists():
            self.game_manager.destroy()
            self.game_manager = None
        if getattr(self, "game_manager_wrapper", None) is not None and self.game_manager_wrapper.winfo_exists():
            self.game_manager_wrapper.destroy()
            self.game_manager_wrapper = None
        if getattr(self, "game_manager_overlay", None) is not None and self.game_manager_overlay.winfo_exists():
            self.game_manager_overlay.place_forget()
            self.game_manager_overlay = None
        if hasattr(self, "_persistent_modal_widgets"):
            self._persistent_modal_widgets.clear()
        for attr in ("busy_overlay", "modal_layer", "header", "content"):
            widget = getattr(self, attr, None)
            if widget is not None and widget.winfo_exists():
                widget.destroy()
            if hasattr(self, attr):
                setattr(self, attr, None)
        self._main_initialized = False

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
        self.header.grid_rowconfigure(0, minsize=48)

        title_block = ctk.CTkFrame(self.header, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w", padx=(0, 14), pady=(4, 4))

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
            text="Launcher de saves e coleções",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w")
        self.subtitle_label.configure(text="Launcher de saves e coleções")

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
        self.nav_rail.grid_rowconfigure(6, weight=1)
        self._build_user_nav()
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
        self._build_modal_layer()
        self._prebuild_game_manager_modal()

    def _build_modal_layer(self):
        self.modal_layer = ctk.CTkFrame(
            self,
            fg_color=GAME_MANAGER_OVERLAY_COLOR,
            corner_radius=0,
        )
        self.modal_layer.place_forget()
        self.modal_layer.bind("<Button-1>", self._handle_modal_background_click)
        self.bind("<Escape>", self._handle_modal_escape, add="+")

    def _prepare_modal_layer(self, close_callback, fg_color=GAME_MANAGER_OVERLAY_COLOR):
        if not self.modal_layer or not self.modal_layer.winfo_exists():
            return

        self._clear_modal_layer_content()
        self._active_modal_close_callback = close_callback
        self._modal_is_closing = False
        self.modal_layer.configure(fg_color=fg_color)
        self.modal_layer.place(x=0, y=0, relwidth=1, relheight=1)
        self.modal_layer.lift()

    def _clear_modal_layer_content(self):
        if not self.modal_layer or not self.modal_layer.winfo_exists():
            return

        for child in self.modal_layer.winfo_children():
            if child in self._persistent_modal_widgets:
                child.place_forget()
                continue
            child.destroy()
        self._game_manager_overlay_canvas = None
        self._game_manager_overlay_image = None
        self._game_manager_panel_bounds = (0, 0, 0, 0)

    def _hide_modal_layer(self):
        if self.modal_layer and self.modal_layer.winfo_exists():
            self._clear_modal_layer_content()
            self.modal_layer.place_forget()
        self._active_modal_close_callback = None
        self._modal_is_closing = False

    def _create_internal_modal_panel(
        self,
        width,
        height,
        *,
        relx=0.5,
        rely=0.5,
        x=None,
        y=None,
        anchor="center",
        fg_color=SURFACE_PRIMARY,
        corner_radius=16,
        border_width=1,
        border_color=BORDER_COLOR,
    ):
        modal = ctk.CTkFrame(
            self.modal_layer,
            width=width,
            height=height,
            fg_color=fg_color,
            bg_color=GAME_MANAGER_OVERLAY_COLOR,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
        )
        modal.grid_propagate(False)
        modal.bind("<Button-1>", lambda _event: "break")
        modal._modal_animation = {
            "width": width,
            "height": height,
            "relx": relx,
            "rely": rely,
            "x": x,
            "y": y,
            "anchor": anchor,
        }
        modal.place(x=-10000, y=-10000, anchor="nw")
        return modal

    def _animate_internal_modal_open(self, modal, on_complete=None):
        animation = getattr(modal, "_modal_animation", None)
        if not animation:
            if on_complete:
                on_complete()
            return

        self._prepare_modal_for_animation(modal, animation)
        animate_modal_open(
            modal,
            animation["width"],
            animation["height"],
            relx=animation["relx"],
            rely=animation["rely"],
            x=animation["x"],
            y=animation["y"],
            anchor=animation["anchor"],
            duration_ms=150,
            start_scale=0.94,
            on_complete=on_complete,
        )

    def _prepare_modal_for_animation(self, modal, animation):
        modal.configure(width=animation["width"], height=animation["height"])
        modal.place(x=-10000, y=-10000, anchor="nw")
        modal.update_idletasks()

    def _close_simple_modal_with_animation(self, modal, on_complete=None):
        if self._modal_is_closing:
            return False

        self._modal_is_closing = True

        def finish():
            try:
                if modal and modal.winfo_exists():
                    modal.destroy()
            finally:
                self._hide_modal_layer()
                if on_complete:
                    on_complete()

        if modal and modal.winfo_exists():
            animate_modal_close(modal, on_complete=finish)
        else:
            finish()
        return True

    def _handle_modal_background_click(self, _event=None):
        if self._modal_is_closing:
            return "break"
        if self._active_modal_close_callback:
            self._active_modal_close_callback()
            return "break"
        return None

    def _handle_modal_escape(self, _event=None):
        if self._modal_is_closing:
            return "break"
        if self.modal_layer and self.modal_layer.winfo_ismapped() and self._active_modal_close_callback:
            self._active_modal_close_callback()
            return "break"
        return None

    def _build_user_nav(self):
        user = get_current_user()
        self.user_menu_visible = False
        self.active_user_button = ctk.CTkButton(
            self.nav_rail,
            text=f"{user.display_name}\nConta local",
            height=46,
            command=self._show_user_menu,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
            font=("Segoe UI Semibold", 11),
        )
        self.active_user_button.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 8))

        self.user_menu_frame = ctk.CTkFrame(
            self.nav_rail,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.user_menu_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.user_menu_frame,
            text="Conta",
            font=("Segoe UI Semibold", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(9, 4))

        self.logout_button = ctk.CTkButton(
            self.user_menu_frame,
            text="Sair da conta",
            command=self._logout_to_login,
            height=32,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
            font=("Segoe UI", 11),
        )
        self.logout_button.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

    def _show_user_menu(self):
        if self.user_menu_visible:
            self._hide_user_menu()
            return

        self.user_menu_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.user_menu_visible = True

    def _hide_user_menu(self):
        if getattr(self, "user_menu_visible", False):
            self.user_menu_frame.grid_forget()
            self.user_menu_visible = False

    def _logout_to_login(self):
        self._hide_user_menu()
        clear_session()
        self._show_auth_screen(create_mode=False)

    def _build_navigation(self):
        nav_items = [
            ("home", "Home"),
            ("library", "Coleções"),
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
            button.grid(row=index + 2, column=0, sticky="ew", padx=8, pady=(4, 0))
            self.nav_buttons[page_name] = button

    def _build_pages(self):
        self.pages = {}
        for page_name in ("home", "library", "game", "mods", "settings"):
            page = ctk.CTkFrame(self.page_host, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(0, weight=1)
            self.pages[page_name] = page

        self._build_home_page()
        self._build_library_page()
        self._build_game_page()
        self._build_placeholder_page(
            "mods",
            "Mods",
            "Estrutura preparada para gerenciamento de mods futuramente.",
        )
        self._build_placeholder_page(
            "settings",
            "Config",
            "Estrutura preparada para configurações avançadas futuramente.",
        )
        self._show_page("home")

    def _navigate(self, page_name):
        if page_name == "game" and not self.current_game:
            self._set_status("Selecione um jogo nas Coleções primeiro.", "info")
            page_name = "library"

        self._show_page(page_name)
        if page_name == "library" and hasattr(self, "library_game_page"):
            self._show_library_collection()

    def _show_page(self, page_name):
        self.current_page = page_name
        for name, button in getattr(self, "nav_buttons", {}).items():
            active = name == page_name
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

    def _build_placeholder_page(self, page_name, title, description):
        if self._page_built.get(page_name):
            return

        page = self.pages[page_name]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(
            page,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI Bold", 24),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        ctk.CTkLabel(
            card,
            text=description,
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))

        self._page_built[page_name] = True

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
        hero.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            hero,
            text="Continuar jogando",
            font=("Segoe UI Bold", 28),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))

        self.home_current_game = ctk.CTkLabel(
            hero,
            text="Escolha um jogo nas Coleções para preparar seus saves.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.home_current_game.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        self.home_play_button = ctk.CTkButton(
            hero,
            text="Jogar",
            command=self._play_current_game_placeholder,
            width=170,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            state="disabled",
        )
        self.home_play_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(8, 18), pady=14)

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
        self.library_list_panel.grid(row=6, column=0, sticky="nsew", padx=6, pady=(10, 6))
        self.library_list_panel.grid_columnconfigure(0, weight=1)
        self.library_list_panel.grid_rowconfigure(2, weight=1)

        self.library_top = ctk.CTkFrame(self.library_list_panel, fg_color="transparent")
        self.library_top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.library_top.grid_columnconfigure(0, weight=1)
        self.library_top.grid_columnconfigure(1, weight=0)

        title_block = ctk.CTkFrame(self.library_top, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="ew", padx=(0, 8))
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

        self.sidebar_add_game_button = ctk.CTkButton(
            self.library_top,
            text="+",
            width=28,
            height=26,
            corner_radius=8,
            command=self._open_game_manager,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=ACCENT_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            font=("Segoe UI Semibold", 15),
        )
        self.sidebar_add_game_button.grid(row=0, column=1, sticky="ne", pady=(1, 0))

        self.library_filter_frame = ctk.CTkFrame(self.library_top, fg_color="transparent")
        self.library_filter_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
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

        self.collections_top = ctk.CTkFrame(self.library_game_page, fg_color="transparent")
        self.collections_top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.collections_top.grid_columnconfigure(0, weight=1)

        title_stack = ctk.CTkFrame(self.collections_top, fg_color="transparent")
        title_stack.grid(row=0, column=0, sticky="ew", padx=(2, 12))
        title_stack.grid_columnconfigure(0, weight=1)

        self.library_game_context_label = ctk.CTkLabel(
            title_stack,
            text="Coleções",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.library_game_context_label.grid(row=0, column=0, sticky="ew")

        self.collection_meta_label = ctk.CTkLabel(
            title_stack,
            text="Organize seus jogos em grupos pessoais",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.collection_meta_label.grid(row=1, column=0, sticky="ew", pady=(1, 0))

        self.add_collection_button = ctk.CTkButton(
            self.collections_top,
            text="+",
            width=34,
            height=30,
            command=self._show_create_collection_modal,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=ACCENT_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            font=("Segoe UI Semibold", 16),
        )
        self.add_collection_button.grid(row=0, column=1, rowspan=2, sticky="e")

        self.collection_grid_frame = ctk.CTkScrollableFrame(
            self.library_game_page,
            fg_color=APP_BACKGROUND,
            corner_radius=0,
            border_width=0,
        )
        self.collection_grid_frame.grid(row=1, column=0, sticky="nsew")
        self.collection_grid_frame.grid_columnconfigure(0, weight=1)
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
        self.left_panel.grid_rowconfigure(4, weight=0)

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
        self.selected_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 10))
        self.selected_card.grid_columnconfigure(0, weight=2)
        self.selected_card.grid_columnconfigure(1, weight=1)
        self.selected_card.grid_columnconfigure(2, weight=0)
        self.selected_card.grid_columnconfigure(3, weight=0)
        self.selected_card.grid_columnconfigure(4, weight=0)
        self.selected_card.grid_columnconfigure(5, weight=0)

        self.game_panel_title = ctk.CTkLabel(
            self.selected_card,
            text="Nenhum jogo",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.game_panel_title.grid(row=0, column=0, sticky="ew", padx=(16, 10), pady=(10, 2))

        self.selected_value = ctk.CTkLabel(
            self.selected_card,
            text="Perfil: nenhum",
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.selected_value.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 10))

        self.selected_hint = ctk.CTkLabel(
            self.selected_card,
            text="",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.selected_hint.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 10))

        self.play_button = ctk.CTkButton(
            self.selected_card,
            text="Jogar",
            command=self._play_current_game_placeholder,
            height=32,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.play_button.grid(row=0, column=2, rowspan=2, sticky="ew", padx=5, pady=10)

        self.quick_save_button = ctk.CTkButton(
            self.selected_card,
            text="Saves",
            command=self._toggle_game_saves_view,
            height=32,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.quick_save_button.grid(row=0, column=3, rowspan=2, sticky="ew", padx=5, pady=10)

        self.load_profile_button = ctk.CTkButton(
            self.selected_card,
            text="Abrir pastas",
            command=self._open_current_game_paths,
            height=32,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.load_profile_button.grid(row=0, column=4, rowspan=2, sticky="ew", padx=5, pady=10)

        self.more_actions_button = ctk.CTkButton(
            self.selected_card,
            text="Gerenciar jogo",
            command=self._open_current_game_in_manager,
            height=32,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.more_actions_button.grid(row=0, column=5, rowspan=2, sticky="ew", padx=(5, 14), pady=10)

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
        self.game_overview.grid_columnconfigure(2, weight=1)

        self.game_context_active_profile = self._build_game_context_tile(
            self.game_overview,
            0,
            0,
            "Perfil ativo",
            "Nenhum",
        )
        self.game_context_saves = self._build_game_context_tile(
            self.game_overview,
            0,
            1,
            "Saves",
            "0 perfis",
        )
        self.game_context_paths = self._build_game_context_tile(
            self.game_overview,
            0,
            2,
            "Diretórios",
            "0 pastas",
        )
        self.game_context_launch = self._build_launch_context_tile(
            self.game_overview,
            1,
            0,
        )
        self.game_context_backup = self._build_game_context_tile(
            self.game_overview,
            1,
            1,
            "Último backup",
            "Sob demanda",
        )
        self.game_context_mods = self._build_game_context_tile(
            self.game_overview,
            1,
            2,
            "Mods",
            "Não configurado",
        )

    def _build_game_context_tile(self, master, row, column, title, value):
        tile = ctk.CTkFrame(
            master,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        tile.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(14 if column == 0 else 7, 14 if column == 2 else 7),
            pady=(14 if row == 0 else 0, 10),
        )
        tile.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tile,
            text=title,
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 1))
        value_label = ctk.CTkLabel(
            tile,
            text=value,
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=260,
        )
        value_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        return value_label

    def _build_launch_context_tile(self, master, row, column):
        tile = ctk.CTkFrame(
            master,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        tile.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(14 if column == 0 else 7, 14 if column == 2 else 7),
            pady=(14 if row == 0 else 0, 10),
        )
        tile.grid_columnconfigure(0, weight=1)
        tile.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            tile,
            text="Inicialização",
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=(12, 4), pady=(10, 1))

        admin_icon = tk.Canvas(
            tile,
            width=16,
            height=16,
            highlightthickness=0,
            bd=0,
            bg=self._theme_value(SURFACE_PRIMARY),
        )
        admin_icon.grid(row=0, column=1, sticky="e", padx=(4, 12), pady=(10, 1))
        self._draw_uac_shield_icon(admin_icon)
        admin_icon.grid_remove()

        executable_label = ctk.CTkLabel(
            tile,
            text="Não configurada",
            font=("Segoe UI Semibold", 12),
            text_color=TEXT_PRIMARY,
            anchor="w",
            justify="left",
            wraplength=240,
        )
        executable_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 1))

        arguments_label = ctk.CTkLabel(
            tile,
            text="Inicialização padrão",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=240,
        )
        arguments_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

        return {
            "file": executable_label,
            "args": arguments_label,
            "admin": admin_icon,
        }

    def _theme_value(self, color):
        if isinstance(color, tuple):
            return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
        return color

    def _draw_uac_shield_icon(self, canvas):
        canvas.delete("all")
        canvas.configure(bg=self._theme_value(SURFACE_PRIMARY))
        canvas.create_polygon(8, 1, 2, 3, 2, 7, 8, 7, fill="#5f8edb", outline="")
        canvas.create_polygon(8, 1, 14, 3, 14, 7, 8, 7, fill="#263143", outline="")
        canvas.create_polygon(2, 7, 8, 7, 8, 15, 5, 13, 3, 10, fill="#263143", outline="")
        canvas.create_polygon(8, 7, 14, 7, 13, 10, 11, 13, 8, 15, fill="#8fb4f5", outline="")
        canvas.create_line(8, 1, 8, 15, fill="#344057", width=1)
        canvas.create_line(2, 7, 14, 7, fill="#344057", width=1)
        canvas.create_polygon(
            8, 1,
            14, 3,
            14, 7,
            13, 10,
            11, 13,
            8, 15,
            5, 13,
            3, 10,
            2, 7,
            2, 3,
            fill="",
            outline="#4b5870",
            width=1,
        )

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
            text="Coleções",
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
            text="Coleções prontas para organizar seus jogos.",
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
            "Escolha um jogo nas Coleções para ver seus perfis.",
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
            return

        self._prepare_modal_layer(self._close_more_actions_modal)
        modal = self._create_internal_modal_panel(
            width=380,
            height=430,
            fg_color=SURFACE_SECONDARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
            y=76,
            anchor="n",
        )
        self.more_actions_modal = modal
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
                    self._close_more_actions_modal(on_complete=callback)
                else:
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
            command=self._close_more_actions_modal,
            height=36,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        ).grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        self._animate_internal_modal_open(modal)

    def _close_more_actions_modal(self, on_complete=None):
        modal = getattr(self, "more_actions_modal", None)
        self._close_simple_modal_with_animation(modal, on_complete=on_complete)

    def _load_selected_profile(self):
        if not self.selected_profile:
            self._set_status("Selecione um perfil para carregar.", "info")
            return
        self._activate_profile(self.selected_profile)

    def _get_sorted_games(self, query=""):
        return listar_nomes_jogos(query)

    def _get_library_query(self):
        return self.library_search.get().strip() if hasattr(self, "library_search") else ""

    def _game_card_signature(self, game, profile_count):
        return (
            game.name,
            bool(game.favorite),
            game.cover_path or "",
            game.banner_path or "",
            tuple(game.save_paths or ()),
            profile_count,
        )

    def _get_reusable_game_card(self, cards, signatures, key, signature):
        card = cards.get(key)
        if card and card.winfo_exists() and signatures.get(key) == signature:
            return card

        if card and card.winfo_exists():
            card.destroy()
        cards.pop(key, None)
        signatures.pop(key, None)
        return None

    def _remember_game_card_signature(self, signatures, key, signature):
        signatures[key] = signature

    def _prune_missing_game_cards(self, cards, signatures, valid_keys):
        for key in list(cards):
            if key in valid_keys:
                continue
            card = cards.pop(key, None)
            signatures.pop(key, None)
            if card and card.winfo_exists():
                card.destroy()

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

        for card in self.library_cards.values():
            if card.winfo_exists():
                card.grid_remove()
        if hasattr(self, "library_empty_state") and self.library_empty_state.winfo_exists():
            self.library_empty_state.grid_remove()

        if not games:
            if not hasattr(self, "library_empty_state") or not self.library_empty_state.winfo_exists():
                self.library_empty_state = ctk.CTkFrame(
                    self.game_library_frame,
                    fg_color="transparent",
                )
                self.library_empty_title = ctk.CTkLabel(
                    self.library_empty_state,
                    text="",
                    font=("Segoe UI Bold", 22),
                    text_color=TEXT_PRIMARY,
                    anchor="w",
                )
                self.library_empty_title.grid(row=0, column=0, sticky="w")
                self.library_empty_description = ctk.CTkLabel(
                    self.library_empty_state,
                    text="",
                    font=("Segoe UI", 13),
                    text_color=TEXT_SECONDARY,
                    anchor="w",
                )
                self.library_empty_description.grid(row=1, column=0, sticky="w", pady=(6, 14))
                self.library_empty_manage_button = ctk.CTkButton(
                    self.library_empty_state,
                    text="Gerenciar jogos",
                    command=self._open_game_manager,
                    width=140,
                    height=38,
                    fg_color=ACCENT_COLOR,
                    hover_color=ACCENT_HOVER,
                )
                self.library_empty_manage_button.grid(row=2, column=0, sticky="w")

            self.library_empty_state.grid(row=0, column=0, sticky="nsew", padx=24, pady=28)
            self.library_empty_title.configure(
                text=(
                    "Nenhum favorito ainda"
                    if self.library_filter == "favorites"
                    else ("Nenhum jogo cadastrado" if not query else "Nenhum jogo encontrado")
                )
            )
            self.library_empty_description.configure(
                text=(
                    "Marque uma estrela nos cards para fixar jogos aqui."
                    if self.library_filter == "favorites"
                    else ("Cadastre jogos para montar sua coleção." if not query else "Tente outro termo de busca.")
                )
            )
            if not query and self.library_filter == "all":
                self.library_empty_manage_button.grid()
            else:
                self.library_empty_manage_button.grid_remove()
            return

        self._prune_missing_game_cards(
            self.library_cards,
            self.library_card_signatures,
            {game.name for game in games},
        )
        for index, game in enumerate(games):
            profile_count = get_profile_count(game.name)
            signature = self._game_card_signature(game, profile_count)
            card = self._get_reusable_game_card(
                self.library_cards,
                self.library_card_signatures,
                game.name,
                signature,
            )
            if not card or not card.winfo_exists():
                card = GameLibraryListItem(
                    self.game_library_frame,
                    game=game,
                    selected=game.name == self.sidebar_selected_game,
                    on_select=self._select_game_from_card,
                    on_open=self._open_game_from_card,
                    on_favorite=self._toggle_favorite_from_card,
                    profile_count=profile_count,
                )
                self.library_cards[game.name] = card
                self._remember_game_card_signature(self.library_card_signatures, game.name, signature)
            else:
                card.game = game
                card.profile_count = profile_count
                card.set_favorite(game.favorite)
                card.set_selected(game.name == self.sidebar_selected_game)
                self._remember_game_card_signature(self.library_card_signatures, game.name, signature)
            card.grid(row=index, column=0, sticky="ew", padx=3, pady=(4 if index == 0 else 2, 2))

    def _refresh_library_collection(self):
        self._refresh_game_selector()
        self._refresh_collection_grid()

    def _refresh_collection_grid(self):
        if not hasattr(self, "collection_grid_frame"):
            return

        self._hide_collection_widgets()

        if self.open_collection_id:
            self._render_open_user_collection()
            return

        collections_view = get_collections_overview()
        self.library_game_context_label.configure(text=collections_view.title)
        self.collection_meta_label.configure(text=collections_view.meta_text)

        if collections_view.is_empty:
            self._show_collection_empty()
            return

        for index, collection in enumerate(collections_view.collections):
            card = self.user_collection_cards.get(collection.id)
            if not card or not card.winfo_exists():
                card = self._build_user_collection_card(collection)
                self.user_collection_cards[collection.id] = card
            else:
                card.title_label.configure(text=collection.name)
                card.count_label.configure(text=f"{collection.game_count} jogo(s)")
            card.grid(row=index, column=0, sticky="ew", padx=8, pady=(8 if index == 0 else 4, 4))

    def _hide_collection_widgets(self):
        for card in self.user_collection_cards.values():
            if card.winfo_exists():
                card.grid_remove()
        for card in self.open_collection_game_cards.values():
            if card.winfo_exists():
                card.grid_remove()
        for widget in (
            self.collection_empty_card,
            self.open_collection_back_row,
            self.open_collection_empty_label,
        ):
            if widget and widget.winfo_exists():
                widget.grid_remove()

    def _show_collection_empty(self):
        if not self.collection_empty_card or not self.collection_empty_card.winfo_exists():
            empty = ctk.CTkFrame(
                self.collection_grid_frame,
                fg_color=SURFACE_PRIMARY,
                corner_radius=14,
                border_width=1,
                border_color=BORDER_COLOR,
            )
            empty.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                empty,
                text="Nenhuma coleção ainda",
                font=("Segoe UI Bold", 18),
                text_color=TEXT_PRIMARY,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
            ctk.CTkLabel(
                empty,
                text="Use o botão + para criar sua primeira coleção.",
                font=("Segoe UI", 12),
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
            self.collection_empty_card = empty
        self.collection_empty_card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

    def _build_user_collection_card(self, collection):
        card = ctk.CTkFrame(
            self.collection_grid_frame,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        card.title_label = ctk.CTkLabel(
            card,
            text=collection.name,
            font=("Segoe UI Semibold", 15),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        card.title_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))

        card.count_label = ctk.CTkLabel(
            card,
            text=f"{collection.game_count} jogo(s)",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        card.count_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        ctk.CTkButton(
            card,
            text="Abrir",
            width=82,
            height=30,
            command=lambda collection_id=collection.id: self._open_user_collection(collection_id),
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=14, pady=12)
        return card

    def _render_open_user_collection(self):
        collection_view = get_open_collection_view(self.open_collection_id)
        if not collection_view:
            self.open_collection_id = ""
            self._refresh_collection_grid()
            return

        self.library_game_context_label.configure(text=collection_view.name)
        self.collection_meta_label.configure(text=collection_view.meta_text)

        if not self.open_collection_back_row or not self.open_collection_back_row.winfo_exists():
            self.open_collection_back_row = ctk.CTkFrame(self.collection_grid_frame, fg_color="transparent")
            ctk.CTkButton(
                self.open_collection_back_row,
                text="Voltar para Coleções",
                width=150,
                height=30,
                command=self._close_user_collection,
                fg_color=SURFACE_SECONDARY,
                hover_color=SURFACE_TERTIARY,
                text_color=TEXT_PRIMARY,
                border_width=1,
                border_color=BORDER_COLOR,
            ).grid(row=0, column=0, sticky="w")
        self.open_collection_back_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 10))

        if collection_view.is_empty:
            if not self.open_collection_empty_label or not self.open_collection_empty_label.winfo_exists():
                self.open_collection_empty_label = ctk.CTkLabel(
                    self.collection_grid_frame,
                    text="Esta coleção ainda está vazia.",
                    font=("Segoe UI", 13),
                    text_color=TEXT_SECONDARY,
                    anchor="w",
                )
            self.open_collection_empty_label.grid(row=1, column=0, sticky="ew", padx=12, pady=18)
            return

        visible_games = collection_view.games
        self._prune_missing_game_cards(
            self.open_collection_game_cards,
            self.open_collection_game_card_signatures,
            {game.name for game in visible_games},
        )
        row = 1
        for game in visible_games:
            profile_count = get_profile_count(game.name)
            signature = self._game_card_signature(game, profile_count)
            card = self._get_reusable_game_card(
                self.open_collection_game_cards,
                self.open_collection_game_card_signatures,
                game.name,
                signature,
            )
            if not card or not card.winfo_exists():
                card = GameLibraryCard(
                    self.collection_grid_frame,
                    game=game,
                    selected=False,
                    on_select=self._open_game_from_collection,
                    on_open=self._open_game_from_collection,
                    on_favorite=self._toggle_favorite_from_card,
                    profile_count=profile_count,
                )
                self.open_collection_game_cards[game.name] = card
                self._remember_game_card_signature(self.open_collection_game_card_signatures, game.name, signature)
            else:
                card.game = game
                card.profile_count = profile_count
                card.set_favorite(game.favorite)
                card.set_selected(False)
                self._remember_game_card_signature(self.open_collection_game_card_signatures, game.name, signature)
            card.grid(row=row, column=0, sticky="w", padx=8, pady=6)
            row += 1

    def _open_user_collection(self, collection_id):
        self.open_collection_id = collection_id
        self._refresh_collection_grid()

    def _close_user_collection(self):
        self.open_collection_id = ""
        self._refresh_collection_grid()

    def _show_create_collection_modal(self):
        if hasattr(self, "create_collection_modal") and self.create_collection_modal.winfo_exists():
            self.create_collection_modal.lift()
            self.create_collection_name_entry.focus_set()
            return

        self._prepare_modal_layer(self._close_create_collection_modal)
        self.create_collection_modal = self._create_internal_modal_panel(
            width=390,
            height=260,
            fg_color=SURFACE_PRIMARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.create_collection_modal.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(
            self.create_collection_modal,
            fg_color="transparent",
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text="Criar coleção",
            font=("Segoe UI Bold", 18),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        self.create_collection_name_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Nome da coleção",
            height=36,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.create_collection_name_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.create_collection_name_entry.bind("<Return>", lambda _event: self._create_collection_from_modal())

        self.create_collection_error_label = ctk.CTkLabel(
            frame,
            text="",
            font=("Segoe UI", 11),
            text_color=ERROR_COLOR,
            anchor="w",
        )
        self.create_collection_error_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Criar",
            command=self._create_collection_from_modal,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Cancelar",
            command=self._close_create_collection_modal,
            height=34,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.create_collection_modal.lift()
        self._animate_internal_modal_open(
            self.create_collection_modal,
            on_complete=self._focus_create_collection_name,
        )

    def _close_create_collection_modal(self):
        modal = getattr(self, "create_collection_modal", None)
        self._close_simple_modal_with_animation(modal)

    def _focus_create_collection_name(self):
        if not (
            hasattr(self, "create_collection_modal")
            and self.create_collection_modal.winfo_exists()
            and hasattr(self, "create_collection_name_entry")
        ):
            return
        self.create_collection_modal.lift()
        self.create_collection_name_entry.focus_set()
        self.create_collection_name_entry.select_range(0, "end")
        self.create_collection_name_entry.icursor("end")

    def _create_collection_from_modal(self):
        name = self.create_collection_name_entry.get() if hasattr(self, "create_collection_name_entry") else ""
        try:
            collection = create_collection(name)
        except CollectionError as exc:
            self.create_collection_error_label.configure(text=str(exc))
            return

        self.open_collection_id = collection.id
        self._close_create_collection_modal()
        self._refresh_collection_grid()

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

        all_games = listar_jogos_biblioteca("")
        favorites = [game for game in all_games if game.favorite][:8]
        recents = listar_jogos_recentes_biblioteca()[:8]

        self._populate_home_shelf(self.home_favorites_frame, favorites, "Nenhum favorito ainda.", "favorites")
        self._populate_home_shelf(self.home_recents_frame, recents, "Nenhum jogo recente ainda.", "recents")

    def _populate_home_shelf(self, frame, games, empty_text, shelf_key):
        shelf_cards = self.home_shelf_cards.setdefault(shelf_key, {})
        shelf_signatures = self.home_shelf_card_signatures.setdefault(shelf_key, {})
        for card in shelf_cards.values():
            if card.winfo_exists():
                card.grid_remove()

        empty_label = self.home_shelf_empty_labels.get(shelf_key)
        if empty_label and empty_label.winfo_exists():
            empty_label.grid_remove()

        if not games:
            self._prune_missing_game_cards(shelf_cards, shelf_signatures, set())
            if not empty_label or not empty_label.winfo_exists():
                empty_label = ctk.CTkLabel(
                    frame,
                    text=empty_text,
                    font=("Segoe UI", 13),
                    text_color=TEXT_SECONDARY,
                    anchor="w",
                )
                self.home_shelf_empty_labels[shelf_key] = empty_label
            empty_label.configure(text=empty_text)
            empty_label.grid(row=0, column=0, sticky="w", padx=16, pady=18)
            return

        self._prune_missing_game_cards(shelf_cards, shelf_signatures, {game.name for game in games})
        for index, game in enumerate(games):
            profile_count = get_profile_count(game.name)
            signature = self._game_card_signature(game, profile_count)
            card = self._get_reusable_game_card(
                shelf_cards,
                shelf_signatures,
                game.name,
                signature,
            )
            if not card or not card.winfo_exists():
                card = GameLibraryCard(
                    frame,
                    game=game,
                    selected=game.name == self.current_game,
                    on_select=self._open_game_from_home,
                    on_open=self._open_game_from_home,
                    on_favorite=self._toggle_favorite_from_card,
                    profile_count=profile_count,
                    compact=True,
                )
                shelf_cards[game.name] = card
                self._remember_game_card_signature(shelf_signatures, game.name, signature)
            else:
                card.game = game
                card.profile_count = profile_count
                card.set_favorite(game.favorite)
                card.set_selected(game.name == self.current_game)
                self._remember_game_card_signature(shelf_signatures, game.name, signature)
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
            self.open_collection_id = ""
            self.library_game_context_label.configure(text="Coleções")
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

    def _toggle_game_saves_view(self):
        if self.game_tool_mode == "saves":
            self._show_game_overview()
        else:
            self._show_game_saves()

    def _sync_game_page_mode(self):
        if not hasattr(self, "game_overview"):
            return

        showing_saves = self.game_tool_mode == "saves"
        if showing_saves:
            self.left_panel.grid_rowconfigure(1, weight=0)
            self.left_panel.grid_rowconfigure(4, weight=1)
            self.game_overview.grid_remove()
            self.profile_header.grid()
            self.profile_search.grid()
            self.profile_list.grid()
            self._refresh_profiles()
        else:
            self.left_panel.grid_rowconfigure(1, weight=1)
            self.left_panel.grid_rowconfigure(4, weight=0)
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

        result = open_game_save_directories(self.current_game)
        self._refresh_home_shelves_if_visible()

        if result.opened_count:
            self._set_status(f"{result.opened_count} pasta(s) de '{self.current_game}' abertas.", "success")
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
            if hasattr(self, "game_context_active_profile"):
                self.game_context_active_profile.configure(text="Nenhum")
                self.game_context_saves.configure(text="0 perfis")
                self.game_context_paths.configure(text="0 pastas")
                self._update_launch_context_tile(None, False)
                self.game_context_backup.configure(text="Sem perfil ativo")
                self.game_context_mods.configure(text="Não configurado")
            if hasattr(self, "home_current_game"):
                self.home_current_game.configure(text="Escolha um jogo nas Coleções para preparar seus saves.")
            if hasattr(self, "home_play_button"):
                self.home_play_button.configure(text="Jogar", state="disabled")
            self.play_button.configure(state="disabled")
            self.quick_save_button.configure(state="disabled")
            self.load_profile_button.configure(state="disabled")
            self.more_actions_button.configure(state="disabled")
            return

        summary = get_game_context_summary(self.current_game)
        paths = tuple(paths) if paths is not None else summary.save_paths
        launch_config = summary.launch_config
        can_launch = summary.can_launch
        self.game_panel_title.configure(text=self.current_game)
        self.game_banner_label.configure(text=summary.initials)
        profile_total = summary.profile_total
        active_profile = summary.active_profile
        self.game_panel_meta.configure(text=f"{profile_total} perfil(is) · {len(paths)} diretório(s)")
        if hasattr(self, "game_context_active_profile"):
            launch_name = Path(launch_config.get("executable_path") or "").name
            self.game_context_active_profile.configure(text=active_profile or "Nenhum")
            self.game_context_saves.configure(text=f"{profile_total} perfil(is)")
            self.game_context_paths.configure(text=f"{len(paths)} pasta(s)")
            self._update_launch_context_tile(launch_config, can_launch)
            self.game_context_backup.configure(text=active_profile or "Sem perfil ativo")
            self.game_context_mods.configure(text="Não configurado")
        if hasattr(self, "home_current_game"):
            self.home_current_game.configure(text=f"{self.current_game} pronto para gerenciar saves.")
        if hasattr(self, "home_play_button"):
            self.home_play_button.configure(
                text="Jogar" if can_launch else "Configurar inicialização",
                state="normal",
            )
        self.play_button.configure(
            text="Jogar" if can_launch else "Configurar inicialização",
            state="normal",
        )
        self.quick_save_button.configure(
            text="Saves",
            state="normal",
            fg_color=ACCENT_COLOR if self.game_tool_mode == "saves" else SURFACE_PRIMARY,
            hover_color=ACCENT_HOVER if self.game_tool_mode == "saves" else SURFACE_TERTIARY,
            border_color=ACCENT_COLOR if self.game_tool_mode == "saves" else BORDER_COLOR,
        )
        self.load_profile_button.configure(state="normal")
        self.more_actions_button.configure(state="normal")

    def _update_launch_context_tile(self, launch_config, can_launch):
        if not hasattr(self, "game_context_launch"):
            return

        launch_config = launch_config or {}
        executable_path = str(launch_config.get("executable_path") or "")
        arguments = str(launch_config.get("launch_arguments") or "")
        launch_as_admin = bool(launch_config.get("launch_as_admin", False))

        file_label = self.game_context_launch["file"]
        args_label = self.game_context_launch["args"]
        admin_label = self.game_context_launch["admin"]

        if not can_launch:
            file_label.configure(text="Não configurada", text_color=TEXT_SECONDARY)
            args_label.configure(text="Inicialização padrão", text_color=TEXT_SECONDARY)
            admin_label.grid_remove()
            return

        file_label.configure(text=Path(executable_path).name, text_color=TEXT_PRIMARY)
        args_label.configure(
            text=arguments if arguments else "Sem argumentos",
            text_color=TEXT_SECONDARY,
        )
        if launch_as_admin:
            self._draw_uac_shield_icon(admin_label)
            admin_label.grid()
        else:
            admin_label.grid_remove()

    def _play_current_game_placeholder(self):
        if not self.current_game:
            self._set_status("Abra um jogo antes de clicar em Jogar.", "info")
            return

        summary = get_game_context_summary(self.current_game)
        launch_config = summary.launch_config
        if not summary.can_launch:
            executable_path = str(launch_config.get("executable_path") or "").strip()
            if executable_path:
                self._set_status("Arquivo de inicialização não encontrado.", "error")
            else:
                self._set_status("Configure um arquivo de inicialização para este jogo.", "info")
            self._open_current_game_in_manager()
            return

        self._set_status(f"Iniciando '{self.current_game}'...", "info")
        result = execute_launch_config(launch_config)
        if result.success:
            self._set_status(f"'{self.current_game}' iniciado.", "success")
        else:
            self._set_status(result.message, result.level)

    def _refresh_profiles(self):
        for card in self.profile_cards.values():
            if card.winfo_exists():
                card.grid_remove()
        if self.profile_empty_label and self.profile_empty_label.winfo_exists():
            self.profile_empty_label.grid_remove()

        query = self.profile_search.get() if self.current_game else ""
        profiles_view = get_save_profiles_view(self.current_game, query, self.selected_profile)
        self.profile_count_label.configure(text=profiles_view.count_text)
        self._update_selected_profile(profiles_view.selected_profile)

        if not self.current_game or profiles_view.is_empty:
            self._show_profile_empty(profiles_view.empty_message)
            self._bind_profile_mousewheel()
            return

        for index, profile in enumerate(profiles_view.filtered_profiles):
            card = self.profile_cards.get(profile.name)
            if not card or not card.winfo_exists():
                card = ProfileCard(
                    self.profile_list,
                    profile_name=profile.name,
                    active=profile.active,
                    on_activate=self._activate_profile,
                )
                self.profile_cards[profile.name] = card
            else:
                card.set_active(profile.active)
            card.grid(row=index, column=0, sticky="ew", padx=14, pady=10)
        self._bind_profile_mousewheel()

    def _show_profile_empty(self, text):
        if not self.profile_empty_label or not self.profile_empty_label.winfo_exists():
            self.profile_empty_label = ctk.CTkLabel(
                self.profile_list,
                text=text,
                text_color=TEXT_SECONDARY,
                anchor="w",
                justify="left",
            )
        self.profile_empty_label.configure(text=text)
        self.profile_empty_label.grid(row=0, column=0, sticky="ew", padx=18, pady=18)

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
        active_profile = get_active_save_profile(self.current_game) if self.current_game else None
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
        for shelf_cards in self.home_shelf_cards.values():
            shelf_card = shelf_cards.get(game_name)
            if shelf_card and shelf_card.winfo_exists():
                shelf_card.set_favorite(favorite)

        favorite_total = len([game for game in listar_jogos_biblioteca("") if game.favorite])
        self._update_library_filter_buttons(favorite_total)

    def _open_game_manager(self):
        if self.busy:
            return

        self._prebuild_game_manager_modal()
        if not (self.game_manager and self.game_manager.winfo_exists()):
            return

        self._prepare_modal_layer(self._close_game_manager_modal)
        self.game_manager_overlay = self.modal_layer
        self._build_game_manager_dim_background()

        selected_game = self._game_manager_initial_game or self.game_manager.selected_game
        self._game_manager_initial_game = None
        self.game_manager.refresh(selected_game=selected_game)
        self.after_idle(self._reveal_game_manager_modal)

    def _prebuild_game_manager_modal(self):
        if not self.modal_layer or not self.modal_layer.winfo_exists():
            return

        if self.game_manager and self.game_manager.winfo_exists():
            return

        self.game_manager_overlay = self.modal_layer
        self.game_manager_wrapper = ctk.CTkFrame(
            self.game_manager_overlay,
            width=MANAGER_MIN_WIDTH,
            height=MANAGER_MIN_HEIGHT,
            fg_color=GAME_MANAGER_OVERLAY_COLOR,
            bg_color=GAME_MANAGER_OVERLAY_COLOR,
            corner_radius=0,
            border_width=0,
        )
        self.game_manager_wrapper.grid_propagate(False)
        self.game_manager_wrapper.grid_columnconfigure(0, weight=1)
        self.game_manager_wrapper.grid_rowconfigure(0, weight=1)
        self.game_manager_wrapper.bind("<Button-1>", lambda _event: "break")

        self.game_manager = GameManagerWindow(
            self.game_manager_wrapper,
            dnd_context=self.dnd_context,
            list_games=lambda: self._get_sorted_games(""),
            get_paths_for_game=obter_diretorios_jogo,
            get_launch_config_for_game=obter_launch_config_jogo,
            on_save=self._save_game_from_manager,
            on_delete=self._delete_game_from_manager,
            on_close=self._close_game_manager_modal,
            overlay_color=GAME_MANAGER_OVERLAY_COLOR,
            auto_focus=False,
        )
        self.game_manager.grid(row=0, column=0, sticky="nsew")
        self.game_manager.update_idletasks()
        self.game_manager_wrapper.place_forget()
        self._persistent_modal_widgets.add(self.game_manager_wrapper)

    def _reveal_game_manager_modal(self):
        if not (
            self.game_manager_overlay
            and self.game_manager_overlay.winfo_exists()
            and self.game_manager_wrapper
            and self.game_manager_wrapper.winfo_exists()
            and self.game_manager
            and self.game_manager.winfo_exists()
        ):
            return

        self.game_manager_wrapper.configure(width=MANAGER_MIN_WIDTH, height=MANAGER_MIN_HEIGHT)
        self.game_manager.configure(width=MANAGER_MIN_WIDTH, height=MANAGER_MIN_HEIGHT)
        self.game_manager.grid(row=0, column=0, sticky="nsew")
        self.game_manager_wrapper.update_idletasks()
        self.game_manager.configure(width=MANAGER_MIN_WIDTH, height=MANAGER_MIN_HEIGHT)
        self.game_manager.lift()
        self.game_manager.update_idletasks()
        self._draw_game_manager_panel_background()
        self.game_manager_wrapper.configure(width=MANAGER_MIN_WIDTH, height=MANAGER_MIN_HEIGHT)
        self.game_manager_wrapper.place(relx=0.5, rely=0.5, x=0, y=0, anchor="center")
        self.game_manager_wrapper.lift()
        self.game_manager.lift()
        self._focus_game_manager_modal()

    def _focus_game_manager_modal(self):
        if not (self.game_manager and self.game_manager.winfo_exists()):
            return

        if self.game_manager_wrapper and self.game_manager_wrapper.winfo_exists():
            self.game_manager_wrapper.lift()
        self.game_manager.lift()
        self.game_manager.focus_set()
        if hasattr(self.game_manager, "name_field"):
            self.game_manager.name_field.focus()

    def _build_game_manager_dim_background(self):
        if not self.game_manager_overlay or not self.game_manager_overlay.winfo_exists():
            return

        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        try:
            self.game_manager_overlay.lower()
            self.update_idletasks()
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            dimmed = ImageEnhance.Brightness(screenshot).enhance(0.55)
            self._game_manager_overlay_image = ImageTk.PhotoImage(dimmed)
        except Exception:
            self._game_manager_overlay_image = None
        finally:
            self.game_manager_overlay.lift()

        background = tk.Canvas(
            self.game_manager_overlay,
            borderwidth=0,
            highlightthickness=0,
            bg=GAME_MANAGER_OVERLAY_COLOR,
        )
        self._game_manager_overlay_canvas = background
        background.place(x=0, y=0, relwidth=1, relheight=1)
        if self._game_manager_overlay_image:
            background.create_image(0, 0, image=self._game_manager_overlay_image, anchor="nw")
        background.bind("<Button-1>", self._handle_game_manager_overlay_click)

    def _draw_game_manager_panel_background(self):
        background = getattr(self, "_game_manager_overlay_canvas", None)
        if not background or not self.game_manager_overlay or not self.game_manager_overlay.winfo_exists():
            return

        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        panel_width = MANAGER_MIN_WIDTH + (GAME_MANAGER_PANEL_INSET * 2)
        panel_height = MANAGER_MIN_HEIGHT + (GAME_MANAGER_PANEL_INSET * 2)
        panel_x = max((width - panel_width) // 2, 0)
        panel_y = max((height - panel_height) // 2, 0)
        self._game_manager_panel_bounds = (
            panel_x,
            panel_y,
            panel_x + panel_width,
            panel_y + panel_height,
        )
        self._draw_rounded_panel(
            background,
            panel_x,
            panel_y,
            panel_x + panel_width,
            panel_y + panel_height,
            GAME_MANAGER_PANEL_RADIUS,
        )

    def _draw_rounded_panel(self, canvas, x1, y1, x2, y2, radius):
        fill = self._theme_color_value(SURFACE_PRIMARY)
        outline = self._theme_color_value(BORDER_COLOR)
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=1)

    def _theme_color_value(self, color):
        if isinstance(color, tuple):
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        return color

    def _handle_game_manager_overlay_click(self, event):
        x1, y1, x2, y2 = getattr(self, "_game_manager_panel_bounds", (0, 0, 0, 0))
        if x1 <= event.x <= x2 and y1 <= event.y <= y2:
            return "break"
        self._close_game_manager_modal()
        return "break"

    def _close_game_manager_modal(self):
        if self.game_manager and self.game_manager.winfo_exists():
            if hasattr(self.game_manager, "_autosave_now"):
                self.game_manager._autosave_now()
        if self.game_manager_wrapper and self.game_manager_wrapper.winfo_exists():
            self.game_manager_wrapper.place_forget()

        self._hide_modal_layer()
        self.game_manager_overlay = self.modal_layer

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

        active_profile = get_active_save_profile(self.current_game)
        if profile_name == active_profile:
            self._update_selected_profile(profile_name)
            self._set_status(f"O perfil '{profile_name}' já está ativo.", "info")
            return

        self._update_selected_profile(profile_name)
        self._run_operation(
            "Trocando os arquivos de save...",
            f"Perfil '{profile_name}' carregado com sucesso.",
            lambda progress: activate_save_profile(self.current_game, profile_name, progress_callback=progress),
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
            lambda progress: create_save_profile(self.current_game, profile_name, progress_callback=progress),
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
            lambda _progress: rename_save_profile(self.current_game, current_name, new_name),
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
            lambda progress: delete_save_profile(self.current_game, profile_name, progress_callback=progress),
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
            lambda progress: clear_current_save(self.current_game, progress_callback=progress),
            on_success=lambda _result: self._refresh_profiles(),
        )

    def _save_current_profile_snapshot(self):
        if not self.current_game:
            self._set_status("Selecione um jogo antes de salvar o save atual.", "error")
            return

        active_profile = get_active_save_profile(self.current_game)
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
            lambda progress: save_active_profile_snapshot(self.current_game, progress_callback=progress),
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
            lambda progress: export_current_save(
                self.current_game,
                destination_folder,
                progress_callback=progress,
            ),
            on_success=self._after_save_exported,
        )

    def _after_save_exported(self, export_path):
        self._set_status(f"Save atual exportado para: {export_path}", "success")

    def _save_game_from_manager(self, current_name, new_name, paths, launch_config):
        self._run_operation(
            "Salvando configuração do jogo...",
            f"Jogo '{new_name}' salvo com sucesso.",
            lambda _progress: salvar_jogo(current_name, new_name, paths, launch_config=launch_config),
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
        if not self.winfo_exists() or not getattr(self, "_main_initialized", False):
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
