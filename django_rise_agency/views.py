"""CSRF-protected RISE approvals UI, isolated to one authorised workspace.

Native BrightBean client portal magic-link sessions are NOT yet integrated;
this first pilot uses authenticated Django workspace members only.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.composer.models import Post
from apps.members.models import WorkspaceMembership
from apps.workspaces.models import Workspace

from .services import approval_status, approve_component, rise_dual_approval_enabled


def _authorized_workspace(request, workspace_id):
    workspace = get_object_or_404(Workspace, pk=workspace_id)
    membership = (
        WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=request.user,
        )
        .select_related("custom_role")
        .first()
    )
    if membership is None or not membership.effective_permissions.get("approve_posts", False):
        # Avoid exposing existence of another organisation's workspace.
        raise Http404("Área não disponível")
    return workspace, membership


@login_required
@require_GET
def approvals(request, workspace_id):
    workspace, membership = _authorized_workspace(request, workspace_id)
    if not rise_dual_approval_enabled(workspace.id):
        raise Http404("Aprovação RISE não está ativa")
    posts = Post.objects.filter(workspace_id=workspace.id)
    if not membership.effective_permissions.get("create_posts", False):
        posts = posts.filter(platform_posts__status="pending_client").distinct()
    posts = posts.prefetch_related("platform_posts", "media_attachments__media_asset").order_by("-created_at")[:60]
    rows = []
    for post in posts:
        # Keep all customer copy safe for HTML autoescape in the template.
        state = approval_status(post)
        rows.append({"post": post, "state": state})
    return render(
        request,
        "django_rise_agency/approvals.html",
        {
            "workspace": workspace,
            "rows": rows,
        },
    )


@login_required
@require_POST
def component_decision(request, workspace_id, post_id, component):
    workspace, membership = _authorized_workspace(request, workspace_id)
    if component not in ("copy", "visual"):
        raise Http404("Componente inválida")
    post = get_object_or_404(Post, pk=post_id, workspace_id=workspace.id)
    decision = (request.POST.get("decision") or "").strip()
    if decision not in ("approve", "revoke"):
        return HttpResponse("Decisão inválida", status=400)
    try:
        approve_component(post, request.user, component, decision == "approve")
    except (ValueError, PermissionError) as exc:
        return HttpResponse(str(exc), status=409)
    return redirect("rise_agency:approvals", workspace_id=workspace.id)
