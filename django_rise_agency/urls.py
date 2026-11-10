from django.urls import path

from . import dashboard, views

app_name = "rise_agency"
urlpatterns = [
    path("", dashboard.agency_dashboard, name="dashboard"),
    path("<uuid:workspace_id>/aprovacoes/", views.approvals, name="approvals"),
    path(
        "<uuid:workspace_id>/aprovacoes/<uuid:post_id>/<slug:component>/",
        views.component_decision,
        name="component_decision",
    ),
]
