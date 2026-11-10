# BrightBean verificado na Fase 3 — checklist de aceitação

## Fonte e fixação

- Repositório: https://github.com/brightbeanxyz/brightbean-studio
- Commit usado: `1d11c52007a3f714979ff1b071d153e69a8c274a`
- `.python-version` upstream: `3.13`
- Licença upstream: AGPL-3.0
- Operações de escrita no GitHub: **nenhuma**; o utilizador conectado não tinha repositórios graváveis listados no momento da análise.

## Módulos reutilizados

| Caminho upstream | Papel na integração |
|---|---|
| `apps/workspaces/models.py` | Workspaces por cliente |
| `apps/composer/models.py` | Post e variantes PlatformPost, media e PostVersion |
| `apps/approvals/services.py` | Aprovação interna e de cliente (workflow nativo) |
| `apps/calendar/views.py` | Calendário, reagendamento e ações em lote |
| `apps/publisher/engine.py` | Envio externo, retries e confirmação |
| `apps/client_portal/models.py` | Links mágicos; NÃO ligados ao portal RISE nesta fase |
| `apps/media_library/models.py` | Versão de media e biblioteca de assets |
| `apps/analytics/models.py` | Histórico de métricas sociais autorizado |

## Necessário testar com Docker/PostgreSQL

- [ ] `makemigrations --check --dry-run` sem diferenças
- [ ] `migrate` num banco vazio e numa cópia de staging
- [ ] `manage.py check` sem erros
- [ ] Testes Django específicos RISE + testes upstream
- [ ] Aprovar copy; impedir envio até aprovar imagem
- [ ] Aprovar imagem; confirmar que o workflow BrightBean também exige aprovação final
- [ ] Alterar texto/imagem/variante; bloquear envio e pedir nova aprovação
- [ ] Agendar pela UI, API e arrastar calendário; não aceitar agendamento sem aprovação
- [ ] Importar CSV: RISE recebe apenas rascunhos, não agendamentos imediatos
- [ ] Testar recorrências e rotinas background adicionais (ainda não cobertas)
- [ ] Dois clientes distintos: verificar isolamento de GET e POST
- [ ] Verificar que o cliente não vê rascunhos internos
- [ ] Validar CSRF, sessões e portal de aprovação por link sem login
- [ ] Verificar permissões sociais e refresh de tokens
- [ ] Publicar cada formato real em contas de teste e reconciliar falhas sem duplicação
- [ ] Testar horários Europe/Lisbon, mudança de hora e indisponibilidade do worker
- [ ] Testar ficheiros privados, RGPD, licenciamento e backup/restore

## Problemas a monitorizar

- Publicações duplicadas e falhas de confirmação, sobretudo em trabalhos assíncronos.
- Permissões Meta e LinkedIn podem impedir funcionalidades anunciadas.
- Envio de emails/DMs não deve ser ativado sem teste dedicado.
- Módulos exclusivos RISE (Canva, Mailchimp, Competitive Intelligence e CRM) continuam por migrar efetivamente.

**Decisão:** ainda não substituir o WordPress. A Fase 3 prepara integração verificada por inspeção, não uma versão comercial validada.
