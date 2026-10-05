import os
import re
import hashlib
from lumina.common.colors import Color, HAS_COLOR
import sys

# Stream para onde as mensagens de progresso vão.
# Padrão: stdout. Quando --error-format=json, é redirecionado para stderr
# (mantendo o stdout exclusivo para o JSON — convenção Unix).
_PROGRESS_STREAM = sys.stdout


def set_progress_stream(stream):
    """Redireciona mensagens de progresso (step/info/warn/etc)."""
    global _PROGRESS_STREAM
    _PROGRESS_STREAM = stream


def cprint(*args, color=Color.RESET, end='\n', sep=' '):
    text = sep.join(str(a) for a in args)
    print(f"{color}{text}{Color.RESET}", end=end, file=_PROGRESS_STREAM)

from lumina.common.paths import LUMINA_ROOT, STD_DIR

def paint(text, color):
    return f"{color}{text}{Color.RESET}"



def info(msg):    cprint(msg, color=Color.INFO)
def success(msg): cprint(msg, color=Color.SUCCESS)
def warn(msg):    cprint(msg, color=Color.WARN)
def error(msg):   cprint(msg, color=Color.ERROR)
def step(msg):    cprint(msg, color=Color.STEP)
def header(msg):  cprint(msg, color=Color.HEADER)
def arrow(msg):   cprint(msg, color=Color.ARROW)


def get_all_dependency_files(filename):
    """Coleta recursivamente todos os `.lm` dependentes (via imports).

    Usado para calcular o hash de cache — se qualquer dependência
    mudar, o cache é invalidado.

    PATCH: agora usa `resolve_import_path` (a mesma função que o
    compilador usa em `parse.py`), garantindo consistência entre
    "o que o compilador importa" e "o que o cache considera".

    A importação é feita dentro da função para evitar ciclo de import
    (`utils` → `compiler.paths` → `utils`).
    """
    from .compiler.paths import resolve_import_path

    files = set()

    def resolve(f):
        abs_f = os.path.abspath(f)
        if abs_f in files:
            return
        files.add(abs_f)
        try:
            with open(f, "r") as file:
                code = file.read()
        except Exception:
            return

        for match in re.finditer(r'import\s+"([^"]+)"', code):
            dep = match.group(1)
            try:
                dep_path = resolve_import_path(dep)
            except FileNotFoundError:
                # Ignora imports não resolvíveis — o objetivo aqui é
                # calcular hash, não validar. Se o arquivo não existe,
                # o `parse_module` vai reportar depois.
                continue
            resolve(dep_path)

    resolve(filename)
    return list(files)


def get_compiler_source_files():
    """Retorna todos os arquivos .py do compilador (lumina/ + lumina_cli/).

    Usado para invalidar o cache quando o próprio compilador muda, não só os .lm.
    """
    sources = []
    for root_pkg in ("lumina", "lumina_cli"):
        root_dir = os.path.join(LUMINA_ROOT, root_pkg)
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Ignora __pycache__
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith(".py"):
                    sources.append(os.path.join(dirpath, fn))
    return sources


def get_cache_hash(filename):
    hasher = hashlib.md5()

    # Fontes .lm do usuário + dependências
    deps = get_all_dependency_files(filename)
    for f in sorted(deps):
        try:
            with open(f, "rb") as file:
                hasher.update(file.read())
        except Exception:
            pass

    # Fontes do compilador — garante que mexer em .py invalida o cache
    for f in sorted(get_compiler_source_files()):
        try:
            with open(f, "rb") as file:
                hasher.update(file.read())
        except Exception:
            pass

    return hasher.hexdigest()