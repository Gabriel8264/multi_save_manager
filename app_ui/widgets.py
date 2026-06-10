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
    WARNING_COLOR,
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


def animate_modal_open(
    modal_frame,
    width,
    height,
    *,
    relx=0.5,
    rely=0.5,
    x=None,
    y=None,
    anchor="center",
    duration_ms=150,
    start_scale=0.94,
    on_complete=None,
):
    frames = 7
    interval = max(duration_ms // frames, 1)
    start_offset = max(int(height * (1 - start_scale) * 0.7), 8)

    def ease_out_cubic(value):
        return 1 - pow(1 - value, 3)

    def place_with_offset(offset=0):
        modal_frame.configure(width=width, height=height)
        place_options = {
            "anchor": anchor,
        }
        if x is not None:
            place_options["x"] = x
        else:
            place_options["relx"] = relx
            place_options["x"] = 0
        if y is not None:
            place_options["y"] = y + offset
        else:
            place_options["rely"] = rely
            place_options["y"] = offset
        modal_frame.place(**place_options)

    def step(index=0):
        if not modal_frame.winfo_exists():
            return

        progress = min(index / frames, 1)
        eased = ease_out_cubic(progress)
        offset = int(start_offset * (1 - eased))
        place_with_offset(offset)
        modal_frame.lift()
        if index >= frames:
            place_with_offset(0)
            if on_complete:
                on_complete()
            return
        modal_frame.after(interval, lambda: step(index + 1))

    modal_frame.configure(width=width, height=height)
    modal_frame.place(x=-10000, y=-10000, anchor="nw")
    modal_frame.update_idletasks()
    place_with_offset(start_offset)
    modal_frame.after(interval, lambda: step(1))


class CloseButton(ctk.CTkFrame):
    def __init__(
        self,
        master,
        command,
        size=34,
        icon_size=12,
        fg_color=SURFACE_SECONDARY,
        hover_color=SURFACE_TERTIARY,
        border_color=BORDER_COLOR,
        icon_color=TEXT_SECONDARY,
        icon_hover_color=TEXT_PRIMARY,
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            fg_color=fg_color,
            corner_radius=9,
            border_width=1,
            border_color=border_color,
        )
        self.command = command
        self.size = size
        self.icon_size = icon_size
        self.normal_color = fg_color
        self.hover_color = hover_color
        self.normal_icon_color = icon_color
        self.hover_icon_color = icon_hover_color
        self.hovered = False

        self.grid_propagate(False)
        self.configure(cursor="hand2")

        self.icon_canvas = tk.Canvas(
            self,
            width=icon_size + 4,
            height=icon_size + 4,
            borderwidth=0,
            highlightthickness=0,
            bg=_theme_color(fg_color),
            cursor="hand2",
        )
        self.icon_canvas.place(relx=0.5, rely=0.5, anchor="center")

        for widget in (self, self.icon_canvas):
            widget.bind("<Button-1>", self._handle_click)
            widget.bind("<Enter>", self._handle_enter)
            widget.bind("<Leave>", self._handle_leave)
        self.icon_canvas.bind("<Configure>", lambda _event: self._draw_icon())
        self.after_idle(self._draw_icon)

    def _handle_click(self, _event=None):
        self.command()
        return "break"

    def _handle_enter(self, _event=None):
        self.hovered = True
        self.configure(fg_color=self.hover_color, border_color=TEXT_SECONDARY)
        self.icon_canvas.configure(bg=_theme_color(self.hover_color))
        self._draw_icon()

    def _handle_leave(self, _event=None):
        if self._pointer_is_inside():
            return
        self.hovered = False
        self.configure(fg_color=self.normal_color, border_color=BORDER_COLOR)
        self.icon_canvas.configure(bg=_theme_color(self.normal_color))
        self._draw_icon()

    def _pointer_is_inside(self):
        pointer_x = self.winfo_pointerx()
        pointer_y = self.winfo_pointery()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty()
        return (
            root_x <= pointer_x <= root_x + self.winfo_width()
            and root_y <= pointer_y <= root_y + self.winfo_height()
        )

    def _draw_icon(self):
        if not self.icon_canvas.winfo_exists():
            return

        canvas = self.icon_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), self.icon_size + 4)
        height = max(canvas.winfo_height(), self.icon_size + 4)
        half = self.icon_size / 2
        center_x = width / 2
        center_y = height / 2
        color = _theme_color(self.hover_icon_color if self.hovered else self.normal_icon_color)
        for start_x, start_y, end_x, end_y in (
            (center_x - half, center_y - half, center_x + half, center_y + half),
            (center_x + half, center_y - half, center_x - half, center_y + half),
        ):
            canvas.create_line(
                start_x,
                start_y,
                end_x,
                end_y,
                fill=color,
                width=1.5,
                capstyle="round",
            )


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
    def __init__(
        self,
        master,
        game,
        selected,
        on_select,
        on_open=None,
        on_favorite=None,
        profile_count=None,
        compact=False,
    ):
        border_color = ACCENT_COLOR if selected else BORDER_COLOR
        width = 146 if compact else 138
        height = 118 if compact else 218
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=SURFACE_PRIMARY if compact else SURFACE_SECONDARY,
            corner_radius=10 if compact else 8,
            border_width=2 if selected else (1 if compact else 0),
            border_color=border_color,
        )
        self.game = game
        self.on_select = on_select
        self.on_open = on_open
        self.on_favorite = on_favorite
        self.profile_count = profile_count
        self.compact = compact
        self.selected = selected
        self.favorite = game.favorite
        self.favorite_button = None
        self.placeholder_label = None
        self.details_label = None
        self.status_label = None
        self.body = None
        self.hovered = False
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        self._bind_click(self)
        self._bind_open(self)
        self._bind_hover(self)
        self._build_media(selected)
        self._build_details(selected)

    def _bind_click(self, widget):
        widget.bind("<Button-1>", self._handle_click)

    def _bind_open(self, widget):
        widget.bind("<Double-Button-1>", self._handle_open)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._handle_enter)
        widget.bind("<Leave>", self._handle_leave)

    def _build_media(self, selected):
        media_height = 54 if self.compact else 174
        image_size = (128, 54) if self.compact else (126, 174)
        media = ctk.CTkFrame(
            self,
            height=media_height,
            fg_color=SURFACE_TERTIARY,
            corner_radius=9 if self.compact else 8,
            border_width=0,
        )
        media.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=7 if self.compact else 4,
            pady=(7 if self.compact else 4, 0),
        )
        media.grid_propagate(False)
        media.grid_columnconfigure(0, weight=1)
        media.grid_rowconfigure(0, weight=1)
        self._bind_click(media)
        self._bind_open(media)
        self._bind_hover(media)

        if self.compact:
            image_source = self.game.banner_path or self.game.cover_path
        else:
            image_source = self.game.cover_path or self.game.banner_path
        image = _load_ctk_image(image_source, image_size)
        if image:
            image_label = ctk.CTkLabel(media, text="", image=image)
            image_label.image = image
            image_label.grid(row=0, column=0, sticky="nsew")
            self._bind_click(image_label)
            self._bind_open(image_label)
            self._bind_hover(image_label)
            self._build_favorite_button(media)
            return

        initials = "".join(part[:1] for part in self.game.name.split()[:2]).upper() or "JG"
        placeholder = ctk.CTkLabel(
            media,
            text=initials,
            font=("Segoe UI Bold", 16 if self.compact else 24),
            text_color=ACCENT_COLOR if selected else TEXT_SECONDARY,
        )
        self.placeholder_label = placeholder
        placeholder.grid(row=0, column=0, sticky="nsew")
        self._bind_click(placeholder)
        self._bind_open(placeholder)
        self._bind_hover(placeholder)
        self._build_favorite_button(media)

    def _build_favorite_button(self, master):
        self.favorite_button = ctk.CTkLabel(
            master,
            text="★" if self.favorite else "☆",
            width=22,
            height=22,
            corner_radius=12,
            fg_color=SURFACE_PRIMARY,
            text_color=WARNING_COLOR if self.favorite else TEXT_SECONDARY,
            font=("Segoe UI Symbol", 14),
        )
        self.favorite_button.grid(row=0, column=0, sticky="ne", padx=5, pady=4)
        self.favorite_button.bind("<Button-1>", self._handle_favorite)
        self._bind_hover(self.favorite_button)

    def _build_details(self, selected):
        body = ctk.CTkFrame(
            self,
            fg_color=SURFACE_PRIMARY if self.compact else "transparent",
            corner_radius=9,
            border_width=0,
        )
        self.body = body
        body.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=7 if self.compact else 4,
            pady=(0, 7 if self.compact else 4),
        )
        body.grid_columnconfigure(0, weight=1)
        self._bind_click(body)
        self._bind_open(body)
        self._bind_hover(body)

        title = ctk.CTkLabel(
            body,
            text=self.game.name,
            font=("Segoe UI Semibold", 11 if self.compact else 11),
            text_color=TEXT_PRIMARY,
            anchor="w",
            wraplength=126 if self.compact else 126,
        )
        title.grid(row=0, column=0, sticky="ew", padx=3, pady=(6 if self.compact else 4, 0))
        self._bind_click(title)
        self._bind_open(title)
        self._bind_hover(title)

        save_count = self.profile_count if self.profile_count is not None else len(self.game.save_paths)
        status_text = "Selecionado" if selected else ("Favorito" if self.favorite else "Pronto")
        details_text = f"{save_count} save(s)"
        if self.compact:
            details_text = f"{details_text} · {status_text}"

        details = ctk.CTkLabel(
            body,
            text=details_text,
            font=("Segoe UI", 9),
            text_color=ACCENT_COLOR if selected and self.compact else TEXT_SECONDARY,
            anchor="w",
        )
        self.details_label = details
        details.grid(row=1, column=0, sticky="ew", padx=3, pady=(1, 5 if self.compact else 0))
        self._bind_click(details)
        self._bind_open(details)
        self._bind_hover(details)

        if self.compact:
            return

    def set_selected(self, selected):
        self.selected = selected
        self._apply_visual_state()

        if self.placeholder_label:
            self.placeholder_label.configure(text_color=ACCENT_COLOR if selected else TEXT_SECONDARY)

        save_count = self.profile_count if self.profile_count is not None else len(self.game.save_paths)
        status_text = "Selecionado" if selected else ("Favorito" if self.favorite else "Pronto")
        details_text = f"{save_count} save(s)"
        if self.compact:
            details_text = f"{details_text} · {status_text}"

        if self.details_label:
            self.details_label.configure(
                text=details_text,
                text_color=ACCENT_COLOR if selected and self.compact else TEXT_SECONDARY,
            )

        if self.status_label:
            self.status_label.configure(
                text=status_text,
                text_color=ACCENT_COLOR if selected or self.favorite else TEXT_SECONDARY,
            )

    def set_favorite(self, favorite):
        self.favorite = favorite
        if self.favorite_button:
            self.favorite_button.configure(
                text="★" if favorite else "☆",
                text_color=WARNING_COLOR if favorite else TEXT_SECONDARY,
            )
        self.set_selected(self.selected)

    def _handle_click(self, _event=None):
        self.on_select(self.game.name)

    def _handle_open(self, _event=None):
        if self.on_open:
            self.on_open(self.game.name)
        else:
            self.on_select(self.game.name)

    def _handle_enter(self, _event=None):
        self.hovered = True
        self._apply_visual_state()

    def _handle_leave(self, _event=None):
        self.hovered = False
        self._apply_visual_state()

    def _apply_visual_state(self):
        if self.compact:
            self.configure(
                border_width=2 if self.selected else 1,
                border_color=ACCENT_COLOR if self.selected else BORDER_COLOR,
            )
            return

        if self.selected:
            self.configure(fg_color=SURFACE_SECONDARY, border_width=2, border_color=ACCENT_COLOR)
        elif self.hovered:
            self.configure(fg_color=SURFACE_SECONDARY, border_width=1, border_color=BORDER_COLOR)
        else:
            self.configure(fg_color=SURFACE_SECONDARY, border_width=0, border_color=SURFACE_SECONDARY)

    def _handle_favorite(self, _event=None):
        if self.on_favorite:
            self.on_favorite(self.game.name)
        return "break"


