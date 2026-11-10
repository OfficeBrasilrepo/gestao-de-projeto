"""Medição em tempo real da skill gestao-de-projeto (zero tokens quando silencioso).
  monitor.py fim     -> hook Stop: mede o contexto do turno, grava em .claude/gestao/medicao.csv e,
                        no momento certo, mostra ao USUÁRIO uma linha sugerindo /compact ou subir de nível.
  monitor.py janela  -> hook SessionStart: recalcula a janela de auto-compactação do projeto e grava
                        "autoCompactWindow" no .claude/settings.local.json (vale a partir da próxima abertura).
  monitor.py resumo  -> números do projeto, comparando com a linha de base.
  monitor.py status  -> uma linha: nível, % pronto, pendências bloqueantes, contexto atual.
  monitor.py linha-base -> mede os logs do projeto ANTES da skill (rodar uma vez, na adoção).
Entrada dos hooks: JSON no stdin com cwd, session_id, transcript_path."""
import csv, json, os, re, statistics, subprocess, sys, time

MIN, MAX, PADRAO = 100_000, 300_000, 150_000
# Avisos em TOKENS ABSOLUTOS, não em % da janela do usuário:
FIM_TAREFA = 0.70   # tarefa concluída e contexto >= 70% do ponto ideal -> sugere /compact
URGENTE = 0.90      # contexto >= 90% do limite automático -> salve o estado já
SEGUIR_MAX = 25     # modo Executar: continuações automáticas por mensagem do usuário
PARADA = "nada a seguir sem você"  # frase com que o Claude encerra quando tudo depende do usuário


def janela_ideal(base_pos_compact):
    """Ponto ideal de compactação: ~3x o que precisa ser relido após compactar, entre 100k e 300k (estimativa)."""
    if not base_pos_compact:
        return PADRAO
    return max(MIN, min(MAX, round(3 * base_pos_compact / 10_000) * 10_000))


def rede_seguranca(ideal):
    """Janela automática do projeto: folga de 40% acima do ponto ideal, para o aviso chegar antes."""
    return min(400_000, round(1.4 * ideal / 10_000) * 10_000)


def ler_transcript(caminho):
    """Retorna (contextos por turno, bases: início do chat e pós-compactação, nº de compactações)."""
    ctx, bases, n, depois = [], [], 0, True  # o 1º turno também é base: o custo fixo de abrir um chat
    try:
        f = open(caminho, encoding="utf-8")
    except OSError:
        return ctx, bases, n
    for linha in f:
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
            n, depois = n + 1, True
            continue
        m = d.get("message")
        if d.get("type") == "assistant" and isinstance(m, dict) and m.get("usage"):
            u = m["usage"]
            c = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            if ctx and c == ctx[-1]:
                continue
            ctx.append(c)
            if depois:
                bases.append(c)
                depois = False
    return ctx, bases, n


def ler_fim(caminho):
    """(último texto do Claude, nº de mensagens digitadas pelo usuário) — para o modo Executar seguir sozinho."""
    ultimo, usuario = "", 0
    try:
        f = open(caminho, encoding="utf-8")
    except OSError:
        return ultimo, usuario
    for linha in f:
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        m = d.get("message")
        if not isinstance(m, dict) or d.get("isMeta"):
            continue
        c = m.get("content")
        textos = [c] if isinstance(c, str) else [b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
        if not textos:
            continue
        if d.get("type") == "assistant":
            ultimo = textos[-1]
        elif d.get("type") == "user" and not any("[gestão]" in t for t in textos):
            usuario += 1
    return ultimo, usuario


def settings_path(cwd):
    return os.path.join(cwd, ".claude", "settings.local.json")


def janela_atual(cwd):
    """Limite automático em vigor: env > settings do projeto > settings do usuário. None = 'auto' (desconhecido)."""
    if os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "").isdigit():
        return int(os.environ["CLAUDE_CODE_AUTO_COMPACT_WINDOW"])
    for p in (settings_path(cwd), os.path.join(os.path.expanduser("~"), ".claude", "settings.json")):
        try:
            v = json.load(open(p, encoding="utf-8")).get("autoCompactWindow")
            if isinstance(v, int):
                return v
        except (OSError, ValueError):
            pass
    return None


