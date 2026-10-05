"""Resolução de imports e parsing do módulo principal."""
import os
from collections import deque

from lumina.ast import ImportStmt
from lumina.errors import LuminaError
from lumina.lexer import Lexer
from lumina.parser import Parser

from ..utils import Color, paint, arrow, STD_DIR
from .paths import resolve_import_path


def parse_module(filename):
    """Parseia o módulo e resolve todos os imports de forma iterativa."""
    abs_path = os.path.abspath(filename)
    queue = deque([abs_path])
    visited = set()
    resolved_ast = []

    prelude_path = os.path.join(STD_DIR, "prelude.lm")
    if os.path.exists(prelude_path):
        queue.appendleft(prelude_path)

    while queue:
        current_file = queue.popleft()
        if current_file in visited:
            continue
        visited.add(current_file)

        try:
            with open(current_file, "r") as f:
                code = f.read()
        except Exception:
            continue

        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, current_file, code)
        ast = parser.parse()

        for node in ast:
            if isinstance(node, ImportStmt):
                # PATCH: delega para `resolve_import_path`, que é a
                # fonte única de verdade para resolução de imports.
                # Antes, essa lógica era duplicada (e podia divergir)
                # em `lumina_cli/utils.py::get_all_dependency_files`.
                try:
                    dep_path = resolve_import_path(node.filename)
                except FileNotFoundError:
                    raise LuminaError(
                        f"Módulo '{node.filename}' não encontrado.",
                        current_file, 0, 0, code,
                    )
                arrow(f"--> Importando módulo: "
                      f"{paint(node.filename, Color.BOLD)}")
                queue.append(dep_path)
            else:
                resolved_ast.append(node)

    return resolved_ast