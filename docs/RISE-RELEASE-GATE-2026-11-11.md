# RISE Content Hub 2.0 — checklist de lançamento (11/11/2026)

## Factos confirmados
- Railway project: renewed-insight; Web e Worker na branch `rise/content-hub-v2`.
- Web e Worker + PostgreSQL: deploy SUCCESS em 10/11/2026.
- Existe volume persistente PostgreSQL; não existe volume montado no serviço Web nem bucket no projeto.
- Logs Web: `404 /media/workspaces/icons/2026/11/Prancheta_18.png` repetido.
- Código RISE inclui: centro de cliente, avença, aprovação dual, KPI manual, PDF com ReportLab, geração de rascunhos OpenAI e consulta de públicos Mailchimp.
- A presença de código não confirma integrações autorizadas nem execução end-to-end.

## Portão de segurança antes do próximo deploy
- [ ] Identificar e salvar media existente; não montar volume vazio sobre diretório com ficheiros.
- [ ] Definir armazenamento persistente e URLs públicos de media necessários à publicação.
- [ ] Recuperar ficheiros em falta e validar todas as imagens.
- [ ] Testar backup/restore de base de dados e media.
- [ ] Criar ambiente staging e executar CI + testes de permissões.

## Produto e experiência
- [ ] Navigation única RISE, PT-PT consistente, remover redundâncias BrightBean.
- [ ] Calendário único multi-cliente e editor com variantes por rede.
- [ ] Fluxo de copy+visual por versão: cliente, comentários na imagem, lote e auditoria.
- [ ] Portal do cliente com âmbito apenas do workspace e acesso simplificado.
- [ ] Biblioteca com pastas e storage persistente.
- [ ] KPIs históricos, PDFs, fontes de dados e conclusões editáveis.
- [ ] Competitive Intelligence: concorrentes, fontes, datas e relatórios.

## Integrações e aceitação
- [ ] Meta (Facebook + Instagram) app, redirect URIs, scopes, OAuth, publicação de teste e reconexão.
- [ ] LinkedIn pessoal/empresa: autorizações adequadas, scopes e publicação de teste.
- [ ] OpenAI: chave própria, rascunhos por marca, confirmação humana.
- [ ] Mailchimp: chave e DC, públicos, campanhas com versão/aprovação, envio de teste sem publicação automática.
- [ ] Canva Pro, ClickUp e CRM RISE: contratos de API e permissão por marca.
- [ ] Avaliar RGPD, isolamento entre organizações e verificação de licenciamento AGPL da base.

## Estado do trabalho nesta auditoria
- PR #7, baseado na branch de produção, altera contagens de publicações para conteúdo único, termina tradução do ecrã de ligação de redes, acrescenta navegação para ligação de redes por cliente e inclui testes.
- PR #6 foi fechado: estava baseado em `main`, não na branch publicada.
- Nenhuma alteração foi aplicada em produção sem validação de armazenamento e testes reais.
