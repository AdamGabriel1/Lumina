"""`lumina new` — cria projeto com lumina.toml + main.lm."""
import os

from ..utils import Color, paint, success


def cmd_new(project_name):
    os.makedirs(project_name, exist_ok=True)
    config = f"""[package]
name = "{project_name}"
version = "0.1.0"
entry = "main.lm"

[dependencies]

# Configuração de link (opcional)
# [link]
# libs = ["m", "raylib"]
# extra_objects = ["helper.cpp"]
# target = "wasm"
# extra_flags = ["-DFOO"]
"""
    with open(os.path.join(project_name, "lumina.toml"), "w") as f:
        f.write(config)

    main_code = (
        'fn main() -> int:\n'
        f'    print("Hello from {project_name}!")\n'
        '    return 0\n'
    )
    with open(os.path.join(project_name, "main.lm"), "w") as f:
        f.write(main_code)

    success(
        f"✅ Projeto '{paint(project_name, Color.BOLD + Color.BRIGHT_CYAN)}' "
        f"criado com sucesso!"
    )
