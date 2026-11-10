"""Vista geral da agência RISE: só leitura e com limites de organização/permissões."""

from collections import defaultdict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.composer.models import PlatformPost, Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.workspaces.models import Workspace

from .models import RiseBrandProfile, RiseRetainer


@login_required
@require_GET
def agency_dashboard(request):
    """Resumo real dos clientes autorizados; nunca mistura dados entre organizações."""
    org = getattr(request, "org", None)
    org_membership = getattr(request, "org_membership", None)
    if (
        org is None
        or org_membership is None
        or org_membership.organization_id != org.pk
        or org_membership.user_id != request.user.pk
    ):
        raise Http404("Organização não disponível")

    is_manager = org_membership.org_role in (
        OrgMembership.OrgRole.OWNER,
        OrgMembership.OrgRole.ADMIN,
    )
    clients = Workspace.objects.filter(organization_id=org.pk, is_archived=False)
    if not is_manager:
        clients = clients.filter(memberships__user_id=request.user.pk).distinct()
    clients = list(clients.order_by("name"))
    client_ids = [ws.pk for ws in clients]

    user_memberships = {
        item.workspace_id: item
        for item in WorkspaceMembership.objects.filter(
            user_id=request.user.pk, workspace_id__in=client_ids
        ).select_related("custom_role")
    }

    post_totals = {
        item["workspace_id"]: item["total"]
        for item in Post.objects.filter(workspace_id__in=client_ids).values("workspace_id").annotate(total=Count("id"))
    }

    status_totals = {
        item["post__workspace_id"]: item
        for item in PlatformPost.objects.filter(post__workspace_id__in=client_ids)
        .values("post__workspace_id")
        .annotate(
            pending=Count("id", filter=Q(status__in=["pending_review", "pending_client"])),
            scheduled=Count("id", filter=Q(status="scheduled")),
            published=Count("id", filter=Q(status="published")),
        )
    }

    # O fuso da organização determina o mês da avença, não o UTC do servidor.
    try:
        local_now = timezone.now().astimezone(ZoneInfo(org.default_timezone or "UTC"))
    except ZoneInfoNotFoundError:
        local_now = timezone.now()
    period = local_now.strftime("%Y-%m")
    retainers = {
        item.workspace_id: item for item in RiseRetainer.objects.filter(workspace_id__in=client_ids, period=period)
    }
    dual_approval_ids = set(
        RiseBrandProfile.objects.filter(workspace_id__in=client_ids, enforce_dual_approval=True).values_list(
            "workspace_id", flat=True
        )
    )

    summary = defaultdict(int)
    rows = []
    for workspace in clients:
        status = status_totals.get(workspace.pk, {})
        total_posts = post_totals.get(workspace.pk, 0)
        pending = status.get("pending", 0)
        scheduled = status.get("scheduled", 0)
        published = status.get("published", 0)
        summary["posts"] += total_posts
        summary["pending"] += pending
        summary["scheduled"] += scheduled
        summary["published"] += published
        permission = user_memberships.get(workspace.pk)
        rows.append(
            {
                "workspace": workspace,
                "post_count": total_posts,
                "pending": pending,
                "scheduled": scheduled,
                "published": published,
                "retainer": retainers.get(workspace.pk),
                "has_access": permission is not None,
                "can_approve": bool(permission and permission.effective_permissions.get("approve_posts", False)),
                "dual_approval": workspace.pk in dual_approval_ids,
            }
        )

    return render(
        request,
        "django_rise_agency/dashboard.html",
        {
            "agency": org,
            "clients": rows,
            "client_count": len(rows),
            "summary": dict(summary),
            "period": period,
            "is_manager": is_manager,
        },
    )
