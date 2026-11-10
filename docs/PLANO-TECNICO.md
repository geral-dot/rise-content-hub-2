# RISE Content Hub 2.0 — Análise de integração

## Fontes analisadas
- Código real do plugin WordPress `RISE-Content-Hub-WordPress-1.11.0-Competitive-Intelligence.zip` (versão 1.11, 7 novembro de 2026).
- README oficial do BrightBean Studio, consultado a 8 novembro de 2026: https://github.com/brightbeanxyz/brightbean-studio
- GitHub issues públicos do BrightBean: https://github.com/brightbeanxyz/brightbean-studio/issues

## Decisão de arquitetura

- BrightBean (Python / Django / PostgreSQL + background jobs) será a base **candidata** do Content Hub 2.0.
- Website institucional WordPress mantém-se isolado. Plugin WordPress 1.11 continua disponível durante a migração.
- O RISE Content Hub 2.0 terá a marca RISE e os seus módulos específicos numa extensão aditiva; alterações ao núcleo BrightBean devem ser minimizadas e documentadas.
- Não reutilizar tokens guardados no plugin. Cada conta social terá ligação OAuth nova na plataforma migrada.
- Versionar um commit da base BrightBean antes de introduzir alterações. Fazer testes upstream e de regressão.

## Mapeamento real da base WordPress 1.11

| Origem WordPress | Tratamento na nova plataforma | Condição |
|---|---|---|
| `rise_hub_records` (`kind=clients`) | Workspaces BrightBean | Criar e validar IDs e isolamento |
| `rise_hub_membership` | Members/roles BrightBean | Convidar utilizadores; não migrar passwords |
| `rise_hub_records` (`kind=content`) | Posts BrightBean | Mapear canal, estado, asset, data, fuso e copy |
| `rise_hub_versions` | Histórico editorial RISE | Preservar versão e autoria |
| `rise_hub_events` | Comentários/aprovações RISE | Distinguir internos/externos e pontos na imagem |
| `rise_hub_records` (`kind=assets`) | Media library | Não exporta binários; migrar por processo autorizado separado |
| `rise_hub_records` (`kind=goals/metrics/reports`) | RISE analytics e relatórios | Preservar valores históricos e proveniência |
| `rise_hub_records` (`kind=competitors`) | RISE Competitive Intelligence | Manter separado dos insights autorizados BrightBean |
| `rise_hub_ci_observations`, `rise_hub_ci_ads` | Histórico de inteligência | Sem inventar investimento ou seguidores ausentes |
| `rise_hub_publishing_jobs` | Log histórico apenas | Nunca enfileirar automaticamente |
| `rise_hub_mc_campaigns/comments/events` | Arquivo Mailchimp RISE | Revalidar versões e destinatários antes de qualquer envio |
| Credenciais OAuth / integrações | **Não migrar** | Reautorizar e verificar scopes |

## Módulos aproveitáveis do BrightBean (documentados, não testados nesta sessão)

1. Organizações e workspaces, perfis e permissões.
2. Content composer, modelos, versões e personalização por rede.
3. Calendário, slots recorrentes e filas editoriais.
4. Engine de publicação, confirmação e retries.
5. Aprovação interna/cliente, histórico e magic links.
6. Social Inbox para as plataformas compatíveis.
7. Analytics autorizado, media library e notificações.

## Módulos que continuarão específicos da RISE

- Avenças por cliente: quantidade contratada por tipo e período; contagem do executado com regras de faturação.
- Aprovação dupla por versão (`copy` e `visual`) e comentários ancorados na imagem.
- Integrações Canva Pro, OpenAI por marca, Mailchimp, ClickUp e CRM RISE.
- RISE Competitive Intelligence (histórico verificável + fontes).
- Relatórios personalizados, conclusões editáveis, exportações e identidade visual RISE.

## Bloqueadores antes da operação com clientes reais

1. **Fonte de código:** obter repo completo BrightBean e fixar hash do commit; executar `pytest` upstream.
2. **Estabilidade:** reproduzir/validar reportes de duplicação de publicações, rascunhos, interface LinkedIn e analytics.
3. **Aprovação:** criar hook de autorização + gate de versão no caminho real de criação, agendamento e reenvio.
4. **Multicliente:** testar leitura, escrita e media com dois clientes isolados e roles diferentes.
5. **Armazenamento:** documentos privados não podem ficar no mesmo espaço público usado para media destinada a publicação.
6. **Migração:** comparação de contagens/versões/taxonomia entre WordPress e Django; verificação manual por amostragem.
7. **Integrações:** testes de Meta, LinkedIn e Canva com credenciais próprias, expiração e renovação de tokens.
8. **Legal:** AGPL-3.0, dados pessoais e acordos de processamento de dados.
9. **Localização:** traduzir interface PT-PT e testar datas, textos, fusos Europe/Lisbon e horário de verão.
10. **Operação:** backups, monitorização, logs sem tokens, alertas, rollback e desativação do publisher WordPress no momento da passagem final.

## Etapas com critérios de aceitação

### F1 — Preparação (kit entregue)
- Código do plugin WordPress 1.11 inspecionado.
- Exportador local só leitura, validador e extensão inicial RISE escritos.
- Testes portáveis e PHP lint aprovados.

### F2 — Fork BrightBean e ambiente de testes
- GitHub fork/branch próprio com commit fixado, testes do upstream executados.
- Django a executar com PostgreSQL num ambiente isolado sem dados de clientes.
- Nova extensão RISE integrada e testada com Django e modelos upstream.

### F3 — Migração de dados de demonstração
- Exportação real de **cópia de teste** do WordPress (sem contas de integração).
- Importação staging, relatório de discrepâncias e mapeamento de workspaces.
- Importação de posts/ficheiros/histórico com cobertura validada.

### F4 — UX e integrações
- Marca RISE, PT-PT, portal de cliente, aprovações, avenças e relatórios.
- Canva/IA/Mailchimp/CRM/ClickUp com permissões e credenciais testadas.

### F5 — Publicação social e produção controlada
- 1–2 clientes-piloto, redes sociais de teste, formatos reais, idempotência.
- Contagens e métricas reconciliadas, backups/restauro, rollback ensaiado.
- Só após validação formal fazer a mudança de plataforma.

## Observações técnicas prioritárias

- O plugin WP 1.11 contém `class-rise-hub.php` (tabelas `records`, `membership`, `versions`, `events`), `class-rise-hub-publisher.php`, `class-rise-hub-mailchimp.php` e `class-rise-hub-intelligence.php`.
- A aprovação WP 1.11 é calculada a partir dos eventos `component_approve` e `component_changes` para a mesma versão, com chaves `visual` e `copy`.
- A versão Django incluída neste kit implementa a política e modelos genéricos, mas não altera o publisher BrightBean: é um ponto de extensão, não uma integração funcional concluída.
- O BrightBean documenta login por convite (`SIGNUP_MODE=invite`) que deverá ser adotado numa plataforma privada da agência, após testar fluxos OAuth.
