"""Self-contained confirmation dialogs for Streamlit 1.38.0."""

from collections.abc import Callable

import streamlit as st


def show(
    message: str,
    *,
    key: str,
    title: str = "Please confirm",
    on_confirm: Callable[[], object],
    on_cancel: Callable[[], object] | None = None,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
) -> None:
    """Open a confirmation dialog from a page's action branch.

    Args:
        message: Markdown content displayed inside the dialog.
        key: Stable, app-wide identifier used to namespace the dialog buttons.
        title: Nonempty dialog heading.
        on_confirm: Zero-argument callback invoked by the confirm button.
        on_cancel: Optional zero-argument callback for explicit cancellation.
        confirm_label: Label for the primary action button.
        cancel_label: Label for the cancellation button.

    Callback return values are ignored. A successful action reruns the app to
    close the dialog. Callback exceptions propagate unchanged, and an action
    cannot execute again within the same opening, even after a failure.

    Call only when an action should open the dialog, such as inside an
    ``if st.button(...)`` branch. Do not call unconditionally on every rerun,
    from a widget callback, or inside another dialog. Streamlit allows only
    one dialog invocation per script run.

    Streamlit 1.38.0 does not report X, Escape, or outside-click dismissal;
    these close the dialog without invoking either callback. No synchronous
    confirmation result or caller-managed session state is required.

    Raises:
        ValueError: A required string is empty or contains only whitespace.
        TypeError: A string argument or callback has an invalid type.
    """
    for name, value in (
        ("message", message),
        ("key", key),
        ("title", title),
        ("confirm_label", confirm_label),
        ("cancel_label", cancel_label),
    ):
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if not value.strip():
            raise ValueError(f"{name} must not be empty")

    if not callable(on_confirm):
        raise TypeError("on_confirm must be callable")
    if on_cancel is not None and not callable(on_cancel):
        raise TypeError("on_cancel must be callable or None")

    # Fragment reruns retain this opening's closure; a new show() starts fresh.
    handled = False
    button_prefix = f"_confirm_dialog:{key}"

    @st.dialog(title, width="small")
    def dialog() -> None:
        nonlocal handled

        st.write(message)
        if handled:
            if st.button("Close", key=f"{button_prefix}:close"):
                st.rerun()
            return

        cancel_column, confirm_column = st.columns(2)
        with cancel_column:
            cancelled = st.button(cancel_label, key=f"{button_prefix}:cancel")
        with confirm_column:
            confirmed = st.button(
                confirm_label,
                key=f"{button_prefix}:confirm",
                type="primary",
            )

        if cancelled or confirmed:
            # Consume the action before user code, including callbacks that fail.
            handled = True
            callback = on_cancel if cancelled else on_confirm
            if callback is not None:
                callback()
            st.rerun()

    dialog()
