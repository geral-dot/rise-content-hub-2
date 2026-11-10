from django.urls import path

from . import client_settings, dashboard, views

app_name = "rise_agency"
urlpatterns = [
    path("", dashboard.agency_dashboard, name="dashboard"),
    path("clientes/<uuid:client_id>/avenca/", client_settings.client_settings, name="client_settings"),
    path("<uuid:workspace_id>/aprovacoes/", views.approvals, name="approvals"),
    path(
        "<uuid:workspace_id>/aprovacoes/<uuid:post_id>/<slug:component>/",
        views.component_decision,
        name="component_decision",
    ),
]
