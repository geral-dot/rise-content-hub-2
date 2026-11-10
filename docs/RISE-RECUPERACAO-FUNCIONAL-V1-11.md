# Recuperação do produto RISE Content Hub — paridade V1.11 → 2.0

> Documento de recuperação funcional, 10/11/2026. **Não equivale a funcionalidades já implementadas.** Criado em branch separada; não publicar no Railway antes de testes de aceitação.

## Decisão de produto

A experiência **RISE Content Hub V1.11 (WordPress)** é a referência de arquitetura de informação, navegação, fluxos e resultados. BrightBean é infraestrutura de publicação, calendário, caixa de entrada e analytics; não define a UX da agência. Não continuar com alterações meramente cosméticas à interface original.

**Situação atual verificada na branch RISE:** `django_rise_agency/urls.py` expõe dashboard, avenças/identidade, aprovações por componente; `models.py` regista perfil, avenças contratadas, gate de aprovações e snapshots legados. Estes componentes não substituem a aplicação editorial V1.11.

## Matriz de paridade (código/documentação; requer validação no navegador)

| Área funcional | Original WordPress V1.11 | Railway atual | Trabalho obrigatório |
|---|---|---|---|
| Dashboard | Área central RISE para conteúdos, clientes, KPIs | Dashboard RISE básico, áreas BrightBean separadas | Única entrada por organização; operação e alertas relevantes |
| Clientes e avenças | Clientes/marcas; quantitativos contratados, criados, aprovados, publicados, disponíveis | Workspaces + avença contratada por mês; contadores não integrados | Ficha completa por cliente, estados e consumo calculado |
| Calendário editorial | Calendário multicliente com filtros | Calendário global e publicação/calendário por workspace em navegações distintas | Calendário editorial RISE único, filtros, pré-visualização, criação |
| Editor | Copy + visual, anexos, ideias, pré-visualização | Editor BrightBean; aprovações RISE isoladas | Um só editor; fluxo direto para aprovação; manter versões |
| Aprovações | Imagem e copy independentes por versão, comentários, pontos na imagem, lotes | Gate de 2 componentes; fluxos BrightBean coexistem | Um só estado; aprovação dupla, comentários visuais e lotes, logs auditáveis |
| Portal do cliente | Clientes só veem a sua marca; aprovação/comentários | Portal genérico BrightBean com autorização própria | Portal com marca, aprovações dupla versão, notificações e histórico |
| Biblioteca | Biblioteca privada por cliente | Biblioteca BrightBean, proteção/armazenamento a verificar | Pastas por cliente + controlo rigoroso de URLs/funções |
| KPIs | Valores manuais, objetivos e histórico | Analytics sociais do BrightBean | KPIs próprios de agência, histórico e fontes |
| Relatórios | Relatório com marca RISE, conclusões editáveis e PDF pelo browser | Analytics genérico; sem módulo RISE equivalente | Relatório RISE com gráficos/intervalos/conclusões/exportação |
| Concorrência | Competitive Intelligence com fontes/datas, históricos, anúncios documentados, CSV | Sem módulo RISE equivalente na branch verificada | Migrar schema e construir painel por marca, sem inventar dados |
| Canva / IA | Integrações e assistente previstos em módulos WordPress, dependem de credenciais | Não reimplementados de modo equivalente no fluxo RISE | Criar conectores e comandos por cliente; testar permissões |
| Mailchimp | Módulo para campanhas sujeitas a aprovação | Sem fluxo RISE equivalente | Editor/versões/aprovação em separado e envio de teste |
| ClickUp / CRM | Criação assistida de tarefas e registos CRM, integração parcial | Sem integração equivalente no fluxo RISE | Sincronizar só após definir autorização e mapeamento |
| Redes sociais | OAuth Meta/LinkedIn preparado, não validado em produção | Engine BrightBean com OAuth, sem credenciais Meta/LinkedIn configuradas no Railway | Configurar apps/permissões/callbacks de teste antes de publicar |
| Idioma e UX | Termos PT-PT orientados à agência | Parcial PT-PT, telas avançadas ainda BrightBean | Glossário único e auditoria página a página |

