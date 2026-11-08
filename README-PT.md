# RISE Content Hub 2.0 — Fase 3 · Integração BrightBean

**Data:** 8 de novembro de 2026  
**Estado:** **overlay de desenvolvimento / pré-produção**. Este ZIP **não contém o BrightBean completo**, não é instalável no WordPress e **não está validado com contas sociais reais**.

## O que acrescenta à Fase 2

- Extensão Django **RISE Agency** ligada aos modelos reais do BrightBean Studio.
- Migração inicial Django preparada (`django_rise_agency/migrations/0001_initial.py`) para marcas, avenças, aprovações duplas e staging do WordPress.
- Interface independente de **aprovação de copy e imagem**, em português de Portugal e cores RISE, com formulários protegidos por CSRF e autenticação Django.
- Proteção por cliente/workspace: utilizadores com papel de cliente só podem consultar conteúdos no estado `pending_client`.
- Reaproveitamento do motor de publicação BrightBean com **verificação final RISE**, incluindo novas leituras de dados na base de dados para reduzir o risco de cache desatualizada.
- Instalador `apply_brightbean_hooks.py` que exige commit fixo e verifica os SHA Git de **7 ficheiros originais**, antes de modificar qualquer código.
- **11 alterações pontuais**: configuração, URLs, criação via API, transição para agendamento, editor, variante de conta, importação CSV, aprovação nativa, publicação e calendário.
- **23 testes portáteis**, sem Django, mais **4 testes de integração** preparados para execução numa instalação BrightBean real.

## Limitações importantes

1. **O código do BrightBean completo não está incluído**: o GitHub ligado permite ler os ficheiros, mas ainda não existe um repositório da RISE com permissões de escrita disponível. O overlay terá de ser aplicado a uma cópia do BrightBean.
2. **Não executámos o Django completo nem migrações reais**: não existem dependências Django/serviços de base de dados disponíveis neste ambiente. É obrigatório correr `makemigrations --check`, `migrate`, `manage.py check` e os testes upstream na instalação de desenvolvimento.
3. A interface RISE desta fase exige uma **sessão Django autenticada**; ainda **não** está ligada ao portal BrightBean de links mágicos. Não a disponibilizar a clientes externos até testar esse percurso.
4. A aprovação RISE aplica-se ao **Post completo**; uma alteração numa variante por plataforma invalida a aprovação de todo o conjunto. Isto é conservador e seguro, mas uma futura versão poderá oferecer aprovação independente por rede.
5. O original BrightBean dispõe de vários caminhos para agendar. Foram introduzidas proteções nos caminhos principais documentados, e existe um **bloqueio final antes do envio externo**. Ainda não foi feita uma prova de cobertura exaustiva de todas as tarefas, importações, recorrências ou plugins futuros.
6. Os ficheiros de media podem ter URLs públicos para integração com redes sociais; **não utilizar para documentos privados dos clientes** sem rever o armazenamento/URLs e as permissões.
7. O projeto BrightBean está licenciado sob **AGPL-3.0**. Rever cumprimento da licença antes de servir uma versão alterada através da Internet.
8. Não reutilizar automaticamente credenciais OAuth nem as filas antigas de publicação WordPress. Exigir reconexão e testes com contas de demonstração.

## Instalação num ambiente de desenvolvimento autorizado

Requisitos: Docker e serviços requeridos pelo BrightBean, Python conforme `.python-version` do projeto, PostgreSQL, alojamento de staging e uma cópia do código-fonte BrightBean em **commit exato** `1d11c52007a3f714979ff1b071d153e69a8c274a`.

