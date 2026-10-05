"""Comandos da CLI Lumina.

Re-exporta a API pública para que `from lumina_cli.commands import cmd_build`
continue funcionando exatamente como antes.
"""

from .errors import ERROR_FORMAT, set_error_format, report_error
from .new import cmd_new
from .install import cmd_install
from .doc import cmd_doc
from .build import cmd_build, cmd_check, cmd_run
from .test_suite import cmd_test
from .clean import cmd_clean
from .bind import cmd_bind
from .fmt import cmd_fmt, cmd_fmt_stdin, cmd_fmt_check_all
from .repl import cmd_repl


__all__ = [
    "ERROR_FORMAT",
    "set_error_format",
    "report_error",
    "cmd_new",
    "cmd_install",
    "cmd_doc",
    "cmd_build",
    "cmd_check",
    "cmd_run",
    "cmd_test",
    "cmd_clean",
    "cmd_bind",
    "cmd_fmt",
    "cmd_fmt_stdin",
    "cmd_fmt_check_all",
    "cmd_repl",
]
