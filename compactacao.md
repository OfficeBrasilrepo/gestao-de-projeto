# Compactação, janela, medição e novo chat × subagente

## Como o Claude Code compacta (verificado em 2.1.282)
- A compactação automática dispara quando o contexto chega perto da **janela**. Limite real = mínimo entre a janela e o máximo do modelo (ou seja, 1M num modelo menor vira o máximo do modelo).
- Fontes da janela, da mais forte para a mais fraca: `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (env, trava o comando) > `autoCompactWindow` nas settings (projeto `.claude/settings.local.json` vence o usuário `~/.claude/settings.json`) > padrão "auto".
- **A janela é lida ao abrir/retomar o chat. Mudar o arquivo com o chat aberto não tem efeito** (testado). Só `/autocompact Nk` digitado pelo usuário muda na hora, mas grava na configuração global.
- Nem a skill nem o Claude disparam `/compact`. Só o usuário.

## Estratégia (tudo em tokens absolutos, nunca em % da janela do usuário)
1. **Ponto ideal** (`monitor.py janela`, no `SessionStart`): ≈ 3× a base medida após compactar, entre 100k e 300k, 150k sem dados. Fica em `.claude/gestao/ideal.json`. Se a janela do usuário for menor, o ideal vira 80% dela.
2. **Rede de segurança** (sempre): grava `autoCompactWindow` = ponto ideal + 40% no `.claude/settings.local.json` do projeto, se mudar > 20%. Use a chave, não o env (o env trava o comando). Vale na próxima abertura e não afeta outros projetos.
3. **Avisos** (`monitor.py fim`, no `Stop`, a cada resposta): mostrados ao usuário, sem gastar tokens. Sempre com os números, por exemplo "contexto 95k · ponto ideal 150k · automática em 350k":
   - tarefa concluída (`Tarefa: —`) e contexto ≥ 70% do ideal → bom momento para /compact;
   - contexto ≥ ideal → /compact ao fim do passo atual;
   - contexto ≥ 90% do limite automático → salvar o estado e compactar já;
   - uma vez por faixa e por ciclo de compactação;
   - nas faixas 1 e 3 o hook também devolve a vez ao Claude uma vez, para ele mesmo atualizar o estado e propor o novo chat (`start_session`) ou pedir o /compact; o usuário não precisa lembrar.
   Antes do usuário compactar, garanta "Em andamento" atualizado e o estado sincronizado.
4. **Medição:** cada resposta grava `timestamp, sessão, contexto, compactações` em `.claude/gestao/medicao.csv` (~100 ms, algumas dezenas de bytes por resposta). `python ~/.claude/skills/gestao-de-projeto/scripts/monitor.py resumo < /dev/null` mostra turnos, contexto médio por turno, pico, ponto ideal e janela. O contexto médio por turno é o principal indicador de custo: cada turno relê o contexto inteiro, e com cache isso custa ~10%, mas soma.

## Novo chat × subagente × continuar
| Situação | Melhor | Por quê |
|---|---|---|
| Busca, leitura ampla, revisão, cujo resultado cabe num resumo | **Subagente** | Contexto próprio e descartável; volta só a conclusão. Barato para o chat principal. |
| Trabalho grande e separado (módulo novo, refatoração ampla) que precisa de idas e vindas com o usuário | **Novo chat** com `PROJETO.md` | Começa enxuto (~20-30k), sem carregar o histórico; o usuário conduz. Ao terminar, atualize o PROJETO.md para o chat principal ver. |
| Continuação direta do que está em contexto | **Continuar** | Reler tudo em outro lugar custaria mais. |
| Contexto alto e tarefa acabou | **`/compact`** no mesmo chat | Equivale a um novo chat, mas mantém o fio. |
| Contexto abaixo do dobro da base de abertura do chat | **Continuar** | Um chat novo começaria quase no mesmo ponto e sem cache (gravar cache custa mais que ler). O hook só sugere a troca acima disso. |

**Preparar o novo chat enxuto:** registre a tarefa em Entregas e em "Em andamento", com só o necessário: arquivos que ela toca, decisões que a afetam e skills úteis. Para as skills, siga "Skills de cada delegação" no `SKILL.md` (find-skills por assunto, anotadas na seção 7 ou, no Leve, em Decisões). Depois entregue ao usuário a frase de abertura pronta, por exemplo "Leia PROJETO.md, faça a entrega E7 usando as skills X e Y". Sugira o novo chat em 1 linha.

Modelo e esforço de cada delegação: seção "Delegação" do `SKILL.md`.

## Hooks (peça permissão e mostre o JSON exato; faça merge no settings existente)
```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "startup|resume|compact",
        "hooks": [
          { "type": "command", "command": "python \"${USERPROFILE:-$HOME}/.claude/skills/gestao-de-projeto/scripts/resumo-retomada.py\"" },
          { "type": "command", "command": "python \"${USERPROFILE:-$HOME}/.claude/skills/gestao-de-projeto/scripts/monitor.py\" janela" } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "python \"${USERPROFILE:-$HOME}/.claude/skills/gestao-de-projeto/scripts/monitor.py\" fim" } ] }
    ]
  }
}
```
Os caminhos usam `${USERPROFILE:-$HOME}` e funcionam em qualquer Windows (Git Bash), macOS ou Linux; só troque `python` por `python3` se for o nome na máquina. Instale os dois já ao criar o PROJETO.md, com uma permissão só. O `Stop` também faz a subida automática de nível: devolve a vez ao Claude uma vez, com `decision: block`, e nunca repete quando `stop_hook_active` está ativo. Com o `SessionStart` instalado, a linha do CLAUDE.md vira fallback. No modo Executar, o `Stop` também mantém o trabalho andando: devolve a vez enquanto o Claude não encerrar com "nada a seguir sem você", até 25 vezes por mensagem do usuário.

## Descartado
- **Bloquear a compactação com `PreCompact`:** funciona (saída 2 bloqueia e o usuário vê a mensagem), mas o risco de bater no teto do modelo não compensa; o aviso no momento certo resolve.
- **Calibração por histórico semanal:** substituída pela medição em tempo real.

## Verificações (2026-11-10, Windows 10, Claude Code 2.1.282, Opus 5.5)
- `/autocompact` sem valor: "350k tokens (from settings)" — o `~/.claude/settings.json` do usuário tem `autoCompactWindow: 350000`.
- Env `CLAUDE_CODE_AUTO_COMPACT_WINDOW=150000`: reconhecido ("from CLAUDE_CODE_AUTO_COMPACT_WINDOW").
- `autoCompactWindow: 120000` no settings do projeto: reconhecido, vence o global.
- Mudança da janela com o chat aberto: não aplicada.
- `SessionStart`: resumo injetado (o Claude respondeu a tarefa do PROJETO.md).
- `Stop` (`monitor.py fim`): mediu o contexto a cada resposta, gravou o CSV, avisou uma vez por faixa e registrou o aviso na sessão como `hook_system_message` (no `-p` não aparece no texto; no chat interativo aparece para o usuário). `monitor.py janela` recalculou 120k → 150k na abertura.
- Subida automática: o `Stop` bloqueou uma vez e o Claude iniciou a subida de nível sozinho (no `-p` ele parou só por falta de permissão de edição).
- Ponto ideal 150k sem amostras; rede de segurança gravada em 210k.
- `PreCompact` com saída 2: bloqueou `/compact` manual e mostrou a mensagem.
- Logs: `~/.claude/projects/<pasta>/*.jsonl`, `message.usage` nas linhas `assistant`, `compact_boundary` em `system`.