def ler_ideal(cwd):
    try:
        return int(json.load(open(os.path.join(pasta_estado(cwd), "ideal.json"))).get("ideal") or PADRAO)
    except (OSError, ValueError):
        return PADRAO


def projeto(cwd):
    try:
        return open(os.path.join(cwd, "PROJETO.md"), encoding="utf-8").read()
    except OSError:
        return ""


def campo(texto, nome):
    m = re.search(rf"-\s*{nome}:\s*([^\n·]+)", texto, re.I)
    return m.group(1).strip() if m else ""


def pasta_estado(cwd):
    p = os.path.join(cwd, ".claude", "gestao")
    os.makedirs(p, exist_ok=True)
    return p


def ler_medicao(cwd):
    try:
        return list(csv.reader(open(os.path.join(pasta_estado(cwd), "medicao.csv"), encoding="utf-8")))
    except OSError:
        return []


def decidir_alerta(ctx, ideal, limite, tarefa_ativa, ja_avisado):
    """(faixa, texto) ou None. Avisa uma vez por faixa e por ciclo de compactação.
    ideal = ponto ideal do projeto (tokens); limite = compactação automática em vigor (None = desconhecido)."""
    if limite:
        ideal = min(ideal, int(0.8 * limite))  # janela do usuário menor que o ideal: o ideal se ajusta a ela
    k = lambda n: f"{n // 1000}k"
    info = f"contexto {k(ctx)} · ponto ideal {k(ideal)}" + (f" · automática em {k(limite)}" if limite else "")
    if limite and ctx >= URGENTE * limite and ja_avisado < 3:
        return 3, f"{info}: salve o estado e rode /compact já, antes da compactação automática"
    if ctx >= ideal and ja_avisado < 2:
        return 2, f"{info}: passou do ponto ideal; rode /compact ao fim do passo atual"
    if not tarefa_ativa and ctx >= FIM_TAREFA * ideal and ja_avisado < 1:
        return 1, f"{info}: tarefa concluída, bom momento para /compact"
    return None


def precisa_subir(nivel, sessoes, compactacoes, pico):
    return nivel.lower().startswith("leve") and (sessoes >= 2 or compactacoes >= 1 or pico >= 100_000)


def git(cwd, *args):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def motivo_desatualizado(mtime, respostas_desde, ultimo_commit, arquivos_alterados):
    """Texto do motivo ou None. Commit depois da última edição do PROJETO.md, ou muitas respostas com código mudando."""
    if ultimo_commit and ultimo_commit > mtime + 60:
        return "houve commit depois da última atualização do PROJETO.md"
    if respostas_desde >= 20 and arquivos_alterados:
        return f"{respostas_desde} respostas com arquivos alterados e o PROJETO.md parado"
    return None