```bash
# Numa máquina de desenvolvimento com acesso à Internet:
git clone https://github.com/brightbeanxyz/brightbean-studio.git rise-content-hub-2
cd rise-content-hub-2
git checkout 1d11c52007a3f714979ff1b071d153e69a8c274a
git switch -c rise/content-hub-v2

# Copiar o diretório django_rise_agency/ e apply_brightbean_hooks.py
# do ZIP Fase 3 para a raiz da cópia BrightBean.

# VALIDAR sem escrever código:
python apply_brightbean_hooks.py .

# APLICAR na branch de desenvolvimento; faz backups .rise-backup:
python apply_brightbean_hooks.py . --write

git diff --check
git diff --stat

# Preparar dependências e serviços conforme README oficial do BrightBean.
# Só depois, no ambiente Django completo:
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test django_rise_agency.tests_django
pytest
```

Não iniciar workers de publicação no momento do primeiro `migrate`. Desativar ligações a contas sociais reais no staging até à aprovação de segurança. O agendador BrightBean pode executar ações em background assim que é iniciado.

### Ativar apenas numa marca de teste

1. Entrar no Django admin como staff autorizado.
2. Criar `RiseBrandProfile` para um `Workspace` de teste e confirmar `enforce_dual_approval = True`.
3. Para um utilizador com `WorkspaceMembership` e permissão de aprovação, aceder a `https://staging.example/rise/<workspace_uuid>/aprovacoes/`.
4. Criar um post de demonstração com copy e ficheiro de imagem.
5. Aprovar apenas o texto: o post deve continuar bloqueado.
6. Aprovar imagem: o gate RISE passa, sem dispensar o workflow nativo BrightBean.
7. Alterar o copy: a aprovação deve tornar-se obsoleta.
8. Verificar que uma conta cliente não consegue aceder aos conteúdos de outro workspace, por URL direto ou POST.

### Importação do WordPress

A exportação da V1.11 e o staging continuam disponíveis da Fase 2:

```bash
RISE_EXPORT_OUTPUT="$HOME/rise-legacy-$(date +%Y%m%d).json" wp eval-file /caminho/export_rise_v111.php
python validate_export.py "$HOME/rise-legacy-AAAAMMDD.json"
python manage.py rise_stage_legacy "$HOME/rise-legacy-AAAAMMDD.json"  # dry-run
python manage.py rise_stage_legacy "$HOME/rise-legacy-AAAAMMDD.json" --apply
```

A importação **preserva apenas snapshots de auditoria**. Não cria novos clientes ou posts no BrightBean nem ativa publicações. O passo de mapeamento de identidades, clientes, conteúdos e ficheiros está previsto para a fase seguinte.

## Verificações executadas no ambiente de preparação

```bash
python -m unittest discover -s tests -v         # 23/23 aprovados
python -m compileall -q django_rise_agency
python -m py_compile apply_brightbean_hooks.py
php -l wordpress_export/export_rise_v111.php
```

Estes resultados atestam **sintaxe, políticas portáteis e transformações de patches simuladas**, não o funcionamento integrado do Django ou a publicação real.

### Ficheiros principais

| Ficheiro | Objetivo |
|---|---|
| `django_rise_agency/models.py` | Dados exclusivos RISE: perfil, avenças, aprovações, histórico, staging |
| `django_rise_agency/migrations/0001_initial.py` | Migração inicial, ainda por validar no upstream |
| `django_rise_agency/services.py` | Aprovação dupla, snapshot editorial, último gate antes de publicar |
| `django_rise_agency/views.py`, `urls.py` | Portal RISE autenticado e isolado por cliente |
| `django_rise_agency/templates/`, `static/` | Área visual de aprovações com identidade RISE |
| `apply_brightbean_hooks.py` | Instalação não destrutiva e versionada de 11 hooks |
| `django_rise_agency/tests_django.py` | Testes de integração para executar na instalação real |
| `tests/test_portable.py` | Testes offline executados nesta entrega |
| `wordpress_export/` | Exportação WordPress 1.11 somente leitura |

**Versão WordPress atual:** permanece intocada. **Domínio final:** não deve ser mudado antes de concluir staging, integrações de redes sociais, segurança e aceitação.
