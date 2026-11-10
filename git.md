# Git, publicação e sincronização

## Boas práticas
README, estrutura clara, `.gitignore`, `.env.example` sem valores reais. Cada entrega numa branch própria (`feat/`, `fix/`, `chore/`) com commits claros. Aprovada, a branch fica aguardando (status "aprovada" na seção Branches).

## Publicar
**Ritmo:** agrupe entregas prontas e publique por pacote. Cada publicação custa uma rodada de gate, pacote e envio, além do trabalho de atualizar do lado do usuário final. Publique na hora só correção de problema em produção, ou o que o usuário precisa já. Pacote grande demais também é ruim: se algo quebrar, é mais difícil achar a causa e voltar atrás. Na recomendação, diga em 1 linha se vale publicar agora ou esperar juntar mais.

1. Liste as branches abertas e aprovadas (seção 9 do PROJETO.md + `git branch`).
2. Para cada uma com pendência ligada, mostre como a pendência consta e pergunte: publicar assim mesmo, ou resolver/alterar/aprovar antes. **Pendência bloqueante aberta, ligada ou não à branch:** não ofereça publicar como pergunta solta ("publico?"). Liste-as primeiro, diga se cada uma afeta o que vai ao ar e só então pergunte. Na dúvida se afeta, trate como afetando.
3. Mescle uma branch por vez, rodando o gate entre elas.
4. Branch com migração de banco vai sozinha na vez e sempre pede autorização (pode perder dados).
5. Atualize a seção Branches e sincronize.

Se a main publica automaticamente em produção, avise antes e deixe pronto o caminho de volta (`git revert <merge> -m 1` ou rollback do deploy).

## Sincronização online (branch órfã `projeto-estado`)
**Uma vez por projeto:** `PROJETO.md`, `PROJETO-ARQUIVO.md` e `.claude/gestao/` no `.gitignore`; no README, como restaurar; recomendar repositório privado. Em Vercel, configure o Ignored Build Step para pular `projeto-estado` (ex.: `[ "$VERCEL_GIT_COMMIT_REF" = "projeto-estado" ] && exit 0 || exit 1`).

**Sincronizar:** `bash ~/.claude/skills/gestao-de-projeto/scripts/sync-estado.sh` (rodar na raiz do repo). Cria a branch na primeira vez, não faz commit vazio, não mexe na branch atual.

**Restaurar:** `bash ~/.claude/skills/gestao-de-projeto/scripts/restaurar-estado.sh`.
- Sem arquivo local: restaura.
- Local igual ao remoto: nada a fazer.
- Local diferente do remoto: o script **não sobrescreve** e sai com código 3 mostrando as diferenças. Resuma para o usuário e pergunte qual vale (inclusive no modo Executar). Para aceitar o remoto: `restaurar-estado.sh --forcar`.

**Sem remoto git:** avise que o estado só existe nesta máquina e ofereça cópia no Drive. Se o push falhar, registre a pendência "sincronizar estado".
