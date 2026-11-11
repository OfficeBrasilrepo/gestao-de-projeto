"""Medição em tempo real da skill gestao-de-projeto (zero tokens quando silencioso).
  monitor.py fim     -> hook Stop: mede o contexto do turno, grava em .claude/gestao/medicao.csv e,
                        no momento certo, avisa o usuário e devolve a vez ao Claude (novo chat, subir nível,
                        PROJETO.md velho, modo Executar seguir).
  monitor.py janela  -> hook SessionStart: recalcula a janela de auto-compactação do projeto e grava
                        "autoCompactWindow" no .claude/settings.local.json (vale a partir da próxima abertura).
  monitor.py resumo  -> números do projeto, comparando com a linha de base.
  monitor.py status  -> uma linha: nível, % pronto, pendências bloqueantes, contexto atual.
  monitor.py linha-base -> mede os logs do projeto ANTES da skill (rodar uma vez, na adoção).
Entrada dos hooks: JSON no stdin com cwd, session_id, transcript_path."""
import csv, json, os, re, statistics, subprocess, sys, time, unicodedata

MIN, MAX, PADRAO = 100_000, 300_000, 150_000
# Avisos em TOKENS ABSOLUTOS, não em % da janela do usuário:
FIM_TAREFA = 0.70   # tarefa concluída e contexto >= 70% do ponto ideal -> sugere /compact
URGENTE = 0.90      # contexto >= 90% do limite automático -> salve o estado já
SEGUIR_MAX = 25     # modo Executar: continuações automáticas por mensagem do usuário
DELEG_MIN = 15     # chamadas no chat principal numa entrega a partir das quais zero delegação é falha
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
    """Uma passada no transcript. Retorna dict com: ctx (contexto por turno), bases (logo após cada
    compactação), abertura (1º turno: custo fixo de abrir um chat), compact (nº de compactações),
    ultimo (último texto do Claude) e usuario (nº de mensagens digitadas pelo usuário)."""
    r = {"ctx": [], "bases": [], "abertura": 0, "compact": 0, "ultimo": "", "usuario": 0,
         "ferramentas": 0, "delegacoes": []}  # chamadas feitas no próprio chat × subagentes/novos chats
    depois = False
    try:
        f = open(caminho, encoding="utf-8")
    except OSError:
        return r
    with f:
        for linha in f:
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("isSidechain"):  # linhas de subagente não são o chat principal
                continue
            if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
                r["compact"] += 1
                depois = True
                continue
            m = d.get("message")
            if not isinstance(m, dict):
                continue
            if d.get("type") == "assistant" and m.get("usage"):
                u = m["usage"]
                c = sum(u.get(x) or 0 for x in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                if not r["ctx"] or c != r["ctx"][-1]:
                    r["ctx"].append(c)
                    r["abertura"] = r["abertura"] or c
                    if depois:
                        r["bases"].append(c)
                        depois = False
            if d.get("isMeta") or d.get("isCompactSummary"):
                continue
            c = m.get("content")
            if d.get("type") == "assistant" and isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        delegacao(b, r)
            textos = [c] if isinstance(c, str) else [b.get("text") or "" for b in c or [] if isinstance(b, dict) and b.get("type") == "text"]
            if not textos:
                continue
            if d.get("type") == "assistant":
                r["ultimo"] = textos[-1]
            elif d.get("type") == "user" and digitado(textos[0]):
                r["usuario"] += 1
    return r


def delegacao(b, r):
    """Conta uma chamada de ferramenta: subagente (Agent/Task) ou novo chat entra em delegacoes, com o modelo."""
    nome, inp = b.get("name", ""), b.get("input") or {}
    if nome in ("Agent", "Task"):
        r["delegacoes"].append(f"{inp.get('model') or 'herdado'}/{inp.get('effort') or '-'}")
    elif nome.endswith("start_session"):
        r["delegacoes"].append(f"chat {inp.get('model') or 'herdado'}")
    else:
        r["ferramentas"] += 1


def fechamento(antes, agora, n_ferr, n_deleg, delegs):
    """Texto do fechamento de entrega ou None. antes/agora = campo Tarefa; fecha quando sai de uma tarefa."""
    if antes in ("", "—", "-") or id_tarefa(antes) == id_tarefa(agora):
        return None
    resumo = ", ".join(f"{delegs.count(x)}× {x}" for x in sorted(set(delegs))) or "nenhuma"
    txt = f"Entrega '{antes}' fechada: {n_ferr} chamadas no chat principal, delegações: {resumo}."
    if n_ferr >= DELEG_MIN and not n_deleg:
        txt += (" Zero delegações com esse volume é falha da regra 'Sempre fora do principal' (testes, build, navegador,"
                " leitura de mais de 3 arquivos, logs): na próxima entrega, delegue essas partes.")
    return txt + (" Feche a entrega: leia get_usage e diga ao usuário em 1 linha o % da Definição de Pronto, as"
                  " pendências bloqueantes, as delegações acima e o uso do plano (aplique 'Limites do plano'). Arquive os chats de tarefa dessa entrega"
                  " que não têm mais reuso, se a Configuração mandar (seção 'Arquivar chats sem reuso').")


def id_tarefa(t):
    """'E7 tela de login' e 'E7 tela de login (testes)' são a mesma tarefa: compara pelo ID quando houver."""
    m = re.match(r"\s*([A-Za-z]{1,3}-?\d+)\b", t)
    return m.group(1).upper() if m else t.strip()


def digitado(t):
    """Mensagem escrita pelo usuário, não injetada (hook, notificação, saída de comando, interrupção)."""
    t = t.lstrip()
    return bool(t) and "[gestão]" not in t and not t.startswith(("<", "[Request interrupted", "Stop hook feedback", "Caveat:"))


def parou(texto):
    """O Claude encerrou com a frase de parada (tolera acento, maiúscula e 'nada mais')."""
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.search(r"nada (mais )?a seguir sem voce", t) is not None


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
        return 3, f"{info}: salve o estado e troque de chat (ou /compact) já, antes da compactação automática"
    if ctx >= ideal and ja_avisado < 2:
        return 2, f"{info}: passou do ponto ideal; troque de chat (ou /compact) ao fim do passo atual"
    if not tarefa_ativa and ctx >= FIM_TAREFA * ideal and ja_avisado < 1:
        return 1, f"{info}: tarefa concluída, bom momento para trocar de chat (ou /compact)"
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
    tp = dados.get("transcript_path", "")
    t = ler_transcript(tp)
    ctx, compact = t["ctx"], t["compact"]
    if not ctx:
        return
    sid = dados.get("session_id") or os.path.splitext(os.path.basename(tp))[0] or "?"
    est = pasta_estado(cwd)
    with open(os.path.join(est, "medicao.csv"), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([int(time.time()), sid, ctx[-1], compact])
    # estado de avisos por sessão + ciclo de compactação
    st_path = os.path.join(est, "avisos.json")
    try:
        with open(st_path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    chave = f"{sid}:{compact}"
    saida = {}
    k = lambda n: f"{n // 1000}k"

    def bloquear(reason):  # devolve a vez ao Claude; um motivo por resposta, o primeiro vence
        if "decision" in saida:
            return False
        saida["decision"], saida["reason"] = "block", "[gestão] " + reason
        return True

    # Cada bloqueio abaixo dispara no máximo uma vez (por ciclo ou por versão do arquivo), então não depende de
    # stop_hook_active: no modo Executar quase toda parada é uma continuação e eles nunca disparariam.
    ativa = campo(texto, "Tarefa") not in ("", "—", "-")
    alerta = decidir_alerta(ctx[-1], ler_ideal(cwd), janela_atual(cwd), ativa, st.get(chave, 0))
    if alerta:
        st[chave], msg = alerta
        saida["systemMessage"] = "[gestão] " + msg  # só o usuário vê; não gasta tokens
    # novo chat só compensa acima do dobro da base (o novo começaria nela de novo, sem cache)
    base = t["bases"][-1] if t["bases"] else t["abertura"]
    if not st.get(chave + ":p"):
        if st.get(chave, 0) == 3:
            proposta = ("contexto perto da compactação automática. Atualize Em andamento, sincronize e proponha já o novo "
                        "chat do projeto (start_session, cwd na raiz, modelo e esforço pela Delegação) como cartão clicável; "
                        "/compact só como segunda opção.")
        elif not ativa and st.get(chave, 0) >= 1 and ctx[-1] >= 2 * base:
            proposta = ("tarefa concluída com contexto alto. Atualize e sincronize o PROJETO.md e proponha em 1 linha, "
                        "conforme 'Pasta certa e novo chat': novo chat (start_session) se a próxima tarefa for separada, "
                        "ou /compact se for continuação.")
        else:
            proposta = ""
        if proposta and bloquear(f"contexto {k(ctx[-1])}: " + proposta):
            st[chave + ":p"] = 1
    rows = ler_medicao(cwd)
    sessoes = len({r[1] for r in rows if len(r) > 1})
    if precisa_subir(campo(texto, "Nível"), sessoes, compact, max(ctx)) and not st.get("subir"):
        if bloquear(f"o projeto cresceu ({sessoes} sessões, {compact} compactações, pico {k(max(ctx))}). Suba agora "
                    "para o nível completo, conforme 'Níveis' da skill gestao-de-projeto, e avise o usuário em uma linha."):
            st["subir"] = 1
    # fechamento de entrega: mede delegações desde que a tarefa começou e pede o fechamento (get_usage, %, bloqueantes)
    tarefa = campo(texto, "Tarefa")
    ent = st.get(sid + ":ent")
    if not (isinstance(ent, list) and len(ent) == 3):
        ent = [tarefa, t["ferramentas"], len(t["delegacoes"])]
    if t["ferramentas"] < ent[1] or len(t["delegacoes"]) < ent[2]:  # transcript novo (retomada): conta do zero
        ent = [ent[0], 0, 0]
    fecho = fechamento(ent[0], tarefa, t["ferramentas"] - ent[1], len(t["delegacoes"]) - ent[2], t["delegacoes"][ent[2]:])
    if fecho and bloquear(fecho):  # se outro motivo já usou a vez, fecha na próxima parada
        linha = fecho.split(" Zero")[0].split(" Feche")[0]
        saida["systemMessage"] = saida["systemMessage"] + " · " + linha if "systemMessage" in saida else "[gestão] " + linha
        ent = [tarefa, t["ferramentas"], len(t["delegacoes"])]
    elif not fecho and id_tarefa(ent[0]) != id_tarefa(tarefa):  # começou tarefa: a contagem parte daqui
        ent = [tarefa, t["ferramentas"], len(t["delegacoes"])]
    elif not fecho:
        ent[0] = tarefa  # mesma tarefa com outro texto: mantém a contagem
    st[sid + ":ent"] = ent
    # PROJETO.md desatualizado: devolve a vez ao Claude uma vez por versão do arquivo
    mtime = int(os.path.getmtime(os.path.join(cwd, "PROJETO.md")))
    if "decision" not in saida and st.get("lembrete") != mtime:
        alterados = [l for l in git(cwd, "status", "--porcelain").splitlines() if "PROJETO" not in l]
        ult = git(cwd, "log", "-1", "--format=%ct")
        motivo = motivo_desatualizado(mtime, sum(1 for r in rows if len(r) > 1 and int(r[0]) > mtime),
                                      int(ult) if ult.isdigit() else 0, alterados)
        if motivo and bloquear(f"{motivo}. Atualize agora o PROJETO.md (Em andamento, com 'Tarefa: —' se a tarefa acabou; Entregas, Decisões, Pendências, "
                               "Branches) com edições pontuais e sincronize se o nível for completo. Não fale disso ao usuário."):
            st["lembrete"] = mtime
    # modo Executar: não para enquanto houver o que avançar sem o usuário (limite por mensagem dele, contra custo sem fim)
    if "decision" not in saida and campo(texto, "Modo").lower().startswith("executar"):
        ultimo = dados.get("last_assistant_message") or t["ultimo"]  # o campo do hook, se houver, é o mais fresco
        seg = st.get(sid + ":seg", [t["usuario"], 0])
        if seg[0] != t["usuario"]:
            seg = [t["usuario"], 0]
        if not parou(ultimo) and seg[1] < SEGUIR_MAX:
            seg[1] += 1
            bloquear(f"Modo Executar ({k(ctx[-1])}): siga para o próximo item que não depende do usuário, por "
                     "prioridade, e atualize o PROJETO.md a cada um; o que depende dele vai para Pendências. Se nada mais "
                     f"avança sem ele, termine com '{PARADA}', resumo e próximo passo clicável.")
        st[sid + ":seg"] = seg
    # guarda as sessões recentes: dois chats abertos no mesmo projeto não apagam o estado um do outro
    recentes = {r[1] for r in rows[-500:] if len(r) > 1} | {sid}
    tmp = st_path + f".{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({c: v for c, v in st.items() if c in ("subir", "lembrete") or c.split(":")[0] in recentes}, f)
    os.replace(tmp, st_path)  # troca atômica: um chat nunca lê o arquivo pela metade
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
        logs = [os.path.join(pasta, n) for n in os.listdir(pasta) if n.endswith(".jsonl")]
        for p in sorted(logs, key=os.path.getmtime)[-30:]:  # os 30 chats mais recentes
            bases += ler_transcript(p)["bases"]
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
    pastas = [pasta_logs(cwd)] + [pasta_logs(os.path.abspath(os.path.join(cwd, p))) for p in sys.argv[2:]]
    ctxs, compact, sessoes = [], 0, 0
    for pasta in filter(os.path.isdir, pastas):
        for nome in os.listdir(pasta):
            if nome.endswith(".jsonl"):
                t = ler_transcript(os.path.join(pasta, nome))
                c, n = t["ctx"], t["compact"]
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
    try:
        with open(os.path.join(pasta_estado(cwd), "erros.log"), encoding="utf-8") as f:
            erros = sum(1 for l in f if l[:4].isdigit())  # cada erro começa com a data
    except OSError:
        erros = 0
    print(f"Nível {campo(texto, 'Nível') or '?'} · pronto {pct} · {bloq} pendência(s) bloqueante(s) · "
          f"contexto {ctx} / ponto ideal {ler_ideal(cwd) // 1000}k · tarefa: {campo(texto, 'Tarefa') or '—'}"
          + (f" · {erros} erro(s) do hook em .claude/gestao/erros.log" if erros else ""))


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
    assert parou("Pronto. Nada a seguir sem você.") and parou("nada mais a seguir sem voce") and not parou("sigo")
    assert digitado("corrige isso") and not digitado("<task-notification>x") and not digitado("Stop hook feedback: [gestão] x")
    assert fechamento("—", "E1", 5, 0, []) is None and fechamento("E1", "E1", 50, 0, []) is None
    assert "falha" in fechamento("E1", "—", 20, 0, []) and "falha" not in fechamento("E1", "—", 20, 1, ["haiku/low"])
    assert "1× haiku/low" in fechamento("E1", "E2", 3, 1, ["haiku/low"]) and "falha" not in fechamento("E1", "—", 5, 0, [])
    assert id_tarefa("E7 tela") == id_tarefa("e7 tela (testes)") and id_tarefa("E7") != id_tarefa("E8")
    assert fechamento("E7 tela", "E7 tela (testes)", 30, 0, []) is None and id_tarefa("ajuste logo") == "ajuste logo"
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
    try:
        {"fim": cmd_fim, "janela": cmd_janela, "resumo": cmd_resumo, "status": cmd_status,
         "linha-base": cmd_linha_base}.get(modo, lambda d: print(__doc__))(dados)
    except Exception:
        if modo not in ("fim", "janela"):
            raise
        # hook nunca quebra o chat: registra o erro para diagnóstico e sai em silêncio
        import traceback
        try:
            with open(os.path.join(pasta_estado(dados.get("cwd") or os.getcwd()), "erros.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + modo + "\n" + traceback.format_exc() + "\n")
        except Exception:  # nem o registro do erro pode quebrar o chat
            pass
