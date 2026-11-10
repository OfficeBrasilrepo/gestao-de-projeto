#!/usr/bin/env bash
# Espelha PROJETO.md (e PROJETO-ARQUIVO.md) na branch órfã projeto-estado do origin.
# Não mexe na branch atual, cria a branch na 1ª vez, não faz commit vazio.
set -e
ROOT=$(git rev-parse --show-toplevel)
[ -f "$ROOT/PROJETO.md" ] || { echo "PROJETO.md não encontrado em $ROOT" >&2; exit 1; }
git remote get-url origin >/dev/null 2>&1 || { echo "Sem remoto 'origin': estado só existe nesta máquina." >&2; exit 2; }
TMP=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$TMP" 2>/dev/null || true' EXIT
git fetch -q origin projeto-estado 2>/dev/null || true
if git show-ref --verify --quiet refs/remotes/origin/projeto-estado; then
  git worktree add -q -B projeto-estado "$TMP" origin/projeto-estado
elif git show-ref --verify --quiet refs/heads/projeto-estado; then
  git worktree add -q "$TMP" projeto-estado  # push anterior falhou: reaproveita a branch local
else
  git worktree add -q --detach "$TMP"
  git -C "$TMP" checkout -q --orphan projeto-estado
  git -C "$TMP" rm -rfq . 2>/dev/null || true
fi
cp "$ROOT/PROJETO.md" "$TMP/"
[ -f "$ROOT/PROJETO-ARQUIVO.md" ] && cp "$ROOT/PROJETO-ARQUIVO.md" "$TMP/" || true
git -C "$TMP" add -f PROJETO.md PROJETO-ARQUIVO.md 2>/dev/null || git -C "$TMP" add -f PROJETO.md
if git -C "$TMP" diff --cached --quiet; then
  echo "estado já sincronizado"
else
  git -C "$TMP" commit -qm "docs(projeto): atualiza estado"
  echo "commit local feito"
fi
# push a partir da raiz: remotos com caminho relativo continuam válidos
if git -C "$ROOT" push -q -u origin projeto-estado; then echo "estado sincronizado"
else echo "push falhou: registre a pendência 'sincronizar estado'" >&2; exit 4; fi