**Importante:** relatório de auditoria V1.11 classificou WordPress como piloto: testes reais de OAuth, WordPress, segurança e publicação estavam pendentes. Não anunciar essas integrações como operacionalmente validadas nem migrar credenciais sem procedimento seguro.

## Estrutura de navegação alvo (RISE)

1. **Visão geral** — operação da agência, entregas em risco, aprovações, clientes.
2. **Clientes** — ficha de marca, avença, diretrizes, concorrência, KPIs, equipa e acessos.
3. **Calendário editorial** — vistas multicliente e por marca.
4. **Conteúdos** — ideias, rascunhos, editor, versões, biblioteca.
5. **Aprovações** — fila interna/cliente, copy, visual, comentários, aprovação em lote.
6. **Publicações** — agendadas, publicadas, falhas e ligações sociais (tecnologia BrightBean).
7. **Relatórios e inteligência** — KPIs, relatórios RISE, concorrência.
8. **Integrações** — redes sociais, Canva, OpenAI, Mailchimp, ClickUp, CRM.
9. **Definições** — apenas admins; utilizadores e organização.

**Evitar** entradas duplicadas Publish/Publicações/Calendário/Cross Calendar, Settings/Workspace Settings e dashboards paralelos. Os fluxos técnicos herdados não devem ser eliminados até existirem rotas equivalentes e testes.

## Ordem de execução e critérios de aceitação

### Fase 0 — preservar original e conhecer dados
- [ ] Obter o ZIP/código da V1.11 **ou cópia fiel do plugin instalado**; manter website original intacto.
- [ ] Capturar navegação, ecrãs e fluxos reais do original; identificar o que estava de facto operacional.
- [ ] Exportar dados do WordPress num ambiente de testes, com backup recuperável; nunca copiar tokens/palavras-passe em claro.
- [ ] Identificar mapeamento clientes, utilizadores, posts, versões, aprovações, comentários, KPIs e concorrentes.

### Fase 1 — recuperar operação quotidiana
- [ ] Dashboard da agência com indicadores corretos; não contar variantes por canal como posts únicos.
- [ ] Ficha de cliente + avença contratada/prod/validada/publicada/restante.
- [ ] Calendário editorial unificado por cliente e geral, editor com visual/copy/versões.
- [ ] Aprovação de texto e imagem na mesma versão, sem fluxos contraditórios; comentários por ponto e em lote.
- [ ] Portal cliente limitado à marca e ao que foi submetido a aprovação.
- [ ] Teste navegador com 2 organizações, 2 clientes, 2 membros e 1 utilizador cliente.

### Fase 2 — recuperar valor estratégico
- [ ] KPIs manuais/históricos e objetivos.
- [ ] Relatórios PDF RISE e conclusões editáveis.
- [ ] Competitive Intelligence com fontes, datas, escassez de dados, exportação CSV.
- [ ] Testar integridade dos dados importados e políticas de acesso.

### Fase 3 — ligar tecnologias externas e operações reais
- [ ] Meta/Instagram/LinkedIn OAuth com contas fictícias, scopes, revisão e reconexão.
- [ ] Canva/IA, Mailchimp e ClickUp/CRM, respetivas permissões e limites.
- [ ] Agendamento, publicação, recuperação de erros e reconciliação com plataforma remota.
- [ ] Armazenamento privado persistente, backups e RGPD; pentest e testes de acesso.

## Regras de lançamento

- Não substituir o WordPress original nem desligá-lo antes de paridade funcional e migração auditada.
- Não fazer merge nem deploy de nova interface como “produto recuperado” por apenas mudar cor/copy.
- Publicar em staging isolado; só atualizar o URL principal com aprovação dos fluxos.
- Nenhuma funcionalidade aparece como “integrada” até passar teste end-to-end e de permissões.
- Referências de documentação: README-PT V1.6, README-V1.11 Intelligence, Auditoria Técnica V1.11 presentes na Library da agência.
