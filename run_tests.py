#!/usr/bin/env python3
"""
Suíte standalone para tests/features/uncertain_features.lm.

Compila, roda, e valida cada linha esperada. ~5 segundos.
Não depende do pytest — útil pra pre-commit ou uso rápido.

Uso:
    python3 run_tests.py
    python3 run_tests.py tests/features/outro.lm
"""
import subprocess
import sys
import os


# Duplicado do conftest.py de propósito — run_tests.py é standalone.
# Se quiser manter DRY, mantenha os dois em sincronia.
EXPECTED_LINES = [
    "1. Slicing: ell",
    "2. Array indexing:",
    "3. Pipe: 10",
    "4. Pipe encadeado: 20",
    "5. Safe nav: 0",
    "6. Propagate: 10",
    "Segunda",
    "Ok: 5",
    "9. Short decl: 42",
    "10. Dentro do if: 100",
    "11. Início",
    "11. Defer executado",
    "11. Fim",
    "12. Assert OK",
    "13. Nome: João, Idade: 30",
    "14. Generics int: 10",
    "14. Generics float: 3.140000",
    "15. Valor profundo: 99",
    "16. Match guard: Grande",
    "17. Valor: 42",
    "18. Par: 10 20",
    "19. Cast: 10 3",
    "20. Ponteiro: 42",
    "21. Lambda: 20",
    "22. Lambda bloco: 30",
    "23. Trait default OK",
    "24. Comando: run",
    "=== Fim dos testes ===",
]


def run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/features/uncertain_features.lm"

    if not os.path.exists(target):
        print(f"❌ Arquivo '{target}' não encontrado.", flush=True)
        return 1

    print("🧹 Limpando cache...", flush=True)
    try:
        run(["python3", "-m", "lumina_cli.main", "clean"], timeout=20)
    except subprocess.TimeoutExpired:
        print("❌ 'clean' travou (>20s).", flush=True)
        return 1

    print(f"🔨 Compilando e rodando {target}...\n", flush=True)
    try:
        build = run(["python3", "-m", "lumina_cli.main", "run", target], timeout=60)
    except subprocess.TimeoutExpired as e:
        print("❌ 'run' travou (>60s).", flush=True)
        if e.stdout:
            print(e.stdout, flush=True)
        return 1

    output = build.stdout + build.stderr
    if build.returncode != 0:
        print("❌ Compilação falhou.\n", flush=True)
        print(output, flush=True)
        return 1

    passed = []
    failed = []
    for line in EXPECTED_LINES:
        if line in output:
            passed.append(line)
        else:
            failed.append(line)

    print("=" * 62, flush=True)
    print(f"📊 Resultado: {len(passed)}/{len(EXPECTED_LINES)} verificações OK", flush=True)
    print("=" * 62, flush=True)

    if failed:
        print("\n❌ Linhas esperadas que NÃO apareceram:\n", flush=True)
        for f in failed:
            print(f"  · {f}", flush=True)
        print("\n📄 Output completo:\n", flush=True)
        print(output, flush=True)
        return 1

    print("\n✅ Todos os testes passaram!\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())