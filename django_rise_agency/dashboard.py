"""Vista geral da agência RISE: só leitura e com limites de organização/permissões."""

from collections import defaultdict
from datetime import timedelta
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

    # A single editorial piece may target several social accounts. Count distinct
    # posts per state to avoid inflating the agency overview by channel variants.
    status_totals = {
        item["post__workspace_id"]: item
        for item in PlatformPost.objects.filter(post__workspace_id__in=client_ids)
        .values("post__workspace_id")
        .annotate(
            pending=Count("post_id", filter=Q(status__in=["pending_review", "pending_client"]), distinct=True),
            scheduled=Count("post_id", filter=Q(status="scheduled"), distinct=True),
            published=Count("post_id", filter=Q(status="published"), distinct=True),
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

    # Ação diária: apenas conteúdos de clientes autorizados. Cada Post é
    # apresentado uma vez, mesmo quando tem vários canais associados.
    workable_ids = [
        ws.pk
        for ws in clients
        if user_memberships.get(ws.pk) and user_memberships[ws.pk].effective_permissions.get("create_posts", False)
    ]
    visible_ids = client_ids if is_manager else workable_ids
    now = timezone.now()
    upcoming_limit = now + timedelta(days=7)
    next_posts = (
        Post.objects.filter(
            workspace_id__in=visible_ids,
            platform_posts__status__in=["pending_review", "pending_client", "scheduled", "failed"],
        )
        .distinct()
        .select_related("workspace")
        .prefetch_related("platform_posts")
        .order_by("scheduled_at", "-created_at")[:80]
    )
    daily_actions = []
    for post in next_posts:
        statuses = {variant.status for variant in post.platform_posts.all()}
        scheduled_for = post.scheduled_at
        if "failed" in statuses:
            label, urgency = "Falha de publicação", 0
        elif "pending_client" in statuses:
            label, urgency = "A aguardar aprovação do cliente", 1
        elif "pending_review" in statuses:
            label, urgency = "A aguardar revisão interna", 2
        elif "scheduled" in statuses and scheduled_for and scheduled_for < now:
            label, urgency = "Agendamento por verificar", 0
        elif "scheduled" in statuses and scheduled_for and scheduled_for <= upcoming_limit:
            label, urgency = "Publicação nos próximos 7 dias", 3
        else:
            continue
        daily_actions.append(
            {
                "post": post,
                "workspace": post.workspace,
                "label": label,
                "urgency": urgency,
                "scheduled_for": scheduled_for,
            }
        )
    daily_actions.sort(key=lambda item: (item["urgency"], item["scheduled_for"] or now))
    daily_actions = daily_actions[:12]

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
                "can_operate": bool(permission and permission.effective_permissions.get("create_posts", False)),
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
            "daily_actions": daily_actions,
            "is_manager": is_manager,
        },
    )
