"""Formato de erro global e report.

Suporta `--error-format=text|json`. Em modo JSON, progresso vai para
stderr e stdout fica exclusivo para a linha JSON (pipe-safe).
"""
import json
import sys

from ..utils import error, set_progress_stream


ERROR_FORMAT = "text"


def set_error_format(fmt: str):
    """Define o formato de erro global."""
    global ERROR_FORMAT
    if fmt not in ("text", "json"):
        fmt = "text"
    ERROR_FORMAT = fmt

    if fmt == "json":
        set_progress_stream(sys.stderr)
    else:
        set_progress_stream(sys.stdout)


def report_error(e):
    """Reporta um erro respeitando ERROR_FORMAT."""
    if ERROR_FORMAT == "json":
        try:
            payload = e.to_dict()
        except AttributeError:
            payload = {"type": "error", "message": str(e)}
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    else:
        error(e)
