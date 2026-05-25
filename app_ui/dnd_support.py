import tkinter

import customtkinter as ctk


class _DummyTix:
    class Tk:
        pass


def _load_tkinterdnd():
    setattr(tkinter, "tix", _DummyTix)
    from tkinterdnd2 import CF_HDROP, COPY, DND_FILES, TkinterDnD

    return COPY, DND_FILES, CF_HDROP, TkinterDnD


def get_dnd_ctk_base():
    try:
        _copy, _dnd_files, _cf_hdrop, tkinter_dnd = _load_tkinterdnd()
    except Exception:
        return ctk.CTk

    class CTkDnD(ctk.CTk, tkinter_dnd.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = tkinter_dnd._require(self)

    return CTkDnD


def enable_tkdnd(root):
    try:
        copy_action, dnd_files, cf_hdrop, tkinter_dnd = _load_tkinterdnd()
    except Exception:
        return None

    try:
        if not getattr(root, "TkdndVersion", None):
            root.TkdndVersion = tkinter_dnd._require(root)
    except Exception:
        return None

    return {
        "action": copy_action,
        "files_type": dnd_files,
        "native_files_type": cf_hdrop,
        "drop_types": (dnd_files, cf_hdrop),
    }


def register_drop_target(widget, dnd_context, callback):
    if not dnd_context:
        return False

    action = str(dnd_context["action"])
    def accept_drop(event=None):
        return action

    def handle_drop(event):
        paths = widget.tk.splitlist(event.data)
        callback(paths)
        return action

    try:
        widget.drop_target_register(*dnd_context.get("drop_types", (dnd_context["files_type"],)))
        for sequence in (
            "<<DropEnter>>",
            "<<DropEnter:DND_Files>>",
            "<<DropEnter:CF_HDROP>>",
            "<<DropPosition>>",
            "<<DropPosition:DND_Files>>",
            "<<DropPosition:CF_HDROP>>",
        ):
            widget.dnd_bind(sequence, accept_drop)
        for sequence in ("<<Drop>>", "<<Drop:DND_Files>>", "<<Drop:CF_HDROP>>"):
            widget.dnd_bind(sequence, handle_drop)
    except Exception:
        return False
    return True


def register_drop_target_tree(widget, dnd_context, callback, visited=None):
    if visited is None:
        visited = set()

    widget_id = str(widget)
    if widget_id in visited:
        return False
    visited.add(widget_id)

    registered = register_drop_target(widget, dnd_context, callback)

    for child in getattr(widget, "winfo_children", lambda: [])():
        registered = register_drop_target_tree(child, dnd_context, callback, visited) or registered

    for attr_name in (
        "_canvas",
        "_label",
        "_text_label",
        "_image_label",
        "_textbox",
        "_entry",
        "_parent_canvas",
        "_parent_frame",
        "_scrollbar",
        "_x_scrollbar",
        "_y_scrollbar",
    ):
        child = getattr(widget, attr_name, None)
        if child and child is not widget:
            registered = register_drop_target_tree(child, dnd_context, callback, visited) or registered

    return registered
