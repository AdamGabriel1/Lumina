"""Compila todos os arquivos de examples/ que não estão no skip.txt.

O skip.txt (compartilhado com scripts/check_examples.sh) lista exemplos
que não são compiláveis como executáveis (bibliotecas sem main(),
exemplos que dependem de headers externos, etc.).

Antes, este teste passava por acidente: `lumina build` engolia o exit
code, então qualquer falha do linker era silenciosa. Agora que exit
codes propagam (ver tests/cli/test_exit_codes.py), precisamos respeitar
o skip.txt.

Este teste paraleliza os builds com um ThreadPoolExecutor — cada
subprocesso é I/O-bound em relação ao Python, então threads bastam.
O nome do binário/IR deriva do path do exemplo (examples/foo.lm →
examples/foo.ll, examples/foo), portanto não há corrida entre workers
desde que cada arquivo tenha nome único (o que é o caso).
"""
import concurrent.futures
import glob
import os
import pathlib
import subprocess
import sys

import pytest


def _load_skip_list(repo_root):
    """Lê `tests/features/skip.txt` (formato: <nome>.lm [motivo])."""
    skip_file = pathlib.Path(repo_root) / "tests" / "features" / "skip.txt"
    skip = set()
    if not skip_file.exists():
        return skip

    for raw in skip_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # primeira palavra é o nome do arquivo
        name = line.split()[0]
        skip.add(name)
    return skip


def _build_one(repo_root, path):
    """Compila um exemplo. Retorna (path, returncode, output)."""
    env = {**os.environ, "LUMINA_NO_COVERAGE": "1"}
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=120,
            env=env,
        )
        return path, r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        return path, 124, f"timeout após 120s\n{out}"


@pytest.mark.slow
@pytest.mark.smoke
def test_smoke_tests_examples(repo_root):
    examples = sorted(glob.glob(os.path.join(repo_root, "examples/*.lm")))
    assert len(examples) > 0, "Nenhum exemplo encontrado"

    skip_list = _load_skip_list(repo_root)
    targets = [
        e for e in examples
        if os.path.basename(e) not in skip_list
    ]
    assert targets, "Todos os exemplos estão na skip list?"

    workers = min(os.cpu_count() or 4, len(targets))
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for path, rc, out in pool.map(
            lambda p: _build_one(repo_root, p), targets
        ):
            if rc != 0:
                failures.append((os.path.basename(path), out[:500]))

    assert not failures, (
        f"{len(failures)} exemplo(s) falharam ao compilar:\n"
        + "\n".join(f"  · {name}: {err}" for name, err in failures)
    )