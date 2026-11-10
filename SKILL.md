---
name: gestao-de-projeto
description: "Memória viva do projeto (PROJETO.md): decisões, entregas, pendências, prioridades, branches, sincronização online e economia de tokens/compactação. Use ao iniciar/retomar projeto, pedir pendências, opções de design ou publicar. Use também quando o usuário disser 'retomar', 'onde paramos', 'pendências', 'o que falta', 'mudar modo', 'subir nível', 'compactar', 'publicar', 'mergear', ou quando existir um PROJETO.md na raiz do projeto, mesmo que ele não cite a skill."
---

# Gestão de projeto

Mantém o estado de um projeto de app em `PROJETO.md` (raiz) para que decisões, entregas e pendências sobrevivam à compactação e possam ser retomadas noutro chat ou máquina, gastando o mínimo de tokens. Responda sempre em português.

## Níveis (a skill cresce com o projeto)
A gestão custa tokens; só vale quando o projeto é grande o bastante. Por isso ela começa leve e sobe sozinha.
- **Leve** (padrão em projeto novo/pequeno): `PROJETO.md` mínimo (Objetivo, Configuração, Em andamento, Entregas, Pendências, Decisões). Sem perguntas além do Modo, sem espelho online.
- **Completo:** modelo inteiro, configuração completa, espelho online.
- **Hooks desde o início:** ao criar o PROJETO.md, peça permissão **uma vez** e instale os dois hooks (`compactacao.md`), mostrando o JSON. Eles medem o contexto a cada resposta e não gastam tokens enquanto estão em silêncio.
- **Subida automática:** quando houver 2ª sessão, 1ª compactação ou contexto ≥ 100k, o hook `Stop` devolve a vez ao Claude uma única vez com a instrução de subir. Aí: troque `Nível: completo`, complete o modelo, configure o espelho online (`git.md`), registre em Decisões e avise em uma linha. Pergunte só o que não dá para deduzir (Como rodar local), num único AskUserQuestion.
- Projeto de uma conversa curta (script, ajuste pontual): não crie nada; diga em uma linha que a skill não compensa aqui.

## Camadas
- **`PROJETO.md`** (raiz): só memória. Nunca entra em commit de código, PR, merge ou deploy (vai no `.gitignore`). Sem segredos (senhas, chaves, tokens, dados de clientes): ele é espelhado online.
- **`PROJETO-ARQUIVO.md`:** concluídos. Leia só quando o usuário pedir.
- **`.claude/gestao/`** (local, no `.gitignore`): medições do hook.
- **Espelho online** (completo): branch órfã `projeto-estado` (`git.md`).
- **`CLAUDE.md` do projeto (fallback):** "Leia PROJETO.md no início da sessão e após compactação (se não existir, restaure da branch projeto-estado) e siga a skill gestao-de-projeto."

## Início / retomada
1. Se o hook `SessionStart` já injetou o resumo, use-o; não releia o arquivo inteiro.
2. Senão leia `PROJETO.md`. Ausente: tente `bash scripts/restaurar-estado.sh`; sem espelho, é projeto novo → crie a partir de `modelo-PROJETO.md` no nível adequado.
3. Configuração ausente: **um único** AskUserQuestion. Leve pergunta só o Modo; Completo pergunta também Como rodar local. Com configuração gravada, não pergunte de novo. A compactação é sempre gerida pela skill (é o motivo dela existir); não há opção manual.
4. Projeto sem testes: a primeira entrega é criar um gate mínimo (prioridade alta).

Mudar depois: `/gestao-de-projeto config` (tudo), `/gestao-de-projeto config modo|local|nível` (uma), ou texto livre.

## Adotar num projeto existente ("usar a skill neste projeto")
Uma passada só, sem reler o que já está no contexto:
1. **Levantamento barato:** README, manifesto (`package.json` etc.), `git log --oneline -30`, `git branch -a`, TODO/FIXME por grep, CLAUDE.md existente. Subagente só se o repositório for grande.
2. **Rascunho do PROJETO.md** no nível certo (repositório com histórico longo ou muitos arquivos já entra no Completo): Objetivo e Stack deduzidos, branches abertas na seção 9, TODOs como pendências com prioridade sugerida, decisões visíveis no histórico (ex.: troca de biblioteca) com motivo "inferido".
3. **Confirmação única:** mostre o rascunho resumido e faça um AskUserQuestion com Modo, Como rodar local e "o que está em andamento agora". Marque como "inferido" o que não foi confirmado.
4. **Instalação:** `.gitignore`, linha no CLAUDE.md, hooks (uma permissão), espelho online e o primeiro sync. Se não houver testes, a entrega E1 é o gate mínimo.
5. **Linha de base:** rode `python scripts/monitor.py linha-base < /dev/null` uma vez, antes de qualquer trabalho com a skill. Ela mede os chats anteriores do projeto para comparar depois.

