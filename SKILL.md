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

## Pasta certa e novo chat (a skill cuida disso)
Os hooks e o settings do projeto só valem quando o chat roda na raiz do projeto (onde ficam `PROJETO.md` e `.git`).
- **Chat aberto numa pasta acima ou ao lado** (ex.: `Downloads` contendo `emissor-nfse`): no app desktop do Claude, use a ferramenta `change_directory` com a raiz do projeto assim que o PROJETO.md existir. O usuário aprova uma vez, e o settings e os hooks do projeto passam a valer neste mesmo chat. Fora do app (CLI), diga em uma linha: `cd <projeto> && claude`.
- **Novo chat quando compensa** (regra em `compactacao.md`: contexto alto com tarefa concluída, ou trabalho grande e separado): no app desktop, proponha você mesmo com `start_session`, com `cwd` na raiz do projeto, `model` e `effort` adequados à tarefa (seção "Delegação") e um resumo curto ("Leia PROJETO.md e continue a entrega E7 usando as skills X"). Atualize e sincronize o PROJETO.md antes. O usuário só clica para iniciar. Fora do app, entregue a frase de abertura pronta.
- Nunca troque de pasta nem abra chat sem o aceite do usuário (as próprias ferramentas pedem). Se ele recusar, siga no chat atual e não insista na mesma sessão.

## Camadas
- **`PROJETO.md`** (raiz): só memória. Nunca entra em commit de código, PR, merge ou deploy (vai no `.gitignore`). Sem segredos (senhas, chaves, tokens, dados de clientes): ele é espelhado online.
- **`PROJETO-ARQUIVO.md`:** concluídos. Leia só quando o usuário pedir.
- **`.claude/gestao/`** (local, no `.gitignore`): medições do hook.
- **Espelho online** (completo): branch órfã `projeto-estado` (`git.md`).
- **`CLAUDE.md` do projeto (fallback):** "Leia PROJETO.md no início da sessão e após compactação (se não existir, restaure da branch projeto-estado) e siga a skill gestao-de-projeto."

## Início / retomada
1. Se o hook `SessionStart` já injetou o resumo, use-o; não releia o arquivo inteiro.
2. Senão leia `PROJETO.md`. Ausente: tente `bash scripts/restaurar-estado.sh`; sem espelho, é projeto novo → crie a partir de `modelo-PROJETO.md` no nível adequado.
3. Configuração ausente: **um único** AskUserQuestion. Leve pergunta só o Modo; Completo pergunta também Como rodar local. Com configuração gravada, não pergunte de novo. A compactação é sempre gerida pela skill (é o motivo dela existir); não há opção manual. Grave também na Configuração o "Chat principal" (modelo atual da sessão; se não for o mais forte disponível, avise) e a linha de "Delegação" do modelo, e mostre as duas ao usuário na confirmação.
4. Projeto sem testes: a primeira entrega é criar um gate mínimo (prioridade alta).
5. **Uso de partida (só na 1ª vez, projeto novo ou existente):** peça ao usuário para rodar `/usage` e colar o print ou os números (custo, leitura e gravação de cache, saída, cache hit, linhas alteradas) antes de começar o trabalho. Registre em Decisões como "linha de base de uso" com a data e o modelo, e calcule o custo por linha alterada. Se ele não quiser, siga sem.

Mudar depois: `/gestao-de-projeto config` (tudo), `/gestao-de-projeto config modo|local|nível` (uma), ou texto livre.

## Adotar num projeto existente ("usar a skill neste projeto")
Uma passada só, sem reler o que já está no contexto:
1. **Levantamento barato:** README, manifesto (`package.json` etc.), `git log --oneline -30`, `git branch -a`, TODO/FIXME por grep, CLAUDE.md existente. Subagente só se o repositório for grande.
2. **Rascunho do PROJETO.md** no nível certo (repositório com histórico longo ou muitos arquivos já entra no Completo): Objetivo e Stack deduzidos, branches abertas na seção 9, TODOs como pendências com prioridade sugerida, decisões visíveis no histórico (ex.: troca de biblioteca) com motivo "inferido".
3. **Confirmação única:** mostre o rascunho resumido e faça um AskUserQuestion com Modo, Como rodar local e "o que está em andamento agora". Marque como "inferido" o que não foi confirmado.
4. **Instalação:** `.gitignore`, linha no CLAUDE.md, hooks (uma permissão), espelho online e o primeiro sync. Se não houver testes, a entrega E1 é o gate mínimo.
5. **Linha de base:** rode `python scripts/monitor.py linha-base < /dev/null` uma vez, antes de qualquer trabalho com a skill. Ela mede os chats anteriores do projeto para comparar depois. Junto, peça o `/usage` de partida (passo 5 do Início).

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
  Procure também no PROJETO.md (grep "linha de base") um registro de uso do painel do Claude Code (custo, leitura de cache, linhas alteradas). Se houver, peça ao usuário o print atual do painel de Uso e compare custo por linha alterada e leitura de cache por sessão, lado a lado com a saída do `resumo`.

