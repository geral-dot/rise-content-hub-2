# RISE Content Hub 2.0 — Código BrightBean confirmado no GitHub

**Consulta ao repositório oficial (08/11/2026)**

- Repositório: https://github.com/brightbeanxyz/brightbean-studio
- Branch principal: `main`
- Commit de referência verificado via API GitHub: `1d11c52007a3f714979ff1b071d153e69a8c274a`
- Acesso disponível: leitura do repositório oficial. A conta GitHub ligada **não apresentou repositórios próprios acessíveis à ferramenta**, pelo que **não foi realizado fork, push nem PR**.
- Restrição do ambiente de desenvolvimento: o Git CLI local não conseguiu resolver `github.com`; o código upstream foi inspecionado através da ligação GitHub, **não foi clonado/instalado localmente**, e portanto o sistema Django não pôde ser executado.

## Estrutura efetivamente observada no commit

| Módulo de BrightBean | Código-base confirmado | Estratégia RISE |
|---|---|---|
| Organizações, workspaces | `apps/organizations/models.py`, `apps/workspaces/models.py` | Reutilizar modelos `Organization` e `Workspace`, personalização da marca por workspace |
| Publicações e versões | `apps/composer/models.py` (`Post`, `PlatformPost`, `PostMedia`, `PostVersion`) | Reutilizar composição, variantes por rede e versões, acrescentando aprovação dupla |
| Aprovações | `apps/approvals/models.py`, `apps/approvals/services.py` | Reutilizar workflow original, com histórico adicional RISE de componentes |
| Calendário | `apps/calendar/models.py`, `apps/calendar/services.py` | Reutilizar sem recriar |
| Publicação | `apps/publisher/engine.py` (`PublishEngine`), `apps/publisher/tasks.py` | Reutilizar com validação RISE na transição para agendamento e imediatamente antes do envio externo |
| API | `apps/api/routers/posts.py` | Reutilizar autorizações, limites, idempotência e quota por plataforma |
| Portal de cliente | `apps/client_portal/models.py`, serviços e views | Reutilizar tokens e UX, adequar ao PT-PT |
| Analytics | `apps/analytics/` | Reutilizar métricas autenticadas. Competidores RISE permanecem separados |
| Media | `apps/media_library/` | Reutilizar, com revisão do acesso privado |
| Perfil de utilizador e permissões | `apps/members/models.py` (`WorkspaceMembership`) | Reutilizar `effective_permissions['approve_posts']` |

## Dois pontos particularmente importantes da arquitetura atual

1. `Post.status` é **derivado** dos estados dos filhos `PlatformPost`. Cada rede possui o seu próprio fluxo: `draft`, `pending_review`, `pending_client`, `approved`, `scheduled`, `publishing`, `published`, `failed` e outros. O RISE deve preservar esta modelação. 
2. `apps/composer/services.py`, método `transition_platform_post`, valida agendamento; `apps/publisher/engine.py`, método `_publish_platform_post`, faz o envio externo. Foram escolhidos dois pontos de verificação para o gate RISE (defesa em profundidade). **Outros caminhos de estado — HTMX, calendário, filas, tarefas e ferramentas MCP — requerem auditoria adicional antes da produção.**

## Integração neste kit

`django_rise_agency/models.py` já usa referências aos modelos reais (`workspaces.Workspace`, `composer.Post`), em vez de IDs de texto genéricos. Os serviços calculam assinatura SHA-256 de conteúdo editorial (texto, variantes por rede, media e ordenação), para detetar alterações após aprovação.

`apply_brightbean_hooks.py` aplica duas intervenções mínimas **apenas** ao commit identificado, com simulação por defeito. Antes da escrita, verifica marcadores exatos, cria backups e recusa outros commits. **Não substitui uma revisão de segurança nem testes de integração**. O próprio BrightBean já possui mecanismos de proteção contra repetição e confirmação de publicação, que devem ser preservados.

O motor de publicação continua desligado neste kit, não existem tokens e não foram publicados conteúdos reais.

## Licença

O projeto publica `LICENSE` no repositório. Confirmar e cumprir os termos AGPL-3.0 antes de disponibilizar modificações a utilizadores através da rede. A marca RISE pode ser aplicada respeitando as obrigações de licença e atribuição.
