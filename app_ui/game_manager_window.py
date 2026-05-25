import tkinter.messagebox as messagebox

import customtkinter as ctk

from app_ui.dnd_support import register_drop_target_tree
from app_ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    BORDER_COLOR,
    SURFACE_PRIMARY,
    SURFACE_SECONDARY,
    SURFACE_TERTIARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from app_ui.widgets import PathListEditor, ValidatedEntry
from core.validators import validate_game_name


class GameManagerWindow(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        dnd_context,
        list_games,
        get_paths_for_game,
        on_save,
        on_delete,
    ):
        super().__init__(master)
        self.withdraw()
        self._set_initial_alpha(0.0)
        self.master_window = master
        self.dnd_context = dnd_context
        self.list_games = list_games
        self.get_paths_for_game = get_paths_for_game
        self.on_save = on_save
        self.on_delete = on_delete
        self.selected_game = None
        self.game_buttons = {}
        self._compact_layout = False

        self.title("Gerenciar jogos")
        self.resizable(False, False)
        self.configure(fg_color=SURFACE_SECONDARY)
        self._ensure_dnd_for_window()

        self.shell = ctk.CTkFrame(
            self,
            fg_color=SURFACE_PRIMARY,
            corner_radius=22,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.shell.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.shell.grid_columnconfigure(0, weight=1)
        self.shell.grid_rowconfigure(1, weight=1)

        self._build_titlebar()

        self.body = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=2)
        self.body.grid_columnconfigure(1, weight=3)
        self.body.grid_rowconfigure(0, weight=1)

        self.grid_columnconfigure(0, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._build_game_list()
        self._build_editor()
        self.refresh()
        self._fit_to_master()
        self.bind("<Configure>", self._on_resize)
        self.after(90, self._show_when_ready)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _ensure_dnd_for_window(self):
        if not self.dnd_context:
            return

        try:
            import tkinter

            from app_ui.dnd_support import _DummyTix

            setattr(tkinter, "tix", _DummyTix)
            from tkinterdnd2 import TkinterDnD

            TkinterDnD._require(self)
        except Exception:
            pass

    def _register_window_drop_targets(self):
        if not self.winfo_exists() or not getattr(self, "paths_editor", None):
            return

        targets = (
            self,
            self.editor_scroll,
            self.paths_editor,
        )
        for target in targets:
            register_drop_target_tree(target, self.dnd_context, self.paths_editor.append_paths)
        self.paths_editor.refresh_drop_targets()

    def _build_titlebar(self):
        titlebar = ctk.CTkFrame(self.shell, fg_color="transparent")
        titlebar.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        titlebar.grid_columnconfigure(0, weight=1)

        title_block = ctk.CTkFrame(titlebar, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            title_block,
            text="Gerenciar jogos",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_block,
            text="Edite a biblioteca sem sair do launcher",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_game_list(self):
        self.left_panel = ctk.CTkFrame(
            self.body,
            fg_color=SURFACE_SECONDARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=0)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(2, weight=1)

        self.left_header = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.left_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.left_header.grid_columnconfigure(0, weight=1)
        self.left_header.grid_columnconfigure(1, weight=0)

        self.left_title = ctk.CTkLabel(
            self.left_header,
            text="Jogos cadastrados",
            font=("Segoe UI Bold", 18),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.left_title.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.new_button = ctk.CTkButton(
            self.left_header,
            text="+ Novo jogo",
            command=self.start_new_game,
            width=116,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.new_button.grid(row=0, column=1, sticky="e")

        self.search_entry = ctk.CTkEntry(
            self.left_panel,
            placeholder_text="Buscar jogo...",
            height=36,
            corner_radius=12,
            fg_color=SURFACE_PRIMARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh())

        self.game_list_frame = ctk.CTkScrollableFrame(
            self.left_panel,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=0,
        )
        self.game_list_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.game_list_frame.grid_columnconfigure(0, weight=1)

    def _build_editor(self):
        self.right_panel = ctk.CTkFrame(
            self.body,
            fg_color=SURFACE_SECONDARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=0)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(2, weight=1)

        self.title_label = ctk.CTkLabel(
            self.right_panel,
            text="Editor de jogo",
            font=("Segoe UI Bold", 18),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))

        self.mode_label = ctk.CTkLabel(
            self.right_panel,
            text="Modo: novo jogo",
            font=("Segoe UI Semibold", 13),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.mode_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        self.editor_scroll = ctk.CTkScrollableFrame(
            self.right_panel,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
        )
        self.editor_scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        self.editor_scroll.grid_columnconfigure(0, weight=1)

        self.form_card = ctk.CTkFrame(
            self.editor_scroll,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.form_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.form_card.grid_columnconfigure(0, weight=1)

        self.name_field = ValidatedEntry(
            self.form_card,
            label_text="Nome do jogo",
            placeholder_text="Ex.: Cyberpunk 2077",
            validator=validate_game_name,
        )
        self.name_field.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        self.name_field.entry.configure(height=36)
        self.name_field.error_label.configure(wraplength=480)

        self.paths_editor = PathListEditor(
            self.editor_scroll,
            dnd_context=self.dnd_context,
            textbox_height=112,
        )
        self.paths_editor.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            self.right_panel,
            text="Preencha os dados do jogo e salve as alterações.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
        )
        self.status_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 8))

        self.button_row = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.button_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 16))
        self.button_row.grid_columnconfigure(0, weight=1)
        self.button_row.grid_columnconfigure(1, weight=1)

        self.save_button = ctk.CTkButton(
            self.button_row,
            text="Adicionar jogo",
            command=self.save_game,
            height=38,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.save_button.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.delete_button = ctk.CTkButton(
            self.button_row,
            text="Excluir jogo",
            command=self.delete_game,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            height=38,
        )
        self.delete_button.grid(row=0, column=1, padx=(8, 0), sticky="ew")

    def refresh(self, selected_game=None):
        self.game_buttons = {}
        for widget in self.game_list_frame.winfo_children():
            widget.destroy()

        search = self.search_entry.get().strip().lower()
        games = self.list_games()
        filtered_games = [game for game in games if search in game.lower()]

        if not filtered_games:
            empty = ctk.CTkLabel(
                self.game_list_frame,
                text="Nenhum jogo encontrado.",
                text_color=TEXT_SECONDARY,
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=14, pady=14)
        else:
            for index, game in enumerate(filtered_games):
                button = ctk.CTkButton(
                    self.game_list_frame,
                    text=game,
                    command=lambda current=game: self.select_game(current),
                    height=40,
                    fg_color=SURFACE_PRIMARY,
                    hover_color=SURFACE_TERTIARY,
                    text_color=TEXT_PRIMARY,
                    border_width=1,
                    border_color=BORDER_COLOR,
                )
                button.grid(row=index, column=0, sticky="ew", padx=12, pady=8)
                self.game_buttons[game] = button

        if selected_game and selected_game in filtered_games:
            self.select_game(selected_game)
        elif self.selected_game in filtered_games:
            self.select_game(self.selected_game)
        elif filtered_games:
            self.select_game(filtered_games[0])
        else:
            self.start_new_game()

    def select_game(self, game):
        self.selected_game = game
        self.name_field.set(game)
        self.paths_editor.set_paths(self.get_paths_for_game(game))
        self.paths_editor.validate(show_error=True)
        self.status_label.configure(text=f"Editando '{game}'.")
        self.mode_label.configure(text=f"Modo: editando '{game}'")
        self.save_button.configure(text="Salvar alterações")
        self.delete_button.configure(state="normal")
        self._refresh_button_states()

    def start_new_game(self):
        self.selected_game = None
        self.name_field.clear()
        self.paths_editor.set_paths([])
        self.paths_editor.clear_feedback()
        self.status_label.configure(text="Modo de criação de novo jogo.")
        self.mode_label.configure(text="Modo: novo jogo")
        self.save_button.configure(text="Adicionar jogo")
        self.delete_button.configure(state="disabled")
        self._refresh_button_states()
        self.name_field.focus()

    def _refresh_button_states(self):
        for game, button in self.game_buttons.items():
            selected = game == self.selected_game
            button.configure(
                fg_color=("#dbeafe", "#1d4ed8") if selected else SURFACE_PRIMARY,
                text_color=TEXT_PRIMARY,
            )

    def save_game(self):
        valid_name = self.name_field.validate(show_error=True)
        valid_paths = self.paths_editor.validate(show_error=True)

        if not (valid_name and valid_paths):
            self.status_label.configure(
                text="Corrija os campos destacados antes de salvar.",
                text_color=("#dc2626", "#f87171"),
            )
            return

        self.on_save(
            self.selected_game,
            self.name_field.get(),
            self.paths_editor.get_paths(),
        )

    def delete_game(self):
        if not self.selected_game:
            return

        confirmed = messagebox.askyesno(
            "Excluir jogo",
            (
                f"Deseja excluir o jogo '{self.selected_game}'?\n\n"
                "Os perfis salvos e as configurações desse jogo também serão removidos."
            ),
            parent=self,
        )
        if confirmed:
            self.on_delete(self.selected_game)

    def show_error(self, title, message):
        self.status_label.configure(text=message, text_color=("#dc2626", "#f87171"))
        messagebox.showerror(title, message, parent=self)

    def set_interaction_enabled(self, enabled):
        state = "normal" if enabled else "disabled"

        self.search_entry.configure(state=state)
        self.name_field.entry.configure(state=state)
        self.paths_editor.textbox.configure(state=state)
        self.paths_editor.add_button.configure(state=state)
        self.paths_editor.open_button.configure(state=state)
        self.paths_editor.validate_button.configure(state=state)
        self.new_button.configure(state=state)
        self.save_button.configure(state=state)
        self.delete_button.configure(state=state if self.selected_game else "disabled")

        for button in self.game_buttons.values():
            button.configure(state=state)

    def _set_initial_alpha(self, value):
        try:
            self.attributes("-alpha", value)
        except Exception:
            pass

    def _show_when_ready(self):
        self._fit_to_master()
        if not self.winfo_exists():
            return

        self._stabilize_initial_layout()
        self._register_window_drop_targets()
        self.update_idletasks()
        self.deiconify()
        self.update_idletasks()
        self.lift()
        self.focus_set()
        self.name_field.focus()
        self.after(30, lambda: self._set_initial_alpha(1.0))

    def _stabilize_initial_layout(self):
        if not self.winfo_exists():
            return

        self.update_idletasks()
        self._sync_editor_scroll_width()
        self._reset_scroll_positions()
        self.update_idletasks()

    def _sync_editor_scroll_width(self):
        if not getattr(self, "editor_scroll", None) or not self.editor_scroll.winfo_exists():
            return

        canvas = getattr(self.editor_scroll, "_parent_canvas", None)
        if not canvas:
            return

        width = max(320, self.right_panel.winfo_width() - 20)
        canvas.configure(width=width)

    def _reset_scroll_positions(self):
        for frame in (getattr(self, "game_list_frame", None), getattr(self, "editor_scroll", None)):
            if not frame or not frame.winfo_exists():
                continue
            canvas = getattr(frame, "_parent_canvas", None)
            if canvas:
                canvas.yview_moveto(0)

    def _fit_to_master(self):
        master = self.master_window
        master.update_idletasks()
        screen_width, screen_height = self._get_screen_size()
        master_width = max(master.winfo_width(), 1000)
        master_height = max(master.winfo_height(), 680)
        width = min(max(920, int(screen_width * 0.78)), screen_width - 48)
        height = min(max(560, int(screen_height * 0.78)), screen_height - 64)
        x = master.winfo_rootx() + ((master_width - width) // 2)
        y = master.winfo_rooty() + ((master_height - height) // 2)
        x = max(16, min(x, screen_width - width - 16))
        y = max(16, min(y, screen_height - height - 48))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _get_screen_size(self):
        return self.winfo_screenwidth(), self.winfo_screenheight()

    def _handle_close(self):
        self.destroy()

    def _on_resize(self, _event=None):
        compact_layout = self.winfo_width() < 980
        if compact_layout == self._compact_layout:
            return

        self._compact_layout = compact_layout

        if compact_layout:
            self.left_panel.grid_configure(row=0, column=0, padx=0, pady=(0, 8), sticky="nsew")
            self.right_panel.grid_configure(row=1, column=0, padx=0, pady=(8, 0), sticky="nsew")
            self.body.grid_columnconfigure(0, weight=1)
            self.body.grid_columnconfigure(1, weight=0)
            self.body.grid_rowconfigure(0, weight=1)
            self.body.grid_rowconfigure(1, weight=2)
        else:
            self.left_panel.grid_configure(row=0, column=0, padx=(0, 7), pady=0, sticky="nsew")
            self.right_panel.grid_configure(row=0, column=1, padx=(7, 0), pady=0, sticky="nsew")
            self.body.grid_columnconfigure(0, weight=2)
            self.body.grid_columnconfigure(1, weight=3)
            self.body.grid_rowconfigure(0, weight=1)
            self.body.grid_rowconfigure(1, weight=0)
