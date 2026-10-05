"""Cores ANSI compartilhadas entre o compilador e a CLI.

Único lugar do projeto que decide se cores devem ser emitidas.
Consumido por `lumina/errors.py` e `lumina_cli/utils.py`.
"""
import os
import sys


def _supports_color(stream=None):
    """Retorna True se o stream (default: stdout) aceita ANSI."""
    stream = stream or sys.stdout

    # Convenções internacionais
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True

    # Sem tty? Sem cor (redirecionamento, pipe, CI)
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False

    # Terminal "burro" (dumb)
    if os.environ.get("TERM") == "dumb":
        return False

    return True


# Decidido uma vez, no import. Se o stream mudar depois, chame refresh().
HAS_COLOR = _supports_color()


class Color:
    """Paleta ANSI. Vazia quando HAS_COLOR é False."""
    RESET     = "\033[0m"  if HAS_COLOR else ""
    BOLD      = "\033[1m"  if HAS_COLOR else ""
    DIM       = "\033[2m"  if HAS_COLOR else ""
    UNDERLINE = "\033[4m"  if HAS_COLOR else ""

    RED     = "\033[31m" if HAS_COLOR else ""
    GREEN   = "\033[32m" if HAS_COLOR else ""
    YELLOW  = "\033[33m" if HAS_COLOR else ""
    BLUE    = "\033[34m" if HAS_COLOR else ""
    MAGENTA = "\033[35m" if HAS_COLOR else ""
    CYAN    = "\033[36m" if HAS_COLOR else ""
    WHITE   = "\033[37m" if HAS_COLOR else ""

    BRIGHT_RED     = "\033[91m" if HAS_COLOR else ""
    BRIGHT_GREEN   = "\033[92m" if HAS_COLOR else ""
    BRIGHT_YELLOW  = "\033[93m" if HAS_COLOR else ""
    BRIGHT_BLUE    = "\033[94m" if HAS_COLOR else ""
    BRIGHT_MAGENTA = "\033[95m" if HAS_COLOR else ""
    BRIGHT_CYAN    = "\033[96m" if HAS_COLOR else ""
    BRIGHT_WHITE   = "\033[97m" if HAS_COLOR else ""

    BRIGHT_BLACK = "\033[90m" if HAS_COLOR else ""

    # Aliases semânticos (usados pela CLI)
    ERROR   = BRIGHT_RED
    SUCCESS = BRIGHT_GREEN
    WARN    = BRIGHT_YELLOW
    INFO    = BRIGHT_CYAN
    STEP    = BRIGHT_MAGENTA
    HEADER  = BOLD + BRIGHT_BLUE
    ARROW   = BRIGHT_CYAN
    PROMPT  = BOLD + BRIGHT_CYAN
    MUTED   = BRIGHT_BLACK


def refresh():
    """Recalcula HAS_COLOR e reatribui as constantes (raro, use com cuidado)."""
    global HAS_COLOR
    HAS_COLOR = _supports_color()
    for name, val in list(vars(Color).items()):
        if name.startswith("_") or callable(val):
            continue
        # Substitui cada código pelo equivalente com/sem cor
        # (implementação simples: reimporta o módulo)
    import importlib
    importlib.reload(sys.modules[__name__])
