def _resolved_window_size(window, fallback_width=None, fallback_height=None, min_width=None, min_height=None):
    current_width = window.winfo_width()
    current_height = window.winfo_height()
    requested_width = window.winfo_reqwidth()
    requested_height = window.winfo_reqheight()

    width_candidates = [requested_width]
    height_candidates = [requested_height]

    if current_width > 1:
        width_candidates.insert(0, current_width)
    if current_height > 1:
        height_candidates.insert(0, current_height)
    if fallback_width:
        width_candidates.append(fallback_width)
    if fallback_height:
        height_candidates.append(fallback_height)
    if min_width:
        width_candidates.append(min_width)
    if min_height:
        height_candidates.append(min_height)

    return max(width_candidates), max(height_candidates)


def center_window(
    window,
    parent=None,
    y_offset=0,
    fallback_width=None,
    fallback_height=None,
    min_width=None,
    min_height=None,
):
    if parent is not None and parent.winfo_exists():
        parent.update_idletasks()
    window.update_idletasks()

    width, height = _resolved_window_size(
        window,
        fallback_width=fallback_width,
        fallback_height=fallback_height,
        min_width=min_width,
        min_height=min_height,
    )

    if parent is not None and parent.winfo_exists():
        reference_width = max(parent.winfo_width(), 1)
        reference_height = max(parent.winfo_height(), 1)
        reference_x = parent.winfo_rootx()
        reference_y = parent.winfo_rooty()
    else:
        reference_width = window.winfo_screenwidth()
        reference_height = window.winfo_screenheight()
        reference_x = 0
        reference_y = 0

    x = reference_x + max((reference_width - width) // 2, 0)
    y = reference_y + max((reference_height - height) // 2, 0) + y_offset

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, min(x, max(screen_width - width, 0)))
    y = max(0, min(y, max(screen_height - height, 0)))

    window.geometry(f"{width}x{height}+{x}+{y}")
    return x, y


def center_window_near_parent_top(window, parent, top_margin=48):
    if parent is not None and parent.winfo_exists():
        parent.update_idletasks()
    window.update_idletasks()

    width = window.winfo_width() or window.winfo_reqwidth()
    height = window.winfo_height() or window.winfo_reqheight()
    parent_width = max(parent.winfo_width(), 1)
    parent_x = parent.winfo_rootx()
    parent_y = parent.winfo_rooty()

    x = parent_x + max((parent_width - width) // 2, 0)
    y = parent_y + max(top_margin, 0)

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, min(x, max(screen_width - width, 0)))
    y = max(0, min(y, max(screen_height - height, 0)))

    window.geometry(f"{width}x{height}+{x}+{y}")
    return x, y
