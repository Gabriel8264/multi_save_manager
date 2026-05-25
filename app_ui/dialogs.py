import customtkinter as ctk

from app_ui.theme import (
    BORDER_COLOR,
    ERROR_COLOR,
    SURFACE_PRIMARY,
    SURFACE_SECONDARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class PromptDialog(ctk.CTkToplevel):
    def __init__(self, master, title, label, initial_value="", validator=None):
        super().__init__(master)
        self.master_window = master
        self.validator = validator
        self.result = None
        self._has_interacted = False

        self.title(title)
        self.geometry("520x320")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=SURFACE_SECONDARY)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.dialog_card = ctk.CTkFrame(
            self,
            fg_color=SURFACE_PRIMARY,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.dialog_card.grid(row=0, column=0, sticky="nsew", padx=22, pady=22)

        self.title_label = ctk.CTkLabel(
            self.dialog_card,
            text=title,
            font=("Segoe UI Bold", 20),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.pack(fill="x", padx=24, pady=(24, 8))

        self.subtitle_label = ctk.CTkLabel(
            self.dialog_card,
            text="Revise o nome antes de confirmar.",
            font=("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
        )
        self.subtitle_label.pack(fill="x", padx=24, pady=(0, 14))

        self.field_label = ctk.CTkLabel(
            self.dialog_card,
            text=label,
            font=("Segoe UI Semibold", 14),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.field_label.pack(fill="x", padx=24, pady=(0, 6))

        self.entry = ctk.CTkEntry(
            self.dialog_card,
            height=44,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
            fg_color=SURFACE_SECONDARY,
            text_color=TEXT_PRIMARY,
        )
        self.entry.pack(fill="x", padx=24)
        if initial_value:
            self.entry.insert(0, initial_value)

        self.error_label = ctk.CTkLabel(
            self.dialog_card,
            text="",
            font=("Segoe UI", 12),
            text_color=ERROR_COLOR,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.error_label.pack(fill="x", padx=24, pady=(6, 0))

        self.button_row = ctk.CTkFrame(
            self.dialog_card,
            fg_color=SURFACE_PRIMARY,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.button_row.pack(fill="x", padx=24, pady=24)

        self.cancel_button = ctk.CTkButton(
            self.button_row,
            text="Cancelar",
            command=self.cancel,
            height=42,
        )
        self.cancel_button.pack(side="left", expand=True, fill="x", padx=(12, 8), pady=12)

        self.confirm_button = ctk.CTkButton(
            self.button_row,
            text="Confirmar",
            command=self.confirm,
            height=42,
        )
        self.confirm_button.pack(side="left", expand=True, fill="x", padx=(8, 12), pady=12)

        self.entry.bind("<KeyRelease>", self._handle_field_change)
        self.entry.bind("<FocusOut>", self._handle_field_blur)
        self.bind("<Return>", lambda _event: self.confirm())
        self.bind("<Escape>", lambda _event: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self._refresh_button_state(show_error=False)
        self.after_idle(self._finalize_layout)
        self.after(10, self._prepare_focus)

    def confirm(self):
        if self._validate_input(show_error=True):
            self.result = self.entry.get().strip()
            self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

    def get_result(self):
        self.wait_window()
        if self.master_window.winfo_exists():
            self.master_window.after(10, self.master_window.focus_force)
        return self.result

    def _validate_input(self, show_error):
        value = self.entry.get().strip()
        if not self.validator:
            self._clear_error()
            return True

        try:
            self.validator(value)
        except ValueError as error:
            if show_error:
                self.entry.configure(border_color=ERROR_COLOR)
                self.error_label.configure(text=str(error))
            return False

        self._clear_error()
        return True

    def _clear_error(self):
        self.entry.configure(border_color=BORDER_COLOR)
        self.error_label.configure(text="")

    def _refresh_button_state(self, show_error):
        state = "normal" if self._validate_input(show_error=show_error) else "disabled"
        self.confirm_button.configure(state=state)

    def _handle_field_change(self, _event=None):
        self._has_interacted = True
        self._refresh_button_state(show_error=True)

    def _handle_field_blur(self, _event=None):
        self._refresh_button_state(show_error=self._has_interacted)

    def _finalize_layout(self):
        self.update_idletasks()
        required_width = max(480, self.dialog_card.winfo_reqwidth() + 44)
        required_height = max(300, self.dialog_card.winfo_reqheight() + 44)
        self.geometry(f"{required_width}x{required_height}")

    def _prepare_focus(self):
        if self.winfo_exists():
            self.lift()
            self.grab_set()
            self.entry.focus_force()
