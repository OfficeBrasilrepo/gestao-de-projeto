# Design: opções, melhoria proativa e aprovação visual

Base: design profissional apoiado em estudos atuais, transições e transparência com moderação, sem informação encavalada, botões sobrepostos ou redundantes.

## Opções (só quando o usuário pedir exemplos ou versões)
Vale para design, layout, mudança organizacional ou fluxo. Apresente:
- **(A)** como está hoje;
- **(B)** o que foi pedido;
- **(C, D, E)** três versões do Claude com UX avançado e referências atuais.

Cada uma com prós e contras, e no fim uma recomendação. Sem pedido de versões, execute direto.

## Sugestão de melhoria proativa (só design, layout e fluxo)
Quando houver alternativa claramente melhor, mostre 1 exemplo ao lado do pedido (problema só objetivo e pequeno: aponte em 1-2 linhas). Sem resposta, execute o pedido. Se o usuário pedir para o Claude ousar mais, a versão do Claude pode virar a principal, mas só numa branch separada, com a pedida preservada.

Sempre como opinião. Descartada → registre como descartada em Decisões; a branch só é apagada se o usuário pedir.
Critérios: hierarquia visual, espaçamento, consistência, acessibilidade, mobile.

## Aprovação visual
- **Mudança estética:** original e alterado lado a lado numa imagem só, desktop e mobile. Gere com `node scripts/comparar-visual.mjs` (Playwright). As capturas vão para uma pasta fora do git (`../.capturas-<projeto>/`) e não passam pelo contexto; olhe só a imagem final da comparação.
- **Decisão escrita:** diff enxuto "antes → depois" em 1-3 linhas.
- Playwright baixa o Chromium: peça permissão antes da primeira instalação (`npx playwright install chromium`). Rotas com login usam a conta de teste do `.env`.

### Uso do script
```bash
node ~/.claude/skills/gestao-de-projeto/scripts/comparar-visual.mjs \
  --antes http://localhost:3000/rota --depois http://localhost:3001/rota --saida ../.capturas-app/rota.png
```
Para "antes", rode a versão da main numa segunda porta (ex.: `git worktree add ../app-main main`).
