"""Hook SessionStart: imprime um resumo curto do PROJETO.md (só leitura).
Sem PROJETO.md: não imprime nada e sai 0."""
import json, os, re, sys

LIMITE = 6000  # ~1-2k tokens


def secoes(texto):
    """Mapeia título (## ou ###) -> linhas do bloco."""
    out, atual = {}, None
    for linha in texto.splitlines():
        m = re.match(r"#{2,3}\s+(?:\d+\.\s*)?(.+)", linha)
        if m:
            atual = m.group(1).strip().lower()
            out[atual] = []
        elif atual is not None:
            out[atual].append(linha)
    return out


def achar(sec, chave):
    return next((v for k, v in sec.items() if k.startswith(chave)), [])


def linhas_tabela(bloco):
    rows = [l for l in bloco if l.strip().startswith("|")]
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]  # pula cabeçalho e ---


def resumo(texto):
    sec = secoes(texto)
    partes = ["[gestao-de-projeto] Resumo de retomada do PROJETO.md (arquivo completo só se precisar):"]
    for nome in ("configuração", "em andamento"):
        corpo = [l for l in achar(sec, nome) if l.strip()]
        if corpo:
            partes.append(f"## {nome.capitalize()}\n" + "\n".join(corpo))
    bloq = [r for r in linhas_tabela(achar(sec, "pendências")) if len(r) > 3 and r[3].lower().startswith("s")]
    if bloq:
        partes.append("## Pendências bloqueantes\n" + "\n".join(" | ".join(r) for r in bloq))
    dec = linhas_tabela(achar(sec, "decisões"))[-3:]
    if dec:
        partes.append("## Últimas decisões\n" + "\n".join(" | ".join(r) for r in dec))
    perg = linhas_tabela(achar(sec, "perguntas"))
    if perg:
        partes.append(f"Perguntas sem resposta: {len(perg)}")
    return "\n\n".join(partes)[:LIMITE]


def main():
    cwd = os.getcwd()
    try:
        dados = json.loads(sys.stdin.read() or "{}")
        cwd = dados.get("cwd") or cwd
    except Exception:
        pass
    caminho = os.path.join(cwd, "PROJETO.md")
    if not os.path.isfile(caminho):
        return
    with open(caminho, encoding="utf-8") as f:
        sys.stdout.reconfigure(encoding="utf-8")
        print(resumo(f.read()))


if __name__ == "__main__":
    if "--teste" in sys.argv:
        t = ("## 1. Visão\n### Configuração\n- Modo: Autônomo\n### Em andamento\n- Tarefa: X\n"
             "## 3. Decisões\n|D|d|m|p|\n|-|-|-|-|\n|1|a|b|c|\n|2|e|f|g|\n"
             "## 4. Pendências\n|ID|A|P|B|Br|O|\n|-|-|-|-|-|-|\n|P1|trava|9|sim|-|u|\n|P2|leve|2|não|-|u|\n")
        r = resumo(t)
        assert "Modo: Autônomo" in r and "Tarefa: X" in r and "P1" in r and "P2" not in r and "e | f" in r, r
        print("ok")
    else:
        main()
