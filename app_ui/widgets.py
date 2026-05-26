import os
import tkinter as tk
import tkinter.filedialog as filedialog
from pathlib import Path

import customtkinter as ctk

try:
    from PIL import Image
except Exception:
    Image = None

from app_ui.dnd_support import register_drop_target_tree
from app_ui.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    BORDER_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    SURFACE_PRIMARY,
    SURFACE_SECONDARY,
    SURFACE_TERTIARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from core.path_resolver import resolver_caminho
from core.validators import validate_save_path

_IMAGE_CACHE = {}


def _theme_color(color):
    if isinstance(color, tuple):
        return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
    return color


def _load_ctk_image(path_value, size):
    if not Image or not path_value:
        return None

    try:
        image_path = Path(resolver_caminho(path_value))
        if not image_path.is_file():
            return None

        cache_key = (str(image_path), size, image_path.stat().st_mtime)
        if cache_key in _IMAGE_CACHE:
            return _IMAGE_CACHE[cache_key]

        with Image.open(image_path) as source_image:
            image = source_image.copy()
        image.thumbnail(size)
        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
        _IMAGE_CACHE[cache_key] = ctk_image
        return ctk_image
    except Exception:
        return None


class ValidatedEntry(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label_text,
        placeholder_text="",
        validator=None,
    ):
        super().__init__(master, fg_color="transparent")
        self.validator = validator
        self.error_message = ""

        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(
            self,
            text=label_text,
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.label.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder_text,
            height=42,
            corner_radius=12,
            fg_color=SURFACE_SECONDARY,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.bind("<KeyRelease>", lambda _event: self.validate(show_error=True))
        self.entry.bind("<FocusOut>", lambda _event: self.validate(show_error=True))

        self.error_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 12),
            text_color=ERROR_COLOR,
            anchor="w",
            justify="left",
        )
        self.error_label.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.error_label.grid_remove()

    def get(self):
        return self.entry.get().strip()

    def set(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.validate(show_error=False)

    def clear(self):
        self.entry.delete(0, "end")
        self.clear_error()

    def focus(self):
        self.entry.focus()

    def validate(self, show_error=True):
        if not self.validator:
            self.clear_error()
            return True

        try:
            self.validator(self.get())
        except ValueError as error:
            self.error_message = str(error)
            if show_error:
                self.entry.configure(border_color=ERROR_COLOR)
                self.error_label.grid()
                self.error_label.configure(text=self.error_message)
            return False

        self.clear_error()
        return True

    def clear_error(self):
        self.error_message = ""
        self.entry.configure(border_color=BORDER_COLOR)
        self.error_label.configure(text="")
        self.error_label.grid_remove()


class GameLibraryCard(ctk.CTkFrame):
    def __init__(self, master, game, selected, on_select, on_open=None, profile_count=None, compact=False):
        border_color = ACCENT_COLOR if selected else BORDER_COLOR
        width = 156 if compact else 230
        height = 132 if compact else 154
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=SURFACE_PRIMARY,
            corner_radius=12,
            border_width=2 if selected else 1,
            border_color=border_color,
        )
        self.game = game
        self.on_select = on_select
        self.on_open = on_open
        self.profile_count = profile_count
        self.compact = compact
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        self._bind_click(self)
        self._bind_open(self)
        self._build_media(selected)
        self._build_details(selected)

    def _bind_click(self, widget):
        widget.bind("<Button-1>", self._handle_click)

    def _bind_open(self, widget):
        widget.bind("<Double-Button-1>", self._handle_open)

    def _build_media(self, selected):
        media_height = 62 if self.compact else 76
        image_size = (138, 62) if self.compact else (210, 76)
        media = ctk.CTkFrame(
            self,
            height=media_height,
            fg_color=SURFACE_TERTIARY,
            corner_radius=12,
            border_width=0,
        )
        media.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        media.grid_propagate(False)
        media.grid_columnconfigure(0, weight=1)
        self._bind_click(media)
        self._bind_open(media)

        image = _load_ctk_image(self.game.banner_path or self.game.cover_path, image_size)
        if image:
            image_label = ctk.CTkLabel(media, text="", image=image)
            image_label.image = image
            image_label.grid(row=0, column=0, sticky="nsew")
            self._bind_click(image_label)
            self._bind_open(image_label)
            return

        initials = "".join(part[:1] for part in self.game.name.split()[:2]).upper() or "JG"
        placeholder = ctk.CTkLabel(
            media,
            text=initials,
            font=("Segoe UI Bold", 18 if self.compact else 24),
            text_color=ACCENT_COLOR if selected else TEXT_SECONDARY,
        )
        placeholder.grid(row=0, column=0, sticky="nsew")
        self._bind_click(placeholder)
        self._bind_open(placeholder)

    def _build_details(self, selected):
        title = ctk.CTkLabel(
            self,
            text=self.game.name,
            font=("Segoe UI Semibold", 12 if self.compact else 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        title.grid(row=1, column=0, sticky="ew", padx=9)
        self._bind_click(title)
        self._bind_open(title)

        save_count = self.profile_count if self.profile_count is not None else len(self.game.save_paths)
        status_text = "Selecionado" if selected else ("Favorito" if self.game.favorite else "Pronto")
        details_text = f"{save_count} save(s)"
        if self.compact:
            details_text = f"{details_text} · {status_text}"

        details = ctk.CTkLabel(
            self,
            text=details_text,
            font=("Segoe UI", 10 if self.compact else 11),
            text_color=ACCENT_COLOR if selected and self.compact else TEXT_SECONDARY,
            anchor="w",
        )
        details.grid(row=2, column=0, sticky="ew", padx=9, pady=(2, 8 if self.compact else 0))
        self._bind_click(details)
        self._bind_open(details)

        if self.compact:
            return

        status = ctk.CTkLabel(
            self,
            text=status_text,
            font=("Segoe UI Semibold", 9 if self.compact else 10),
            text_color=ACCENT_COLOR if selected or self.game.favorite else TEXT_SECONDARY,
            anchor="w",
        )
        status.grid(row=3, column=0, sticky="ew", padx=9, pady=(0, 6))
        self._bind_click(status)
        self._bind_open(status)

    def _handle_click(self, _event=None):
        self.on_select(self.game.name)

    def _handle_open(self, _event=None):
        if self.on_open:
            self.on_open(self.game.name)
        else:
            self.on_select(self.game.name)


class PathListEditor(ctk.CTkFrame):
    def __init__(
        self,
        master,
        dnd_context=None,
        textbox_height=180,
        dialog_parent=None,
        on_validation_change=None,
    ):
        super().__init__(master, fg_color="transparent")
        self.dnd_context = dnd_context
        self.dialog_parent = dialog_parent
        self.on_validation_change = on_validation_change
        self._validation_after = None
        self._compact_toolbar = False
        self.bind("<Configure>", self._on_resize)

        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(
            self,
            text="Diretórios de save",
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.label.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.toolbar.grid_columnconfigure(0, weight=1)
        self.toolbar.grid_columnconfigure(1, weight=1)

        self.add_button = ctk.CTkButton(
            self.toolbar,
            text="Selecionar pasta",
            command=self.browse_for_folder,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            height=36,
        )
        self.add_button.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.open_button = ctk.CTkButton(
            self.toolbar,
            text="Abrir pastas",
            command=self.open_paths,
            fg_color=SURFACE_PRIMARY,
            hover_color=SURFACE_TERTIARY,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_COLOR,
            height=36,
        )
        self.open_button.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self.drop_zone = tk.Frame(
            self,
            height=38,
            bg=_theme_color(SURFACE_TERTIARY),
            highlightthickness=1,
            highlightbackground=_theme_color(ACCENT_COLOR),
            highlightcolor=_theme_color(ACCENT_COLOR),
        )
        self.drop_zone.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.drop_zone.grid_propagate(False)
        self.drop_zone.grid_columnconfigure(0, weight=1)

        self.drop_zone_label = tk.Label(
            self.drop_zone,
            text="+  Arraste uma pasta aqui",
            bg=_theme_color(SURFACE_TERTIARY),
            fg=_theme_color(ACCENT_COLOR),
            font=("Segoe UI", 12, "bold"),
            anchor="center",
        )
        self.drop_zone_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=5)

        self.textbox = ctk.CTkTextbox(
            self,
            height=textbox_height,
            corner_radius=12,
            fg_color=SURFACE_SECONDARY,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=("Consolas", 12),
        )
        self.textbox.grid(row=3, column=0, sticky="nsew")
        self.textbox.bind("<KeyRelease>", self._schedule_validation)
        self.textbox.bind("<Double-Button-1>", self._open_path_from_click)
        self._configure_path_tags()
        self.grid_rowconfigure(3, weight=1)

        drop_targets = (
            self.drop_zone,
            self.drop_zone_label,
            self.textbox,
        )
        drop_enabled = False
        for target in drop_targets:
            drop_enabled = register_drop_target_tree(target, self.dnd_context, self.append_paths) or drop_enabled
        if not drop_enabled:
            self.drop_zone_label.configure(fg=_theme_color(TEXT_SECONDARY))
        self.bind("<Map>", lambda _event: self.refresh_drop_targets(), add="+")
        self.drop_zone.bind("<Enter>", lambda _event: self.refresh_drop_targets(), add="+")
        self.drop_zone_label.bind("<Enter>", lambda _event: self.refresh_drop_targets(), add="+")
        self.after(300, self.refresh_drop_targets)

        self.feedback_label = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.feedback_label.grid(row=4, column=0, sticky="ew", pady=(5, 0))
        self.feedback_label.grid_remove()

    def refresh_drop_targets(self):
        drop_targets = (
            self.drop_zone,
            self.drop_zone_label,
            self.textbox,
        )
        registered = False
        for target in drop_targets:
            registered = register_drop_target_tree(target, self.dnd_context, self.append_paths) or registered
        return registered

    def _on_resize(self, _event=None):
        if not self.winfo_exists():
            return

        width = self.winfo_width()
        if width <= 1:
            return

        wraplength = max(260, width - 16)
        self.feedback_label.configure(wraplength=wraplength)

        compact = width < 850
        if compact == self._compact_toolbar:
            return

        self._compact_toolbar = compact
        if compact:
            self.toolbar.grid_columnconfigure(0, weight=1)
            self.toolbar.grid_columnconfigure(1, weight=1)
            self.add_button.grid_configure(row=0, column=0, padx=(0, 6), pady=0, sticky="ew")
            self.open_button.grid_configure(row=0, column=1, padx=(6, 0), pady=0, sticky="ew")
        else:
            self.toolbar.grid_columnconfigure(0, weight=1)
            self.toolbar.grid_columnconfigure(1, weight=1)
            self.add_button.grid_configure(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")
            self.open_button.grid_configure(row=0, column=1, padx=(8, 0), pady=0, sticky="ew")

    def _schedule_validation(self, _event=None):
        if self._validation_after:
            self.after_cancel(self._validation_after)
        self._validation_after = self.after(250, lambda: self.validate(show_error=True))

    def _configure_path_tags(self):
        try:
            self.textbox.tag_config("invalid_path", foreground=_theme_color(ERROR_COLOR))
        except Exception:
            pass

    def _set_feedback(self, message="", color=None):
        if not message:
            self.feedback_label.configure(text="")
            self.feedback_label.grid_remove()
            return

        self.feedback_label.grid()
        self.feedback_label.configure(text=message, text_color=color or TEXT_SECONDARY)

    def _clear_path_highlights(self):
        try:
            self.textbox.tag_remove("invalid_path", "1.0", "end")
        except Exception:
            pass

    def _highlight_invalid_lines(self, line_numbers):
        self._clear_path_highlights()
        for line_number in line_numbers:
            try:
                self.textbox.tag_add("invalid_path", f"{line_number}.0", f"{line_number}.end")
            except Exception:
                pass

    def _refresh_path_highlights(self):
        invalid_lines, _valid_paths = self._find_invalid_path_lines()
        if invalid_lines:
            self._highlight_invalid_lines(invalid_lines)
            self.textbox.configure(border_color=ERROR_COLOR)
            return False

        self._clear_path_highlights()
        self.textbox.configure(border_color=BORDER_COLOR)
        return True

    def _get_path_lines(self):
        content = self.textbox.get("1.0", "end")
        return [
            (line_number, line.strip())
            for line_number, line in enumerate(content.splitlines(), start=1)
            if line.strip()
        ]

    def _find_invalid_path_lines(self):
        invalid_lines = []
        valid_paths = []

        for line_number, path in self._get_path_lines():
            try:
                valid_paths.append(validate_save_path(path))
            except ValueError:
                invalid_lines.append(line_number)

        return invalid_lines, valid_paths

    def has_valid_paths(self):
        invalid_lines, valid_paths = self._find_invalid_path_lines()
        return not invalid_lines and bool(valid_paths)

    def browse_for_folder(self):
        parent = self.dialog_parent if self.dialog_parent and self.dialog_parent.winfo_exists() else self.winfo_toplevel()
        path = filedialog.askdirectory(parent=parent)
        if path:
            self.append_paths([path])
        self._restore_dialog_parent_focus(parent)

    def _restore_dialog_parent_focus(self, parent):
        if not parent or not parent.winfo_exists():
            return

        try:
            parent.lift()
            parent.focus_set()
        except Exception:
            pass

    def open_paths(self):
        invalid_lines, valid_paths = self._find_invalid_path_lines()
        if invalid_lines:
            self.textbox.configure(border_color=ERROR_COLOR)
            self._highlight_invalid_lines(invalid_lines)
            self._set_feedback()
            return

        if not valid_paths:
            self.textbox.configure(border_color=ERROR_COLOR)
            self._clear_path_highlights()
            self._set_feedback()
            return

        for path in valid_paths:
            os.startfile(str(Path(resolver_caminho(path))))

        self.textbox.configure(border_color=BORDER_COLOR)
        self._clear_path_highlights()
        self._set_feedback(f"Abrindo {len(valid_paths)} pasta(s) no Explorador de Arquivos.", SUCCESS_COLOR)

    def append_paths(self, paths):
        normalized = self.get_paths()
        normalized_resolved = {str(Path(resolver_caminho(path))) for path in normalized}
        added_count = 0
        changed = False
        for path in paths:
            cleaned = path.strip().strip("{").strip("}")
            if not cleaned:
                continue

            resolved = Path(resolver_caminho(cleaned))
            if not resolved.is_dir():
                continue

            resolved_str = str(resolved)
            if resolved_str not in normalized_resolved:
                normalized_resolved.add(resolved_str)
                normalized.append(cleaned)
                added_count += 1
                changed = True

        if changed:
            self.set_paths(normalized)
            self._refresh_path_highlights()
            self._set_feedback(
                (
                    "Pasta adicionada aos diretórios de save."
                    if added_count == 1
                    else f"{added_count} pastas adicionadas aos diretórios de save."
                ),
                SUCCESS_COLOR,
            )

    def get_paths(self):
        return [path for _line_number, path in self._get_path_lines()]

    def set_paths(self, paths):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", "\n".join(paths))
        self._refresh_path_highlights()

    def _open_path_from_click(self, event):
        try:
            line = int(float(self.textbox.index(f"@{event.x},{event.y}").split(".")[0]))
        except (ValueError, ctk.TclError):
            return

        line_value = self.textbox.get(f"{line}.0", f"{line}.end").strip()
        if not line_value:
            return

        try:
            normalized = validate_save_path(line_value)
        except ValueError:
            self.textbox.configure(border_color=ERROR_COLOR)
            self._highlight_invalid_lines([line])
            self._set_feedback()
            return

        self.textbox.configure(border_color=BORDER_COLOR)
        self._clear_path_highlights()
        self._set_feedback("Abrindo pasta no Explorador de Arquivos.", SUCCESS_COLOR)
        os.startfile(str(Path(resolver_caminho(normalized))))

    def validate(self, show_error=True):
        invalid_lines, valid_paths = self._find_invalid_path_lines()
        if invalid_lines:
            if show_error:
                self._highlight_invalid_lines(invalid_lines)
                self._set_feedback()
            self.textbox.configure(border_color=ERROR_COLOR)
            self._notify_validation_change(False)
            return False

        if not valid_paths:
            self._clear_path_highlights()
            self._set_feedback()
            self.textbox.configure(border_color=ERROR_COLOR)
            self._notify_validation_change(False)
            return False

        self.textbox.configure(border_color=BORDER_COLOR)
        self._clear_path_highlights()
        self._set_feedback()
        self._notify_validation_change(True)
        return True

    def _notify_validation_change(self, valid):
        if self.on_validation_change:
            self.on_validation_change(valid)

    def clear_feedback(self):
        self.textbox.configure(border_color=BORDER_COLOR)
        self._clear_path_highlights()
        self._set_feedback()


class ProfileCard(ctk.CTkFrame):
    def __init__(self, master, profile_name, active, on_activate):
        super().__init__(
            master,
            fg_color=SURFACE_PRIMARY,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.profile_name = profile_name
        self.on_activate = on_activate

        self.grid_columnconfigure(0, weight=1)
        self.bind("<Button-1>", self._handle_click)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        header.grid_columnconfigure(0, weight=1)
        header.bind("<Button-1>", self._handle_click)

        self.title_label = ctk.CTkLabel(
            header,
            text=profile_name,
            font=("Segoe UI Semibold", 18),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.title_label.bind("<Button-1>", self._handle_click)

        tag_text = "Perfil ativo" if active else "Perfil salvo"
        tag_color = SUCCESS_COLOR if active else TEXT_SECONDARY
        self.tag_label = ctk.CTkLabel(
            header,
            text=tag_text,
            font=("Segoe UI Semibold", 12),
            text_color=tag_color,
        )
        self.tag_label.grid(row=0, column=1, sticky="e")
        self.tag_label.bind("<Button-1>", self._handle_click)

        self.description = ctk.CTkLabel(
            self,
            text="Clique para carregar este conjunto de saves no jogo selecionado.",
            font=("Segoe UI", 13),
            text_color=TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=520,
        )
        self.description.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.description.bind("<Button-1>", self._handle_click)

        self.action_button = ctk.CTkButton(
            self,
            text="Carregar perfil",
            command=self._handle_click,
            fg_color=SUCCESS_COLOR if active else ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            height=40,
        )
        if active:
            self.action_button.configure(text_color=("#052e16", "#041b10"))
        self.action_button.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))

    def _handle_click(self, _event=None):
        self.on_activate(self.profile_name)


class BusyOverlay(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=("#e2e8f0", "#020617"))

        self.card = ctk.CTkFrame(
            self,
            fg_color=SURFACE_PRIMARY,
            corner_radius=22,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")

        self.title_label = ctk.CTkLabel(
            self.card,
            text="Operação em andamento",
            font=("Segoe UI Bold", 22),
            text_color=TEXT_PRIMARY,
        )
        self.title_label.pack(padx=28, pady=(24, 10))

        self.message_label = ctk.CTkLabel(
            self.card,
            text="Aguarde...",
            font=("Segoe UI", 14),
            text_color=TEXT_SECONDARY,
            wraplength=360,
            justify="center",
        )
        self.message_label.pack(padx=28, pady=(0, 12))

        self.progress = ctk.CTkProgressBar(self.card, width=300)
        self.progress.pack(padx=28, pady=(0, 24))
        self.progress.set(0)

        self.place_forget()

    def show(self, message):
        self.message_label.configure(text=message)
        self.progress.set(0)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def hide(self):
        self.place_forget()

    def set_progress(self, value, message):
        self.message_label.configure(text=message)
        self.progress.set(value)

