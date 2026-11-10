# Fase UI 1 — RISE Content Hub 2.0

Branch isolada `rise/agency-dashboard-v1`, para revisão antes do deploy no Railway.

## Incluído
- `/rise/`: dashboard de agência em português com KPIs reais e ligações ao calendário.
- Carteira multicliente limitada à organização ativa; utilizadores comuns apenas veem workspaces em que participam.
- Indicadores de publicações por estado de entrega/canal, e avenças mensais já existentes.
- Menus de acesso rápido à visão geral, à carteira e ao calendário global; identidade visual RISE aplicada via CSS adicional.
- O código do BrightBean de publicação, autenticação e redes sociais não foi substituído.

## Importante
- Os indicadores 'em aprovação', 'agendadas' e 'publicadas' contam entregas `PlatformPost` por canal; 'conteúdos' conta `Post` único.
- Avenças mostram valores contratados, NÃO o consumo real.
- A ação 'Aprovações RISE' só é visível para membros com permissão e quando a política RISE está ativa.
- O WordPress original não é alterado.
- Não criar posts nem conectar clientes reais até testar permissões e armazenamento privado.

## Para testar
`python manage.py test django_rise_agency.tests_django django_rise_agency.tests_dashboard`

Depois, verificar no navegador (desktop/mobile) os menus e `/rise/` com 2 organizações e 2 utilizadores com permissões diferentes.
