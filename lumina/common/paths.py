"""Localização de diretórios do projeto Lumina.

Fonte única de verdade para `LUMINA_ROOT` e `STD_DIR`. Consumido pelo
compilador (`lumina/`) e, opcionalmente, pela CLI (`lumina_cli/`).

Antes, `lumina_cli/utils.py` calculava os caminhos por conta própria.
Como `lumina/` (compilador) não pode importar de `lumina_cli/` (CLI),
este módulo vive em `lumina/common/` e ambos podem usá-lo sem
violar a direção de dependência.

Layout esperado em disco:

    <LUMINA_ROOT>/
    ├── lumina/
    │   └── common/
    │       └── paths.py       ← este arquivo
    ├── lumina_cli/
    ├── std/
    │   ├── prelude.lm
    │   ├── io.lm
    │   └── ...
    └── ...

`LUMINA_ROOT` é derivado do path do pacote. Funciona tanto em
instalação editable (`pip install -e .`) quanto em clone direto.
"""
import os


# __file__ = <LUMINA_ROOT>/lumina/common/paths.py
# dirname x3 = <LUMINA_ROOT>
LUMINA_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STD_DIR = os.path.join(LUMINA_ROOT, "std")


__all__ = ["LUMINA_ROOT", "STD_DIR"]
