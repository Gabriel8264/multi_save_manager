import tkinter.messagebox as messagebox

import customtkinter as ctk
import tkinter.filedialog as filedialog
from pathlib import Path

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
from core.launch_manager import validate_launch_config
from core.validators import validate_game_name


class GameManagerWindow(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        dnd_context,
        list_games,
        get_paths_for_game,
        get_launch_config_for_game,
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
        self.get_launch_config_for_game = get_launch_config_for_game
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
        self.shell.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.body.grid_columnconfigure(0, weight=2)
        self.body.grid_columnconfigure(1, weight=3)
        self.body.grid_rowconfigure(0, weight=1)

        self.grid_columnconfigure(0, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._build_game_list()
        self._build_editor()
        self.refresh()
        self.start_new_game()
        self._fit_to_master()
        self.bind("<Configure>", self._on_resize)
        self.after(90, self._show_when_ready)
        self.after(120, self._bind_mousewheel_scopes)
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
            self.right_panel,
            self.paths_editor,
        )
        for target in targets:
            register_drop_target_tree(target, self.dnd_context, self.paths_editor.append_paths)
        self.paths_editor.refresh_drop_targets()

    def _bind_mousewheel_scopes(self):
        if not self.winfo_exists():
            return

        self._bind_scrollable_mousewheel(self.game_list_frame)
        self._bind_textbox_mousewheel(self.paths_editor.textbox)

    def _bind_scrollable_mousewheel(self, scrollable):
        canvas = getattr(scrollable, "_parent_canvas", None)
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

        self._bind_mousewheel_tree(scrollable, on_mousewheel, on_button_4, on_button_5)
        self._bind_mousewheel_tree(canvas, on_mousewheel, on_button_4, on_button_5)

    def _bind_textbox_mousewheel(self, textbox):
        native_textbox = getattr(textbox, "_textbox", None)
        target = native_textbox or textbox

        def on_mousewheel(event):
            target.yview_scroll(self._mousewheel_units(event), "units")
            return "break"

        def on_button_4(_event):
            target.yview_scroll(-4, "units")
            return "break"

        def on_button_5(_event):
            target.yview_scroll(4, "units")
            return "break"

        self._bind_mousewheel_tree(textbox, on_mousewheel, on_button_4, on_button_5)
        if native_textbox:
            self._bind_mousewheel_tree(native_textbox, on_mousewheel, on_button_4, on_button_5)

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
            "_textbox",
            "_entry",
            "_parent_canvas",
            "_parent_frame",
        ):
            child = getattr(widget, attr_name, None)
            if child and child is not widget:
                self._bind_mousewheel_tree(child, on_mousewheel, on_button_4, on_button_5, visited)

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
        self.right_panel.grid_rowconfigure(0, weight=0)
        self.right_panel.grid_rowconfigure(1, weight=0)
        self.right_panel.grid_rowconfigure(2, weight=0)
        self.right_panel.grid_rowconfigure(3, weight=0)
        self.right_panel.grid_rowconfigure(4, weight=1, minsize=190)
        self.right_panel.grid_rowconfigure(5, weight=0)

        self.editor_header = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.editor_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 6))
        self.editor_header.grid_columnconfigure(1, weight=1)

        self.game_visual = ctk.CTkFrame(
            self.editor_header,
            width=42,
            height=42,
            fg_color=SURFACE_TERTIARY,
            corner_radius=10,
            border_width=1,
            border_color=ACCENT_COLOR,
        )
        self.game_visual.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12))
        self.game_visual.grid_propagate(False)
        self.game_visual.grid_columnconfigure(0, weight=1)
        self.game_visual.grid_rowconfigure(0, weight=1)

        self.game_visual_label = ctk.CTkLabel(
            self.game_visual,
            text="+",
            font=("Segoe UI Bold", 21),
            text_color=ACCENT_COLOR,
        )
        self.game_visual_label.grid(row=0, column=0, sticky="nsew")

        self.title_stack = ctk.CTkFrame(self.editor_header, fg_color="transparent")
        self.title_stack.grid(row=0, column=1, sticky="ew")
        self.title_stack.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_stack,
            text="Adicionar jogo",
            font=("Segoe UI Bold", 18),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")

        self.form_card = ctk.CTkFrame(
            self.right_panel,
            fg_color=SURFACE_PRIMARY,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.form_card.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 5))
        self.form_card.grid_columnconfigure(0, weight=1)

        self.name_field = ValidatedEntry(
            self.form_card,
            label_text="Nome do jogo",
            placeholder_text="Ex.: Cyberpunk 2077",
            validator=validate_game_name,
        )
        self.name_field.grid(row=0, column=0, sticky="ew", padx=10, pady=4)
        self.name_field.entry.configure(height=32)
        self.name_field.error_label.configure(wraplength=480)

        self.launch_card = ctk.CTkFrame(
            self.right_panel,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.launch_card.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 5))
        self.launch_card.grid_columnconfigure(0, weight=1)
        self.launch_card.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            self.launch_card,
            text="Inicialização",
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(7, 4))

        self.launch_path_label = ctk.CTkLabel(
            self.launch_card,
            text="Nenhum arquivo configurado.",
            font=("Segoe UI", 11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.launch_path_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.launch_select_button = ctk.CTkButton(
            self.launch_card,
            text="Selecionar arquivo",
            command=self._select_launch_file,
            width=132,
            height=28,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
        )
        self.launch_select_button.grid(row=1, column=1, sticky="e", padx=(8, 4), pady=(0, 5))

        self.launch_clear_button = ctk.CTkButton(
            self.launch_card,
            text="Remover",
            command=self._clear_launch_file,
            width=78,
            height=28,
            fg_color=SURFACE_SECONDARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.launch_clear_button.grid(row=1, column=2, sticky="e", padx=(4, 10), pady=(0, 5))

        self.launch_arguments_hint = ctk.CTkLabel(
            self.launch_card,
            text="Argumentos opcionais",
            font=("Segoe UI", 10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.launch_arguments_hint.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 2))

        self.launch_arguments_entry = ctk.CTkEntry(
            self.launch_card,
            height=30,
            corner_radius=10,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.launch_arguments_entry.grid(row=3, column=0, sticky="ew", padx=(10, 8), pady=(0, 7))

        self.launch_admin_var = ctk.BooleanVar(value=False)
        self.launch_admin_checkbox = ctk.CTkCheckBox(
            self.launch_card,
            text="Executar como administrador",
            variable=self.launch_admin_var,
            text_color=TEXT_SECONDARY,
            checkbox_width=18,
            checkbox_height=18,
        )
        self.launch_admin_checkbox.grid(row=3, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=(0, 7))

        self.launch_file_path = ""

        self.paths_editor = PathListEditor(
            self.right_panel,
            dnd_context=self.dnd_context,
            textbox_height=140,
            dialog_parent=self,
            on_validation_change=self._handle_field_validation_change,
        )
        self.paths_editor.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 6))
        self.name_field.entry.bind(
            "<KeyRelease>",
            lambda _event: self.after_idle(self._refresh_validation_status),
            add="+",
        )
        self.name_field.entry.bind(
            "<FocusOut>",
            lambda _event: self.after_idle(self._refresh_validation_status),
            add="+",
        )

        self.status_label = ctk.CTkLabel(
            self.right_panel,
            text="Preencha os dados do jogo e salve as alterações.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
        )
        self.status_label.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 6))

        self.button_row = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.button_row.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 14))
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
        self.save_button.grid(row=0, column=0, columnspan=2, padx=0, sticky="ew")

        self.delete_button = ctk.CTkButton(
            self.button_row,
            text="Excluir jogo",
            command=self.delete_game,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            height=38,
        )
        self.delete_button.grid(row=0, column=1, padx=(8, 0), sticky="ew")
        self.delete_button.grid_remove()

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

        self._bind_mousewheel_scopes()

        if selected_game and selected_game in filtered_games:
            self.select_game(selected_game)
        elif self.selected_game in filtered_games:
            self.select_game(self.selected_game)
        else:
            self.start_new_game()

    def select_game(self, game):
        self.selected_game = game
        self.name_field.set(game)
        self.paths_editor.set_paths(self.get_paths_for_game(game))
        self._set_launch_config(self.get_launch_config_for_game(game))
        self.paths_editor.validate(show_error=True)
        self.title_label.configure(text="Editar jogo")
        self.game_visual_label.configure(text=self._game_initials(game), text_color=TEXT_PRIMARY)
        self.game_visual.configure(fg_color=SURFACE_TERTIARY, border_color=ACCENT_COLOR)
        self.status_label.configure(text="", text_color=TEXT_SECONDARY)
        self.save_button.configure(text="Salvar alterações")
        self.save_button.grid_configure(column=0, columnspan=1, padx=(0, 8), sticky="ew")
        self.delete_button.grid()
        self.delete_button.configure(state="normal")
        self._refresh_button_states()

    def start_new_game(self):
        self.selected_game = None
        self.name_field.clear()
        self.paths_editor.set_paths([])
        self._set_launch_config({})
        self.paths_editor.clear_feedback()
        self.title_label.configure(text="Adicionar jogo")
        self.game_visual_label.configure(text="+", text_color=ACCENT_COLOR)
        self.game_visual.configure(fg_color=SURFACE_TERTIARY, border_color=ACCENT_COLOR)
        self.status_label.configure(text="")
        self.save_button.configure(text="Adicionar jogo")
        self.save_button.grid_configure(column=0, columnspan=2, padx=0, sticky="ew")
        self.delete_button.grid_remove()
        self.delete_button.configure(state="disabled")
        self._refresh_button_states()
        self.name_field.focus()

    def _game_initials(self, game):
        parts = [part for part in game.replace("_", " ").replace("-", " ").split() if part]
        if not parts:
            return "JG"
        return "".join(part[0] for part in parts[:2]).upper()

    def _handle_field_validation_change(self, _valid):
        self._refresh_validation_status()

    def _set_launch_config(self, config):
        config = config or {}
        self.launch_file_path = str(config.get("executable_path") or "")
        self.launch_arguments_entry.delete(0, "end")
        self.launch_arguments_entry.insert(0, str(config.get("launch_arguments") or ""))
        self.launch_admin_var.set(bool(config.get("launch_as_admin", False)))
        self._refresh_launch_label()

    def _get_launch_config(self):
        return {
            "executable_path": self.launch_file_path,
            "launch_arguments": self.launch_arguments_entry.get(),
            "launch_as_admin": bool(self.launch_admin_var.get()),
        }

    def _refresh_launch_label(self):
        if self.launch_file_path:
            self.launch_path_label.configure(text=self.launch_file_path, text_color=TEXT_PRIMARY)
        else:
            self.launch_path_label.configure(text="Nenhum arquivo configurado.", text_color=TEXT_SECONDARY)

    def _select_launch_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Selecionar arquivo de inicialização",
            filetypes=[
                ("Arquivos de inicialização", "*.exe *.bat"),
                ("Executáveis", "*.exe"),
                ("Arquivos BAT", "*.bat"),
            ],
        )
        if not file_path:
            return

        try:
            validate_launch_config({"executable_path": file_path})
        except ValueError as error:
            self.status_label.configure(text=str(error), text_color=("#dc2626", "#f87171"))
            return

        self.launch_file_path = str(Path(file_path))
        self._refresh_launch_label()
        self._refresh_validation_status()

    def _clear_launch_file(self):
        self.launch_file_path = ""
        self._refresh_launch_label()
        self._refresh_validation_status()

    def _refresh_validation_status(self):
        if not self.winfo_exists():
            return

        if self.name_field.error_message:
            return

        if not self.paths_editor.has_valid_paths():
            return

        if self.selected_game:
            self.status_label.configure(
                text="",
                text_color=TEXT_SECONDARY,
            )
        else:
            self.status_label.configure(
                text="",
                text_color=TEXT_SECONDARY,
            )

    def _refresh_button_states(self):
        for game, button in self.game_buttons.items():
            selected = game == self.selected_game
            button.configure(
                fg_color=ACCENT_COLOR if selected else SURFACE_PRIMARY,
                text_color=TEXT_PRIMARY,
            )

    def save_game(self):
        valid_name = self.name_field.validate(show_error=True)
        valid_paths = self.paths_editor.validate(show_error=True)
        try:
            launch_config = validate_launch_config(self._get_launch_config())
        except ValueError as error:
            self.status_label.configure(text=str(error), text_color=("#dc2626", "#f87171"))
            return

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
            launch_config.__dict__,
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
        self.launch_select_button.configure(state=state)
        self.launch_clear_button.configure(state=state)
        self.launch_arguments_entry.configure(state=state)
        self.launch_admin_checkbox.configure(state=state)
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
        self._reset_scroll_positions()
        self.update_idletasks()

    def _reset_scroll_positions(self):
        for frame in (getattr(self, "game_list_frame", None),):
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

