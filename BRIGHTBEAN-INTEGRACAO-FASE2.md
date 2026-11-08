# Fase 2 — Aplicação da extensão RISE sobre BrightBean Studio

**Estado:** código de extensão e pontos de adaptação preparados e revistos estaticamente. Ainda não está instalado nem testado em Django real.

## Fluxo proposto para desenvolvimento

1. Criar um fork privado de trabalho do BrightBean **considerando os termos AGPL**, num repositório a que a equipa RISE tenha acesso. Não alterar a `main` original.
2. Criar branch a partir do commit verificado `1d11c52007a3f714979ff1b071d153e69a8c274a`.
3. Copiar `django_rise_agency/` para a raiz do projeto (ao lado de `apps/`), e `validate_export.py` se se pretender validar exportação de forma autónoma.
4. Acrescentar `"django_rise_agency.apps.RiseAgencyConfig"` a `LOCAL_APPS` em `config/settings/base.py`.
5. **Simular** a aplicação dos hooks: `python apply_brightbean_hooks.py /caminho/brightbean`.
6. Na branch de desenvolvimento, aplicar os hooks: `python apply_brightbean_hooks.py /caminho/brightbean --write`. Fazer revisão do diff antes de continuar.
7. No ambiente Django preparado a partir dos requisitos do BrightBean: `python manage.py makemigrations django_rise_agency && python manage.py migrate`.
8. Executar a suite upstream `pytest` e testes de integração específicos do gate (múltiplos clientes, conta de cliente, aprovação parcial, media alterado, publicação/retentativas, UTC/Lisboa).
9. Ativar o perfil RISE apenas em workspaces de teste. Todos os restantes workspaces continuam com o workflow nativo.
10. Construir endpoints e interface RISE para aprovar separadamente copy/visual, chamadas apenas após autorização. `approve_component()` não tem endpoint próprio neste kit.
11. Só depois de aprovar integração, mapear IDs do legado WordPress para workspaces, posts e assets reais. Primeiro importar dados de staging; nunca transportar os antigos agendamentos para fila ativa.

**Atenção:** neste kit, `_publish_platform_post` é um bloqueio de última linha. Falhas de aprovação são marcadas como `failed`, não enviadas para a plataforma. O agendamento nativo `pending_review` e variantes dependem de fluxos upstream e têm de ser testados com a UI. Esta abordagem precisa de ser revista em conjunto com os restantes estados antes de produção para evitar falsos erros editoriais na calendarização.

## Ficheiros por função

- `django_rise_agency/models.py`: clientes/marcas, avenças, aprovação dupla e histórico, staging.
- `django_rise_agency/services.py`: assinatura editorial, autorização do aprovador, gate de publicação.
- `django_rise_agency/fingerprint.py`: hash determinístico da versão editorial.
- `apply_brightbean_hooks.py`: valida e aplica hooks em dois pontos do código BrightBean.
- `wordpress_export/export_rise_v111.php`: exportador WordPress **só leitura**, para execução autorizada via WP-CLI.
- `validate_export.py`: verificador de consistência e campos sensíveis.
- `django_rise_agency/management/commands/rise_stage_legacy.py`: preserva dados históricos em staging, sem introduzir automaticamente posts no BrightBean.

## Critérios de aceitação para a próxima entrega

- Django arranca com a app RISE e migrations sem erros.
- A política impede agendamento e envio sem as duas aprovações.
- Alteração a copy ou media invalida aprovação anterior, incluindo variantes por rede.
- Cliente de uma marca não visualiza nem aprova conteúdos de outra.
- Publicação de demonstração, falhas de API e repetição produzem um único post remoto, confirmado por plataforma.
- Dados WordPress importados para staging sem divergências de contagem.
- Interface de cliente em PT-PT com identidade RISE validada.