def cmd_fim(dados):
    cwd = dados.get("cwd") or os.getcwd()
    texto = projeto(cwd)
    if not texto:
        return
    ctx, bases, compact = ler_transcript(dados.get("transcript_path", ""))
    if not ctx:
        return
    sid = dados.get("session_id", "?")
    est = pasta_estado(cwd)
    with open(os.path.join(est, "medicao.csv"), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([int(time.time()), sid, ctx[-1], compact])
    # estado de avisos por sessão + ciclo de compactação
    st_path = os.path.join(est, "avisos.json")
    try:
        st = json.load(open(st_path, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    chave = f"{sid}:{compact}"
    saida = {}
    ativa = campo(texto, "Tarefa") not in ("", "—", "-")
    alerta = decidir_alerta(ctx[-1], ler_ideal(cwd), janela_atual(cwd), ativa, st.get(chave, 0))
    if alerta:
        st[chave], msg = alerta
        saida["systemMessage"] = "[gestão] " + msg  # só o usuário vê; não gasta tokens
    # devolve a vez ao Claude para ele preparar o novo chat ou o /compact: urgente (3) na hora;
    # senão, uma vez por ciclo, quando já houve aviso e a tarefa terminou (mesmo que o aviso tenha vindo antes)
    urgente = alerta and alerta[0] == 3
    # novo chat só compensa se o contexto já passou do dobro da base (o novo começaria nela de novo, sem cache)
    fim_tarefa = (not ativa and st.get(chave, 0) >= 1 and not st.get(chave + ":p")
                  and ctx[-1] >= 2 * (bases[-1] if bases else 0))
    if (urgente or fim_tarefa) and not dados.get("stop_hook_active"):
        st[chave + ":p"] = 1
        info = f"[gestão] contexto {ctx[-1] // 1000}k. "
        saida["decision"] = "block"
        saida["reason"] = info + (
            "Contexto perto da compactação automática. Atualize Em andamento, sincronize e proponha já o novo chat do projeto "
            "(start_session com cwd na raiz, resumo do próximo passo, modelo e esforço pela Delegação) como cartão clicável; "
            "/compact só como segunda opção." if urgente else
            "Tarefa concluída com contexto alto. Atualize e sincronize o PROJETO.md e, conforme 'Pasta certa e novo chat' "
            "da skill gestao-de-projeto, proponha ao usuário em 1 linha: novo chat (start_session com cwd na raiz, modelo "
            "e esforço da próxima tarefa) se a próxima tarefa for separada, ou /compact se for continuação.")
    rows = ler_medicao(cwd)
    sessoes = len({r[1] for r in rows if len(r) > 1})
    if (precisa_subir(campo(texto, "Nível"), sessoes, compact, max(ctx))
            and not st.get("subir") and not dados.get("stop_hook_active")):
        st["subir"] = 1
        # subida automática: devolve a vez ao Claude uma única vez com a instrução
        saida["decision"] = "block"
        saida["reason"] = (f"[gestão] O projeto cresceu ({sessoes} sessões, {compact} compactações, pico {max(ctx) // 1000}k). "
                           "Suba agora a gestão para o nível completo, conforme a seção 'Níveis' da skill gestao-de-projeto, "
                           "e avise o usuário em uma linha.")
    # PROJETO.md desatualizado: devolve a vez ao Claude uma vez por versão do arquivo
    mtime = int(os.path.getmtime(os.path.join(cwd, "PROJETO.md")))
    if "decision" not in saida and not dados.get("stop_hook_active") and st.get("lembrete") != mtime:
        alterados = [l for l in git(cwd, "status", "--porcelain").splitlines() if "PROJETO" not in l]
        ult = git(cwd, "log", "-1", "--format=%ct")
        motivo = motivo_desatualizado(mtime, sum(1 for r in rows if len(r) > 1 and int(r[0]) > mtime),
                                      int(ult) if ult.isdigit() else 0, alterados)
        if motivo:
            st["lembrete"] = mtime
            saida["decision"] = "block"
            saida["reason"] = (f"[gestão] {motivo}. Atualize agora o PROJETO.md (Em andamento, Entregas, Decisões, "
                               "Pendências, Branches) com edições pontuais e sincronize se o nível for completo. Não fale disso ao usuário.")
    # modo Executar: não para enquanto houver o que avançar sem o usuário (limite por mensagem dele, contra custo sem fim)
    if "decision" not in saida and campo(texto, "Modo").lower().startswith("executar"):
        ultimo, usuario = ler_fim(dados.get("transcript_path", ""))
        seg = st.get(sid + ":seg", [usuario, 0])
        if seg[0] != usuario:
            seg = [usuario, 0]
        if PARADA not in ultimo.lower() and seg[1] < SEGUIR_MAX:
            seg[1] += 1
            saida["decision"] = "block"
            saida["reason"] = (f"[gestão] Modo Executar (contexto {ctx[-1] // 1000}k): não pare. Siga para a próxima entrega, "
                               "pendência ou passo que não depende do usuário, por prioridade, e atualize o PROJETO.md ao concluir "
                               "cada um. O que depende dele (aval, arquivos, push, publicação, merge que publica, ação irreversível) "
                               "fica registrado em Pendências/Perguntas e não trava o resto. Se nada mais puder avançar sem ele, "
                               f"termine com a frase exata '{PARADA}', um resumo curto do que espera dele e o próximo passo clicável (caixa de próximo passo com botões, ou cartão de novo chat se o contexto estiver alto).")
        st[sid + ":seg"] = seg
    json.dump({k: v for k, v in st.items() if k in ("subir", "lembrete") or k.startswith(sid)}, open(st_path, "w"))
    if saida:
        print(json.dumps(saida, ensure_ascii=False))


def cmd_janela(dados):
    cwd = dados.get("cwd") or os.getcwd()
    texto = projeto(cwd)
    if not texto:
        return
    pasta = os.path.dirname(dados.get("transcript_path", "")) or ""
    bases = []
    if os.path.isdir(pasta):
        for nome in sorted(os.listdir(pasta))[-30:]:
            if nome.endswith(".jsonl"):
                bases += ler_transcript(os.path.join(pasta, nome))[1]
    ideal = janela_ideal(statistics.median(bases) if bases else None)
    json.dump({"ideal": ideal, "amostras": len(bases)}, open(os.path.join(pasta_estado(cwd), "ideal.json"), "w"))
    nova = rede_seguranca(ideal)
    atual = janela_atual(cwd) or 0
    if atual and abs(nova - atual) / atual <= 0.20:
        return
    p = settings_path(cwd)
    try:
        cfg = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    cfg["autoCompactWindow"] = nova
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(cfg, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[gestão] ponto ideal {ideal // 1000}k; janela automática do projeto: {atual // 1000}k -> {nova // 1000}k (vale na próxima abertura)")


def pasta_logs(cwd):
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd))


def cmd_linha_base(dados):
    cwd = dados.get("cwd") or os.getcwd()
    # pastas extras: onde os chats antigos rodaram (ex.: a pasta-mãe), se não foi na raiz do projeto
    pastas = [pasta_logs(cwd)] + [pasta_logs(os.path.abspath(p)) for p in sys.argv[2:]]
    ctxs, compact, sessoes = [], 0, 0
    for pasta in filter(os.path.isdir, pastas):
        for nome in os.listdir(pasta):
            if nome.endswith(".jsonl"):
                c, _, n = ler_transcript(os.path.join(pasta, nome))
                if c:
                    ctxs += c
                    compact += n
                    sessoes += 1
    base = {"data": time.strftime("%Y-%m-%d"), "respostas": len(ctxs), "sessoes": sessoes, "compactacoes": compact,
            "ctx_medio": int(statistics.mean(ctxs)) if ctxs else None}
    json.dump(base, open(os.path.join(pasta_estado(cwd), "linha-base.json"), "w"))
    print(f"Linha de base: {len(ctxs)} respostas em {sessoes} sessões antes da skill"
          + (f", contexto médio {base['ctx_medio'] // 1000}k por resposta" if ctxs else " (sem histórico: a comparação começa do zero)"))


def comparar(atual, base):
    """'54k (antes: 80k, -32%)' ou só '54k' sem linha de base."""
    if not base:
        return f"{atual / 1000:.0f}k"
    return f"{atual / 1000:.0f}k (antes da skill: {base / 1000:.0f}k, {100 * (atual - base) / base:+.0f}%)"


def cmd_status(dados):
    cwd = dados.get("cwd") or os.getcwd()
    texto = projeto(cwd)
    if not texto:
        print("Sem PROJETO.md neste projeto.")
        return
    feitos, total = len(re.findall(r"- \[x\]", texto, re.I)), len(re.findall(r"- \[[ x]\]", texto, re.I))
    bloq = 0
    m = re.search(r"##\s*4\..*?(?=\n## |\Z)", texto, re.S)
    if m:
        for linha in m.group(0).splitlines()[3:]:
            cel = [c.strip() for c in linha.strip().strip("|").split("|")]
            bloq += len(cel) > 3 and cel[3].lower().startswith("s")
    rows = [r for r in ler_medicao(cwd) if len(r) > 3]
    ctx = f"{int(rows[-1][2]) // 1000}k" if rows else "?"
    pct = f"{100 * feitos // total}%" if total else "sem Definição de Pronto"
    print(f"Nível {campo(texto, 'Nível') or '?'} · pronto {pct} · {bloq} pendência(s) bloqueante(s) · "
          f"contexto {ctx} / ponto ideal {ler_ideal(cwd) // 1000}k · tarefa: {campo(texto, 'Tarefa') or '—'}")


def cmd_resumo(dados):
    cwd = dados.get("cwd") or os.getcwd()
    rows = [r for r in ler_medicao(cwd) if len(r) > 3]
    if not rows:
        print("Sem medições ainda.")
        return
    ctxs = [int(r[2]) for r in rows]
    try:
        base = json.load(open(os.path.join(pasta_estado(cwd), "linha-base.json"))).get("ctx_medio")
    except (OSError, ValueError):
        base = None
    print(f"Respostas medidas: {len(rows)} · sessões: {len({r[1] for r in rows})} · "
          f"contexto médio/resposta: {comparar(statistics.mean(ctxs), base)} · pico: {max(ctxs) / 1000:.0f}k · "
          f"ponto ideal: {ler_ideal(cwd) // 1000}k · automática: {(janela_atual(cwd) or 0) // 1000 or 'auto'}k")


def teste():
    assert janela_ideal(None) == 150_000 and janela_ideal(20_000) == 100_000 and janela_ideal(60_000) == 180_000
    assert rede_seguranca(150_000) == 210_000 and rede_seguranca(300_000) == 400_000
    assert decidir_alerta(100_000, 150_000, 350_000, True, 0) is None       # meio da tarefa, abaixo do ideal
    assert decidir_alerta(110_000, 150_000, 350_000, False, 0)[0] == 1      # tarefa concluída, >= 70% do ideal
    assert decidir_alerta(110_000, 150_000, 350_000, False, 1) is None      # já avisou nesta faixa
    assert decidir_alerta(160_000, 150_000, 350_000, True, 1)[0] == 2       # passou do ideal
    assert decidir_alerta(95_000, 150_000, 100_000, True, 0)[0] == 3        # usuário pôs 100k: urgente em tokens
    assert "contexto 95k" in decidir_alerta(95_000, 150_000, 100_000, True, 0)[1]
    assert decidir_alerta(160_000, 150_000, None, True, 0)[0] == 2          # janela 'auto' desconhecida
    assert decidir_alerta(60_000, 150_000, 100_000, False, 0)[0] == 1       # ideal vira 80k; 60k >= 70% dele
    assert precisa_subir("leve", 2, 0, 50_000) and not precisa_subir("completo", 5, 3, 300_000)
    assert not precisa_subir("leve", 1, 0, 50_000)
    assert motivo_desatualizado(1000, 3, 2000, []) is not None          # commit depois da edição
    assert motivo_desatualizado(1000, 25, 0, ["M a.ts"]) is not None    # muitas respostas e código mudando
    assert motivo_desatualizado(1000, 25, 0, []) is None                # só conversa: não incomoda
    assert motivo_desatualizado(1000, 5, 1030, ["M a.ts"]) is None      # commit junto da edição
    assert comparar(54_000, 80_000) == "54k (antes da skill: 80k, -32%)" and comparar(54_000, None) == "54k"
    print("ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "--teste":
        teste()
        sys.exit()
    try:
        dados = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
    except ValueError:
        dados = {}
    {"fim": cmd_fim, "janela": cmd_janela, "resumo": cmd_resumo, "status": cmd_status,
     "linha-base": cmd_linha_base}.get(modo, lambda d: print(__doc__))(dados)