class GameLibraryListItem(ctk.CTkFrame):
    def __init__(self, master, game, selected, on_select, on_open=None, on_favorite=None, profile_count=None):
        super().__init__(
            master,
            height=40,
            fg_color=SURFACE_TERTIARY if selected else SURFACE_SECONDARY,
            corner_radius=8,
            border_width=1,
            border_color=ACCENT_COLOR if selected else SURFACE_SECONDARY,
        )
        self.game = game
        self.on_select = on_select
        self.on_open = on_open
        self.on_favorite = on_favorite
        self.profile_count = profile_count
        self.selected = selected
        self.favorite = game.favorite
        self.hovered = False
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        self._bind_click(self)
        self._bind_open(self)
        self._bind_hover(self)

        self.icon = ctk.CTkFrame(
            self,
            width=26,
            height=26,
            fg_color=SURFACE_PRIMARY,
            corner_radius=6,
            border_width=0,
            border_color=SURFACE_PRIMARY,
        )
        self.icon.grid(row=0, column=0, sticky="w", padx=(7, 8), pady=7)
        self.icon.grid_propagate(False)
        self.icon.grid_columnconfigure(0, weight=1)
        self.icon.grid_rowconfigure(0, weight=1)
        self._bind_click(self.icon)
        self._bind_open(self.icon)
        self._bind_hover(self.icon)

        initials = "".join(part[:1] for part in self.game.name.split()[:2]).upper() or "JG"
        self.icon_label = ctk.CTkLabel(
            self.icon,
            text=initials,
            font=("Segoe UI Bold", 8),
            text_color=ACCENT_COLOR if selected else TEXT_SECONDARY,
        )
        self.icon_label.grid(row=0, column=0, sticky="nsew")
        self._bind_click(self.icon_label)
        self._bind_open(self.icon_label)
        self._bind_hover(self.icon_label)

        text_stack = ctk.CTkFrame(self, fg_color="transparent")
        text_stack.grid(row=0, column=1, sticky="ew", pady=0)
        text_stack.grid_columnconfigure(0, weight=1)
        self._bind_click(text_stack)
        self._bind_open(text_stack)
        self._bind_hover(text_stack)

        self.title_label = ctk.CTkLabel(
            text_stack,
            text=self.game.name,
            font=("Segoe UI Semibold", 10),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")
        self._bind_click(self.title_label)
        self._bind_open(self.title_label)
        self._bind_hover(self.title_label)

        self.favorite_button = ctk.CTkLabel(
            self,
            text="★" if self.favorite else "☆",
            width=22,
            height=22,
            text_color=WARNING_COLOR if self.favorite else TEXT_SECONDARY,
            font=("Segoe UI Symbol", 12),
        )
        self.favorite_button.grid(row=0, column=2, sticky="e", padx=(5, 7))
        self.favorite_button.bind("<Button-1>", self._handle_favorite)
        self._bind_hover(self.favorite_button)

    def _bind_click(self, widget):
        widget.bind("<Button-1>", self._handle_click)

    def _bind_open(self, widget):
        widget.bind("<Double-Button-1>", self._handle_open)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._handle_enter)
        widget.bind("<Leave>", self._handle_leave)

    def set_selected(self, selected):
        self.selected = selected
        self._apply_visual_state()
        self.icon_label.configure(text_color=ACCENT_COLOR if selected else TEXT_SECONDARY)

    def set_favorite(self, favorite):
        self.favorite = favorite
        self.favorite_button.configure(
            text="★" if favorite else "☆",
            text_color=WARNING_COLOR if favorite else TEXT_SECONDARY,
        )

    def _handle_click(self, _event=None):
        self.on_select(self.game.name)

    def _handle_open(self, _event=None):
        if self.on_open:
            self.on_open(self.game.name)
        else:
            self.on_select(self.game.name)

    def _handle_enter(self, _event=None):
        self.hovered = True
        self._apply_visual_state()

    def _handle_leave(self, _event=None):
        self.hovered = False
        self._apply_visual_state()

    def _apply_visual_state(self):
        if self.selected:
            self.configure(fg_color=SURFACE_TERTIARY, border_color=ACCENT_COLOR)
        elif self.hovered:
            self.configure(fg_color=SURFACE_TERTIARY, border_color=BORDER_COLOR)
        else:
            self.configure(fg_color=SURFACE_SECONDARY, border_color=SURFACE_SECONDARY)

    def _handle_favorite(self, _event=None):
        if self.on_favorite:
            self.on_favorite(self.game.name)
        return "break"


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
        self.toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.toolbar.grid_columnconfigure(0, weight=1)
        self.toolbar.grid_columnconfigure(1, weight=1)

        self.add_button = ctk.CTkButton(
            self.toolbar,
            text="Selecionar pasta",
            command=self.browse_for_folder,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            height=32,
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
            height=32,
        )
        self.open_button.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self.drop_zone = tk.Frame(
            self,
            height=40,
            bg=_theme_color(SURFACE_TERTIARY),
            highlightthickness=1,
            highlightbackground=_theme_color(ACCENT_COLOR),
            highlightcolor=_theme_color(ACCENT_COLOR),
        )
        self.drop_zone.grid(row=2, column=0, sticky="ew", pady=(2, 8))
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
        self.drop_zone_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=7)

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

    def set_active(self, active):
        self.tag_label.configure(
            text="Perfil ativo" if active else "Perfil salvo",
            text_color=SUCCESS_COLOR if active else TEXT_SECONDARY,
        )
        self.action_button.configure(
            fg_color=SUCCESS_COLOR if active else ACCENT_COLOR,
            text_color=("#052e16", "#041b10") if active else TEXT_PRIMARY,
        )


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

