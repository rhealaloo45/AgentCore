"""Tkinter GUI wizard for ``roscoe init``.

Opens a native desktop window with dropdowns, checkboxes, and text fields.
Returns the same answers dict that ``_run_wizard`` (CLI) returns, so
``_apply_wizard`` works identically regardless of input method.

Falls back gracefully: if Tk is unavailable (headless server, no display),
the caller catches ``_TkUnavailable`` and uses the CLI wizard instead.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

_PROVIDERS = [
    ("OpenAI", "openai"),
    ("OpenRouter  (100+ models, one API key)", "openrouter"),
    ("Azure OpenAI", "azure_openai"),
    ("Anthropic", "anthropic"),
    ("Gemini", "gemini"),
    ("Ollama  (free, local, no API key)", "ollama"),
]

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "openrouter": "meta-llama/llama-3.1-8b-instruct",
    "azure_openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-1.5-pro",
    "ollama": "llama3.1",
}

_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "azure_openai": "AZURE_OPENAI_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": None,
}

_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
}

# --- Colors ---
BG = "#FAFAFA"
CARD_BG = "#FFFFFF"
ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
ACCENT_FG = "#FFFFFF"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
HEADING = "#111827"
LABEL_FG = "#374151"
CANCEL_BG = "#F3F4F6"
CANCEL_HOVER = "#E5E7EB"


class _TkUnavailable(Exception):
    pass


def _card(parent: tk.Widget, title: str, row: int) -> ttk.Frame:
    """Create a titled card frame with consistent styling."""
    outer = tk.Frame(parent, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
    outer.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 12))
    outer.columnconfigure(0, weight=1)

    header = tk.Frame(outer, bg=CARD_BG)
    header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
    tk.Label(
        header, text=title, font=("Helvetica", 12, "bold"),
        fg=HEADING, bg=CARD_BG, anchor="w",
    ).pack(side="left")

    body = tk.Frame(outer, bg=CARD_BG)
    body.grid(row=1, column=0, sticky="ew", padx=16, pady=(6, 14))
    body.columnconfigure(1, weight=1)
    return body


def _label(parent: tk.Widget, text: str, row: int, col: int = 0, **kw: object) -> tk.Label:
    lbl = tk.Label(parent, text=text, fg=LABEL_FG, bg=CARD_BG, anchor="w")
    lbl.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3, **kw)
    return lbl


def _entry(parent: tk.Widget, var: tk.Variable, row: int, col: int = 1, width: int = 32) -> ttk.Entry:
    e = ttk.Entry(parent, textvariable=var, width=width)
    e.grid(row=row, column=col, sticky="w", pady=3, columnspan=2)
    return e


def _checkbox(parent: tk.Widget, text: str, var: tk.BooleanVar, row: int, col: int = 0) -> ttk.Checkbutton:
    cb = ttk.Checkbutton(parent, text=text, variable=var)
    cb.grid(row=row, column=col, sticky="w", pady=2, columnspan=2)
    return cb


def _spinbox(parent: tk.Widget, var: tk.Variable, row: int, col: int, *, from_: float, to: float,
             increment: float = 1, width: int = 7) -> ttk.Spinbox:
    sb = ttk.Spinbox(parent, from_=from_, to=to, increment=increment, textvariable=var, width=width)
    sb.grid(row=row, column=col, sticky="w", pady=3, padx=(0, 4))
    return sb


def _hint(parent: tk.Widget, text: str, row: int, col: int = 1) -> tk.Label:
    lbl = tk.Label(parent, text=text, fg=MUTED, bg=CARD_BG, font=("Helvetica", 10))
    lbl.grid(row=row, column=col, sticky="w", pady=0, columnspan=2)
    return lbl


def run_wizard_gui(project_name: str) -> dict | None:
    """Open the GUI wizard. Returns answers dict, or None if user cancelled."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise _TkUnavailable(str(exc)) from exc

    root.title(f"roscoe — new agent: {project_name}")
    root.configure(bg=BG)
    root.resizable(False, False)

    result: dict | None = None

    style = ttk.Style(root)
    style.theme_use("clam" if "clam" in style.theme_names() else style.theme_use())
    style.configure("TEntry", fieldbackground="#FFFFFF")
    style.configure("TSpinbox", fieldbackground="#FFFFFF")
    style.configure("TCombobox", fieldbackground="#FFFFFF")
    style.configure("TCheckbutton", background=CARD_BG)

    # --- Scrollable container ---
    container = tk.Frame(root, bg=BG)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1)

    content_row = 0

    # ===== Header =====
    header_frame = tk.Frame(container, bg=BG)
    header_frame.grid(row=content_row, column=0, sticky="ew", padx=24, pady=(20, 4))
    tk.Label(
        header_frame, text="roscoe", font=("Helvetica", 22, "bold"),
        fg=ACCENT, bg=BG,
    ).pack(side="left")
    content_row += 1

    tk.Label(
        container, text=f"Configure your new agent: {project_name}",
        font=("Helvetica", 13), fg=HEADING, bg=BG, anchor="w",
    ).grid(row=content_row, column=0, sticky="w", padx=24, pady=(0, 2))
    content_row += 1

    tk.Label(
        container,
        text="All choices are saved to agent_config.yaml. You can edit it anytime.",
        font=("Helvetica", 10), fg=MUTED, bg=BG, anchor="w",
    ).grid(row=content_row, column=0, sticky="w", padx=24, pady=(0, 16))
    content_row += 1

    # ===== Card 1: LLM Provider =====
    card1 = _card(container, "LLM Provider", content_row)
    content_row += 1

    provider_var = tk.StringVar(value="openai")
    provider_labels = [label for label, _ in _PROVIDERS]

    _label(card1, "Provider", 0)
    provider_combo = ttk.Combobox(
        card1, textvariable=provider_var, values=provider_labels, state="readonly", width=34
    )
    provider_combo.current(0)
    provider_combo.grid(row=0, column=1, sticky="w", pady=3, columnspan=2)

    def _provider_key() -> str:
        idx = provider_combo.current()
        return _PROVIDERS[idx][1] if idx >= 0 else "openai"

    _label(card1, "Model", 1)
    model_var = tk.StringVar(value=_DEFAULT_MODELS["openai"])
    model_entry = _entry(card1, model_var, 1)

    _label(card1, "Temperature", 2)
    temp_var = tk.DoubleVar(value=0.1)
    _spinbox(card1, temp_var, 2, 1, from_=0.0, to=2.0, increment=0.1)
    _hint(card1, "0.0 = precise, 1.0 = creative", 2, 2)

    # Azure deployment (hidden by default)
    azure_label = _label(card1, "Deployment", 3)
    azure_var = tk.StringVar()
    azure_entry = _entry(card1, azure_var, 3)
    azure_label.grid_remove()
    azure_entry.grid_remove()

    # Custom base URL (openai only)
    custom_url_var = tk.BooleanVar(value=False)
    url_cb = _checkbox(card1, "Custom endpoint (Together, etc.)", custom_url_var, 4)
    base_url_var = tk.StringVar()
    base_url_entry = _entry(card1, base_url_var, 5, width=40)
    base_url_entry.grid_remove()

    def _on_custom_toggle(*_: object) -> None:
        if custom_url_var.get():
            base_url_entry.grid()
        else:
            base_url_entry.grid_remove()

    custom_url_var.trace_add("write", _on_custom_toggle)

    def _on_provider_change(*_: object) -> None:
        key = _provider_key()
        model_var.set(_DEFAULT_MODELS.get(key, ""))
        if key == "azure_openai":
            azure_label.grid()
            azure_entry.grid()
        else:
            azure_label.grid_remove()
            azure_entry.grid_remove()
        if key == "openai":
            url_cb.grid()
        else:
            url_cb.grid_remove()
            base_url_entry.grid_remove()

    provider_combo.bind("<<ComboboxSelected>>", _on_provider_change)

    # ===== Card 2: Middleware =====
    card2 = _card(container, "Middleware", content_row)
    content_row += 1

    cost_var = tk.BooleanVar(value=True)
    _checkbox(card2, "Cost tracking — estimate USD per run", cost_var, 0)

    rate_var = tk.BooleanVar(value=True)
    _checkbox(card2, "Rate limiting", rate_var, 1)
    _label(card2, "RPM", 1, 2)
    rpm_var = tk.IntVar(value=60)
    _spinbox(card2, rpm_var, 1, 3, from_=1, to=10000)

    retry_var = tk.BooleanVar(value=True)
    _checkbox(card2, "Auto-retry on transient failures", retry_var, 2)
    _label(card2, "Attempts", 2, 2)
    retry_attempts_var = tk.IntVar(value=3)
    _spinbox(card2, retry_attempts_var, 2, 3, from_=1, to=10)

    audit_var = tk.BooleanVar(value=True)
    _checkbox(card2, "Audit logging — JSONL record of every run", audit_var, 3)

    # ===== Card 3: Human-in-the-loop =====
    card3 = _card(container, "Human-in-the-loop", content_row)
    content_row += 1

    hitl_var = tk.BooleanVar(value=False)
    _checkbox(card3, "Require approval before running certain tools", hitl_var, 0)

    _label(card3, "Tool names", 1)
    approval_var = tk.StringVar(value="send_email, delete_record")
    approval_entry = _entry(card3, approval_var, 1, width=40)
    _hint(card3, "Comma-separated function names, e.g. send_email, submit_payment", 2)

    # ===== Card 4: Memory =====
    card4 = _card(container, "Memory", content_row)
    content_row += 1

    conv_var = tk.BooleanVar(value=True)
    _checkbox(card4, "Conversation memory — remembers within a session", conv_var, 0)
    _label(card4, "Window size", 0, 2)
    window_var = tk.IntVar(value=10)
    _spinbox(card4, window_var, 0, 3, from_=1, to=100)

    persist_var = tk.BooleanVar(value=False)
    _checkbox(card4, "Persistent memory — remembers across sessions (sqlite)", persist_var, 1)

    # ===== Buttons =====
    btn_frame = tk.Frame(container, bg=BG)
    btn_frame.grid(row=content_row, column=0, sticky="e", padx=24, pady=(4, 20))

    def _on_create() -> None:
        nonlocal result
        provider = _provider_key()

        base_url = _BASE_URLS.get(provider)
        if provider == "openai" and custom_url_var.get() and base_url_var.get().strip():
            base_url = base_url_var.get().strip()

        approval_tools: list[str] = []
        if hitl_var.get():
            approval_tools = [t.strip() for t in approval_var.get().split(",") if t.strip()]

        result = {
            "provider": provider,
            "model": model_var.get().strip() or _DEFAULT_MODELS.get(provider, ""),
            "temperature": temp_var.get(),
            "base_url": base_url,
            "azure_deployment": azure_var.get().strip() or None if provider == "azure_openai" else None,
            "env_key": _ENV_KEYS.get(provider),
            "cost_tracking": cost_var.get(),
            "rate_limiting": rate_var.get(),
            "rpm": rpm_var.get(),
            "retry": retry_var.get(),
            "retry_attempts": retry_attempts_var.get(),
            "audit": audit_var.get(),
            "conversation_memory": conv_var.get(),
            "window_size": window_var.get(),
            "persistent_memory": persist_var.get(),
            "human_approval": hitl_var.get(),
            "approval_tools": approval_tools,
        }
        root.destroy()

    def _on_cancel() -> None:
        root.destroy()

    cancel_btn = tk.Button(
        btn_frame, text="Cancel", command=_on_cancel,
        bg=CANCEL_BG, fg=LABEL_FG, activebackground=CANCEL_HOVER,
        relief="flat", padx=16, pady=6, font=("Helvetica", 11),
        cursor="hand2", highlightthickness=0, bd=0,
    )
    cancel_btn.pack(side="left", padx=(0, 10))

    create_btn = tk.Button(
        btn_frame, text="Create Project", command=_on_create,
        bg=ACCENT, fg=ACCENT_FG, activebackground=ACCENT_HOVER,
        activeforeground=ACCENT_FG,
        relief="flat", padx=20, pady=6, font=("Helvetica", 11, "bold"),
        cursor="hand2", highlightthickness=0, bd=0,
    )
    create_btn.pack(side="left")

    # --- Center on screen ---
    root.update_idletasks()
    w = max(root.winfo_width(), 560)
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()
    return result