## Atualização do PROJETO.md
- **Rede contra arquivo velho:** se houver commit depois da última edição do PROJETO.md, ou 20+ respostas com arquivos alterados sem editá-lo, o hook `Stop` devolve a vez com a ordem de atualizar. Faça a atualização em silêncio e continue.
- Edição pontual (Edit) a cada decisão, entrega, pendência ou pergunta nova, e antes de `/compact`.
- **Em andamento** (`- Tarefa: … · Próximo passo: … · Arquivos: …`): sobrescreva ao iniciar e ao concluir cada tarefa; ao concluir, use `- Tarefa: —`. O hook usa esse campo para saber se é um bom momento de compactar.
- Concluídos vão para `PROJETO-ARQUIVO.md` (~150 linhas ativas, teto 300).
- Completo: sincronize (`bash scripts/sync-estado.sh`) ao fim de cada tarefa, ao registrar decisão, após merge/deploy, ao fim da sessão e antes de `/compact`.
- A skill nunca roda `/compact` (só o usuário pode). Quem avisa o momento é o hook.

## Delegação: o chat principal arquiteta, a skill distribui
O chat principal fica no modelo mais forte disponível (ex.: Fable/Opus) e cuida do que exige julgamento: arquitetura, decisões, revisão do que voltou das delegações. A execução vai para o nível certo. No início da sessão, se o chat principal não estiver no modelo mais forte, avise em 1 linha: as delegações nunca podem usar um modelo acima do dele.

Ao receber um conjunto de tarefas, quebre em partes e aplique esta regra a cada uma, sem esperar o usuário pedir:
Antes de delegar, decida nesta ordem, em 1 linha para o usuário ("subagente Haiku/baixo: só leitura"):
1. **Onde:** subagente se o resultado cabe num resumo e não precisa do usuário; novo chat se precisa de idas e vindas ou é grande e separado; continuar aqui se depende do que já está no contexto.
2. **Modelo e esforço** pela tarefa, não pelo hábito:

| Tarefa | Modelo | Esforço |
|---|---|---|
| Mecânica ou só leitura: buscar, listar, renomear, formatar, resumir arquivos | Haiku | low |
| Implementação comum: tela, endpoint, teste, bug localizado | Sonnet | medium |
| Difícil ou de risco: arquitetura, refatoração ampla, design/UX, bug sem pista, segurança, dinheiro, migração | o modelo atual (Opus/Fable) | high |

- Subagente: passe `model` e `effort` na ferramenta Agent (a skill autoriza escolher o esforço).
- Novo chat no app: passe `model` e `effort` no `start_session`. O app só aceita modelo igual ou mais barato que o do chat atual, e esforço igual ou menor. Por isso o chat principal deve estar no modelo mais forte que o projeto precisa.
- Na dúvida entre dois níveis, use o de cima. Errar para baixo custa retrabalho, que sai mais caro que a diferença de preço.
- Registre a escolha na Entrega ("E7 · novo chat Sonnet/medium") para calibrar: se precisou refazer, suba o nível dessa categoria nas próximas.
- **Revise o que voltar:** saída de Haiku/Sonnet passa por uma conferência rápida do chat principal antes de ser dada como pronta (diff, testes, gate). A economia só vale se a qualidade se mantém.
- **Não delegue o que é menor que a própria delegação:** tarefa de 1-3 chamadas de ferramenta, faça aqui. Delegar tem custo de contexto inicial.

## Economia de tokens
Agrupe tarefas relacionadas e faça de uma vez. Não releia o que já está no contexto. Para trabalho grande e separado, siga a regra "novo chat × subagente" de `compactacao.md`.
