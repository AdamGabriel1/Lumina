find . -type f \
  \( -name '*.py' -o -name '*.lm' -o -name '*.c' -o -name '*.h' -o -name '*.cpp' -o -name '*.hpp' \
     -o -name '*.rs' -o -name '*.go' -o -name '*.js' -o -name '*.json' -o -name '*.toml' \
     -o -name '*.md' -o -name '*.txt' -o -name '*.sh' -o -name '*.S' -o -name '*.html' \
     -o -name '*.css' -o -name '*.yml' -o -name '*.yaml' -o -name 'Makefile' -o -name 'LICENSE' \) \
  -not -path './.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' \
  -not -path './.venv/*' \
  -not -path './venv/*' \
  -not -path './dist/*' \
  -not -path './build/*' \
  -not -path './target/*' \
  -not -name '*.pyc' \
  -not -name '*.o' \
  -not -name '*.ll' \
  -not -name '*.wasm' \
  -not -name '*.vsix' \
  -not -name '*.wal' \
  -not -name 'lumina-ld' \
  -not -name '*.so' \
  -not -name '*.a' \
  -not -name '*.exe' \
  -not -name '*.bin' \
  -print | sort | while IFS= read -r f; do
    printf '\n\n===== FILE: %s =====\n\n' "$f"
    cat "$f"
  done > lumina_bundle.txt
