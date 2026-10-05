"""`lumina clean` — limpa cache e binários."""
import glob
import os
import subprocess

from ..utils import Color, paint, success, step


def cmd_clean():
    step("🧹 Limpando cache e binários...")

    if os.path.exists(".lumina_cache"):
        subprocess.run(["rm", "-rf", ".lumina_cache"])
        success("✅ Cache (.lumina_cache) removido.")

    for ext in ["*.ll", "*.wasm"]:
        for f in glob.glob(ext):
            os.remove(f)
            success(f"✅ Removido: {paint(f, Color.MUTED)}")

    known_outputs = {"programa_final", "lumina_test_bin", "output", "lumina_jit_temp"}
    for f in os.listdir("."):
        if f in known_outputs and os.path.isfile(f):
            os.remove(f)
            success(f"✅ Removido binário: {paint(f, Color.MUTED)}")

    success("Limpeza concluída!")
