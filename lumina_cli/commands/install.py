"""`lumina install` — baixa dependências github:* para lumina_modules/."""
import os
import subprocess

try:
    import tomllib
except ImportError:
    tomllib = None

from ..utils import Color, paint, info, success, warn
from .errors import report_error


def cmd_install():
    if not os.path.exists("lumina.toml"):
        report_error("Nenhum arquivo 'lumina.toml' encontrado no diretório atual.")
        return

    if tomllib is None:
        report_error("tomllib não disponível. Use Python 3.11+.")
        return

    with open("lumina.toml", "rb") as f:
        config = tomllib.load(f)

    deps = config.get("dependencies", {})
    if not deps:
        info("Nenhuma dependência encontrada no lumina.toml.")
        return

    os.makedirs("lumina_modules", exist_ok=True)

    for pkg_name, source in deps.items():
        if not source.startswith("github:"):
            warn(f"⚠️  Fonte inválida para {paint(pkg_name, Color.BOLD)}. "
                 f"Use 'github:usuario/repo'.")
            continue

        repo_path = source.split(":")[1]
        url = f"https://github.com/{repo_path}.git"
        dest = os.path.join("lumina_modules", pkg_name)

        if os.path.exists(dest):
            info(f"🔄 Atualizando pacote '{paint(pkg_name, Color.BOLD)}'...")
            try:
                subprocess.run(["git", "-C", dest, "pull"], check=True)
                success(f"✅ Pacote '{pkg_name}' atualizado.")
            except subprocess.CalledProcessError:
                report_error(f"Falha ao atualizar {pkg_name}.")
        else:
            info(f"⬇️  Baixando pacote '{paint(pkg_name, Color.BOLD)}' de {url}...")
            try:
                subprocess.run(["git", "clone", url, dest], check=True)
                success(f"✅ Pacote '{pkg_name}' instalado em lumina_modules/{pkg_name}")
            except subprocess.CalledProcessError:
                report_error(f"Falha ao baixar o repositório {url}")