## Modo: uma chave, o risco decide o resto
- **Perguntar antes:** proponha os passos, espere aprovação, execute.
- **Executar:** execute sem interromper; dúvidas viram "Perguntas sem resposta" com a suposição adotada.

Independentemente do modo:
- **Reversível** (código numa branch, testes, refatoração): segue a chave.
- **Merge na `main`:** se a `main` publica sozinha em produção (ex.: Vercel), sempre pede aprovação, com rollback pronto (`git revert -m 1` / rollback do deploy). Se não publica, segue a chave, mas só com o gate verde e sem pendência ligada à branch.
- **Irreversível — sempre pede autorização:** apagar dados ou tabelas; migração que perde dados; force push/reescrita de histórico; apagar branch não mergeada ou arquivos sem cópia; enviar e-mail/mensagem a clientes; cobrar ou mover dinheiro; revogar ou trocar chaves.

**Gate de qualidade** (antes de qualquer merge ou pedido de aprovação): build, lint, typecheck, testes e smoke test com o app rodando local, sem erro de console nas telas afetadas. O gate reduz o risco, não o zera.

## Regras do dia a dia
- **Crítica:** a cada decisão ou pedido, 1-2 linhas com prós, contras e impacto em outras partes. Não execute algo que quebre outra parte sem avisar.
- **Prioridade:** nota 1-10 (10 = mais urgente), opcional. Sem nota, decida pela influência (bloqueio, impacto, dependências) e informe. Empate: bloqueantes primeiro.
- **Pendências:** qualquer comando ou pergunta pode virar pendência. Ao pedir "pendências", liste por prioridade (bloqueantes primeiro) com as perguntas sem resposta. Pendência que impede avanço: pare e pergunte só sobre ela.
- **Perguntas ignoradas:** registre na seção 5 sem cobrar; o usuário decide depois (descartar, virar pendência, responder).
- **Design, layout, fluxo** (opções A/B/C, sugestão de melhoria, aprovação visual): `design.md`.
- **Publicar, mergear, sincronizar:** `git.md`.
- **Compactação, janela, medição, novo chat × subagente:** `compactacao.md`.
- **Meta:** ao fechar cada entrega, informe o % da Definição de Pronto. Em 100%, avise e confira pendências e perguntas (o projeto não encerra sozinho).

## Status e medição
- "status": `python scripts/monitor.py status < /dev/null` → nível, % pronto, pendências bloqueantes, contexto atual, tarefa. Repasse a linha.
- "a skill está economizando?": `python scripts/monitor.py resumo < /dev/null` → contexto médio por resposta agora × antes da skill. Diga com franqueza que a comparação é aproximada (trabalhos diferentes) e só vale após ~1 semana ou ~200 respostas.

## Atualização do PROJETO.md
- **Rede contra arquivo velho:** se houver commit depois da última edição do PROJETO.md, ou 20+ respostas com arquivos alterados sem editá-lo, o hook `Stop` devolve a vez com a ordem de atualizar. Faça a atualização em silêncio e continue.
- Edição pontual (Edit) a cada decisão, entrega, pendência ou pergunta nova, e antes de `/compact`.
- **Em andamento** (`- Tarefa: … · Próximo passo: … · Arquivos: …`): sobrescreva ao iniciar e ao concluir cada tarefa; ao concluir, use `- Tarefa: —`. O hook usa esse campo para saber se é um bom momento de compactar.
- Concluídos vão para `PROJETO-ARQUIVO.md` (~150 linhas ativas, teto 300).
- Completo: sincronize (`bash scripts/sync-estado.sh`) ao fim de cada tarefa, ao registrar decisão, após merge/deploy, ao fim da sessão e antes de `/compact`.
- A skill nunca roda `/compact` (só o usuário pode). Quem avisa o momento é o hook.

## Economia de tokens
Agrupe tarefas relacionadas e faça de uma vez. Não releia o que já está no contexto. Para trabalho grande e separado, siga a regra "novo chat × subagente" de `compactacao.md`.
