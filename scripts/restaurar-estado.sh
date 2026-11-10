#!/usr/bin/env bash
# Restaura PROJETO.md da branch projeto-estado. Nunca sobrescreve um local diferente sem --forcar.
# Saída: 0 restaurado/igual · 2 sem espelho remoto · 3 conflito (local ≠ remoto)
set -e
ROOT=$(git rev-parse --show-toplevel); cd "$ROOT"
git fetch -q origin projeto-estado 2>/dev/null || { echo "Sem branch projeto-estado no remoto." >&2; exit 2; }
for f in PROJETO.md PROJETO-ARQUIVO.md; do
  git cat-file -e "origin/projeto-estado:$f" 2>/dev/null || continue
  TMP=$(mktemp); git show "origin/projeto-estado:$f" > "$TMP"
  if [ ! -f "$f" ]; then mv "$TMP" "$f"; echo "$f restaurado"
  elif cmp -s "$TMP" "$f"; then rm "$TMP"; echo "$f já igual ao remoto"
  elif [ "$1" = "--forcar" ]; then mv "$TMP" "$f"; echo "$f substituído pela versão remota"
  else
    echo "CONFLITO em $f (local ≠ remoto). Diferenças (- local, + remoto):"
    diff -u "$f" "$TMP" | head -60 || true
    rm "$TMP"; CONFLITO=1
  fi
done
[ -z "$CONFLITO" ] || exit 3
