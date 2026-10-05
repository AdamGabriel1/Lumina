#!/usr/bin/env bash
# context.sh — gera bundles enxutos de contexto para IA.
# Uso: ./scripts/context.sh <bundle>
# Bundles: docs | docs-lang | docs-internals | docs-engineering
#          lang | cli | std | all | tree
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p ctx

COMMON_IGNORE="**/__pycache__/**,**/*.pyc,**/.venv/**,**/node_modules/**,CHANGELOG.md"

case "${1:-}" in
  # ------- Documentação -------
  docs)
    # Visão geral enxuta: exclui engineering (pesado) e guias longos.
    repomix \
      --include "README.md,llms.txt,docs/index.md,docs/README.md,docs/getting-started/**,docs/internals/arquitetura.md" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/docs.xml ;;

  docs-lang)
    # Linguagem + stdlib + ferramental + CLI (para "como uso X?")
    repomix \
      --include "docs/guia/**,docs/referencia/**,llms.txt" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/docs-lang.xml ;;

  docs-internals)
    # Pipeline interno (para "como funciona X?")
    repomix \
      --include "docs/internals/**,docs/engineering/decisoes/**,lumina.toml" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/docs-internals.xml ;;

  docs-engineering)
    # Meta-doc do time (só quando for sobre perf/bugs/testes)
    repomix \
      --include "docs/engineering/**,CHANGELOG.md" \
      --output ctx/docs-engineering.xml ;;

  # ------- Código -------
  lang)
    repomix \
      --include "lumina/**,lumina_core/**,pyproject.toml" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/lang.xml ;;

  cli)
    repomix \
      --include "lumina_cli/**,pyproject.toml,lumina.toml,examples/MeuBanco/lumina.toml" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/cli.xml ;;

  std)
    repomix \
      --include "std/**,docs/guia/stdlib.md" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/std.xml ;;

  # ------- Combinados -------
  internals|all-internals)
    # Código do compilador + docs de internals (para refactor profundo)
    repomix \
      --include "lumina/**,lumina_core/**,docs/internals/**,docs/engineering/decisoes/**,pyproject.toml" \
      --ignore "$COMMON_IGNORE" \
      --output ctx/internals.xml ;;

  all)
    repomix --output ctx/all.xml ;;

  # ------- Árvore -------
  tree)
    tree -L 3 -I '__pycache__|node_modules|*.pyc|.venv|*.ll|*.wasm|*.o|target|ctx' \
      > ctx/tree.txt && cat ctx/tree.txt ;;

  *)
    echo "uso: $0 {docs|docs-lang|docs-internals|docs-engineering|lang|cli|std|internals|all|tree}"
    echo ""
    echo "Recomendado:"
    echo "  docs              — visão geral (pergunta conceitual)"
    echo "  docs-lang         — como usar X na linguagem"
    echo "  docs-internals    — como funciona X por dentro"
    echo "  docs-engineering  — perf, bugs, testes"
    echo "  lang              — bug/refactor no compilador"
    echo "  cli               — bug/refactor na CLI"
    echo "  std               — trabalhar na stdlib"
    echo "  internals         — lang + docs-internals juntos"
    echo "  tree              — só orientação rápida"
    exit 1 ;;
esac

# Relatório de tokens
echo ""
printf '%-24s %8s  %s\n' "BUNDLE" "BYTES" "≈TOKENS"
for f in ctx/*.xml ctx/tree.txt; do
  [ -f "$f" ] || continue
  bytes=$(wc -c <"$f")
  printf '%-24s %8s  ~%d\n' "$(basename "$f")" "$(numfmt --to=iec "$bytes")" "$((bytes / 4))"
done
