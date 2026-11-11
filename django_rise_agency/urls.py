from django.urls import path

from . import (
    client_center,
    client_settings,
    competitive_intelligence,
    dashboard,
    integrations,
    monthly_reporting,
    views,
)

app_name = "rise_agency"
urlpatterns = [
    path("", dashboard.agency_dashboard, name="dashboard"),
    path("integracoes/", integrations.integrations, name="integrations"),
    path("integracoes/guardar/", integrations.save_integration, name="save_integration"),
    path("integracoes/remover/", integrations.disconnect_service, name="disconnect_service"),
    path("integracoes/mailchimp/publicos/", integrations.mailchimp_read, name="mailchimp_read"),
    path(
        "clientes/<uuid:client_id>/concorrencia/", competitive_intelligence.competitor_observations, name="competitors"
    ),
    path("clientes/<uuid:client_id>/ia/", integrations.ai_editor, name="ai_editor"),
    path("clientes/<uuid:client_id>/ia/gerar/", integrations.ai_generate, name="ai_generate"),
    path("clientes/<uuid:client_id>/relatorio/", monthly_reporting.report_detail, name="report_detail"),
    path("clientes/<uuid:client_id>/relatorio/guardar/", monthly_reporting.report_save, name="report_save"),
    path("clientes/<uuid:client_id>/relatorio/pdf/", monthly_reporting.report_pdf, name="report_pdf"),
    path("clientes/<uuid:client_id>/", client_center.client_center, name="client_center"),
    path("clientes/<uuid:client_id>/classificar/", client_center.classify_content, name="classify_content"),
    path("clientes/<uuid:client_id>/avenca/", client_settings.client_settings, name="client_settings"),
    path("<uuid:workspace_id>/aprovacoes/", views.approvals, name="approvals"),
    path(
        "<uuid:workspace_id>/aprovacoes/<uuid:post_id>/<slug:component>/",
        views.component_decision,
        name="component_decision",
    ),
]
