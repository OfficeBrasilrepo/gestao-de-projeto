# gestao-de-projeto (skill do Claude Code)

Memória viva do projeto (`PROJETO.md`): decisões, entregas, pendências, branches, sincronização online e compactação de contexto no momento certo.

## Instalar em outro computador
Requisitos: Claude Code, Git (no Windows, Git Bash) e Python 3.

```bash
git clone https://github.com/OfficeBrasilrepo/gestao-de-projeto.git ~/.claude/skills/gestao-de-projeto
```

Atualizar depois:

```bash
git -C ~/.claude/skills/gestao-de-projeto pull
```

Abra o Claude Code num projeto e diga "usar a skill gestao-de-projeto neste projeto". Ela cria o `PROJETO.md` e pede permissão para instalar os hooks. Se o Python da máquina se chamar `python3`, troque `python` por `python3` nos comandos dos hooks.

## Arquivos
- `SKILL.md`: fluxo e regras centrais.
- `modelo-PROJETO.md`: modelo do arquivo de estado.
- `git.md`, `compactacao.md`, `design.md`: lidos só quando o assunto aparece.
- `scripts/`: `monitor.py` (medição, avisos, status), `resumo-retomada.py` (hook de abertura), `sync-estado.sh` / `restaurar-estado.sh` (espelho na branch `projeto-estado`), `comparar-visual.mjs` (antes/depois com Playwright).
