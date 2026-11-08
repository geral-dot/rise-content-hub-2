from django.urls import path

from . import views

app_name = "rise_agency"
urlpatterns = [
    path("<uuid:workspace_id>/aprovacoes/", views.approvals, name="approvals"),
    path(
        "<uuid:workspace_id>/aprovacoes/<uuid:post_id>/<slug:component>/",
        views.component_decision,
        name="component_decision",
    ),
]
