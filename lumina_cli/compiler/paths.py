"""Resolução de caminhos de módulos `.lm`.

Um `import "X"` em Lumina pode referenciar:

  1. `std/X`             → `<LUMINA_ROOT>/std/X.lm`
  2. caminho relativo    → `./X.lm` (relativo ao CWD)
  3. dependência         → `lumina_modules/X.lm`

Esta lógica estava duplicada em:
  - `lumina_cli/compiler/parse.py::parse_module`
  - `lumina_cli/utils.py::get_all_dependency_files`

Extraída para cá para que uma mudança de política (ex: adicionar
busca em `~/.lumina/modules/`, ou permitir `pkg://nome`) só precise
ser feita em um lugar.
"""
import os

from ..utils import STD_DIR


def resolve_import_path(import_name: str) -> str:
    """Resolve `import "X"` para um caminho **absoluto** de arquivo `.lm`.

    Args:
        import_name: nome como aparece no `import`, sem aspas.

    Returns:
        Caminho absoluto para o `.lm` correspondente.

    Raises:
        FileNotFoundError: se nenhum candidato existir em disco.
    """
    # 1. std/X → <LUMINA_ROOT>/std/X.lm
    if import_name.startswith("std/"):
        clean = import_name[len("std/"):]
        if clean.endswith(".lm"):
            clean = clean[:-3]
        path = os.path.join(STD_DIR, clean + ".lm")
        if os.path.exists(path):
            return path
        raise FileNotFoundError(
            f"Módulo '{import_name}' não encontrado em std/."
        )

    # 2. Caminho relativo direto (com ou sem extensão).
    if import_name.endswith(".lm"):
        if os.path.exists(import_name):
            return os.path.abspath(import_name)
    else:
        with_ext = import_name + ".lm"
        if os.path.exists(with_ext):
            return os.path.abspath(with_ext)

    # 3. Dependência instalada em lumina_modules/.
    mod_path = os.path.join("lumina_modules", import_name)
    if not mod_path.endswith(".lm"):
        mod_path += ".lm"
    if os.path.exists(mod_path):
        return os.path.abspath(mod_path)

    raise FileNotFoundError(f"Módulo '{import_name}' não encontrado.")
