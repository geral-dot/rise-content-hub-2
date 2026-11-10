"""Centro de cliente RISE: operação, avenças e classificação editorial real.

Os indicadores contratados contam um Post uma única vez, independentemente
de quantas variantes sociais existirem. Os conteúdos sem classificação não
são inventados como posts nem stories.
"""

import re
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.composer.models import PlatformPost, Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.workspaces.models import Workspace

from .models import RiseBrandProfile, RiseEditorialAssignment, RiseRetainer
from .services import approval_status


STATUS_NAMES = {
    "draft": "Rascunho",
    "pending_review": "Em revisão interna",
    "pending_client": "A aguardar cliente",
    "approved": "Aprovado",
    "changes_requested": "Alterações pedidas",
    "rejected": "Rejeitado",
    "scheduled": "Agendado",
    "publishing": "Em publicação",
    "published": "Publicado",
    "partially_published": "Parcialmente publicado",
    "failed": "Falha na publicação",
    "on_hold": "Em espera",
}


def _client_access(request, client_id):
    org = getattr(request, "org", None)
    org_member = getattr(request, "org_membership", None)
    if (
        org is None
        or org_member is None
        or org_member.user_id != request.user.pk
        or org_member.organization_id != org.pk
    ):
        raise Http404("Cliente indisponível")
    workspace = get_object_or_404(Workspace, pk=client_id, organization_id=org.pk, is_archived=False)
    manager = org_member.org_role in (OrgMembership.OrgRole.OWNER, OrgMembership.OrgRole.ADMIN)
    member = (
        WorkspaceMembership.objects.filter(user_id=request.user.pk, workspace_id=workspace.pk)
        .select_related("custom_role")
        .first()
    )
    perms = member.effective_permissions if member else {}
    # O portal de cliente já tem o seu próprio fluxo. Não expor rascunhos RISE.
    can_create = bool(perms.get("create_posts", False))
    if not manager and not can_create:
        raise Http404("Cliente indisponível")
    return workspace, member, manager, manager or can_create


def _local_zone(workspace):
    try:
        return ZoneInfo(workspace.effective_timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _period_window(workspace, period):
    zone = _local_zone(workspace)
    if not period:
        period = timezone.now().astimezone(zone).strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise ValueError("Mês inválido")
    year, month = map(int, period.split("-"))
    if year < 2000 or year > 2099:
        raise ValueError("Mês fora do intervalo permitido")
    start = datetime(year, month, 1, tzinfo=zone)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = datetime(next_year, next_month, 1, tzinfo=zone)
    return period, start, end


@login_required
@require_GET
def client_center(request, client_id):
    workspace, membership, is_manager, can_classify = _client_access(request, client_id)
    try:
        period, start, end = _period_window(workspace, request.GET.get("period", ""))
    except ValueError:
        return HttpResponseBadRequest("Mês inválido. Indica AAAA-MM.")

    retainer = RiseRetainer.objects.filter(workspace_id=workspace.pk, period=period).first()
    profile = RiseBrandProfile.objects.filter(workspace_id=workspace.pk).first()

    classified = RiseEditorialAssignment.objects.filter(post__workspace_id=workspace.pk, period=period)
    # Variantes Facebook/Instagram/LinkedIn nunca duplicam uma entrega.
    counts = classified.aggregate(
        posts=Count("pk", filter=Q(format=RiseEditorialAssignment.Format.POST), distinct=True),
        stories=Count("pk", filter=Q(format=RiseEditorialAssignment.Format.STORY), distinct=True),
        posts_published=Count(
            "pk",
            filter=Q(format=RiseEditorialAssignment.Format.POST, post__platform_posts__status=PlatformPost.Status.PUBLISHED),
            distinct=True,
        ),
        stories_published=Count(
            "pk",
            filter=Q(format=RiseEditorialAssignment.Format.STORY, post__platform_posts__status=PlatformPost.Status.PUBLISHED),
            distinct=True,
        ),
    )
    unclassified = Post.objects.filter(
        workspace_id=workspace.pk,
        created_at__gte=start,
        created_at__lt=end,
        rise_assignment__isnull=True,
    ).order_by("-created_at")
    unclassified_count = unclassified.count()
    unclassified_rows = list(unclassified.prefetch_related("platform_posts")[:35])

    assignments = list(
        classified.select_related("post")
        .prefetch_related("post__platform_posts", "post__media_attachments__media_asset")
        .order_by("-post__created_at")[:60]
    )
    rows = []
    for assignment in assignments:
        post = assignment.post
        status = post.status
        approval = approval_status(post) if profile and profile.enforce_dual_approval else None
        rows.append(
            {
                "assignment": assignment,
                "post": post,
                "status": status,
                "status_name": STATUS_NAMES.get(status, "Em preparação"),
                "approval": approval,
            }
        )
    for post in unclassified_rows:
        post.rise_status_label = STATUS_NAMES.get(post.status, "Em preparação")

    return render(
        request,
        "django_rise_agency/client_center.html",
        {
            "workspace": workspace,
            "period": period,
            "retainer": retainer,
            "profile": profile,
            "counts": counts,
            "rows": rows,
            "unclassified_rows": unclassified_rows,
            "unclassified_count": unclassified_count,
            "all_classified_count": sum((counts["posts"], counts["stories"])),
            "is_manager": is_manager,
            "has_workspace_access": membership is not None,
            "can_create": bool(membership and membership.effective_permissions.get("create_posts", False)),
            "can_approve": bool(membership and membership.effective_permissions.get("approve_posts", False)),
            "can_classify": can_classify,
            "posts_remaining": max(0, retainer.posts_included - counts["posts"]) if retainer else None,
            "stories_remaining": max(0, retainer.stories_included - counts["stories"]) if retainer else None,
            "posts_progress": min(100, round(100 * counts["posts"] / retainer.posts_included))
            if retainer and retainer.posts_included
            else 0,
            "stories_progress": min(100, round(100 * counts["stories"] / retainer.stories_included))
            if retainer and retainer.stories_included
            else 0,
        },
    )


@login_required
@require_POST
def classify_content(request, client_id):
    workspace, _membership, _is_manager, can_classify = _client_access(request, client_id)
    if not can_classify:
        raise Http404("Cliente indisponível")
    period_value = request.POST.get("period", "").strip()
    try:
        period, _start, _end = _period_window(workspace, period_value)
        if not period_value:
            raise ValueError("Período em falta")
    except ValueError:
        return HttpResponseBadRequest("Mês inválido. Indica AAAA-MM.")
    content_format = request.POST.get("format", "").strip()
    if content_format not in RiseEditorialAssignment.Format.values:
        return HttpResponseBadRequest("Formato editorial inválido")
    post = get_object_or_404(Post, pk=request.POST.get("post_id"), workspace_id=workspace.pk)
    RiseEditorialAssignment.objects.update_or_create(
        post=post,
        defaults={
            "period": period,
            "format": content_format,
            "updated_by": request.user,
        },
    )
    messages.success(request, "Conteúdo associado à avença selecionada.")
    url = reverse("rise_agency:client_center", kwargs={"client_id": workspace.pk})
    return redirect(f"{url}?{urlencode({'period': period})}#conteudos")
