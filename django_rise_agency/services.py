"""RISE approval policy on top of BrightBean models (pinned upstream commit).

The last publisher hook is authoritative. These helpers never submit to a
social API and do not auto-approve the native BrightBean workflow.
"""
from django.db import transaction

from .fingerprint import snapshot_digest
from .editorial_policy import editorial_platform_options
from .models import RiseApprovalGate, RiseApprovalHistory, RiseBrandProfile


LOCKED_STATES = {"publishing", "published", "partially_published"}


def rise_dual_approval_enabled(workspace_id):
    """Opt-in: no RISE profile means native BrightBean behaviour is untouched."""
    return RiseBrandProfile.objects.filter(
        workspace_id=workspace_id, enforce_dual_approval=True
    ).exists()


def editorial_snapshot(post):
    """Editorial fields and media versions that a reviewer actually approves.

    Do NOT hash mutable publish outcomes, timestamps on posts, processing
    variants or analytics. Replacing the actual bytes of a media file without
    creating a new MediaAssetVersion must be prohibited by operational policy.
    """
    media = []
    attachments = post.media_attachments.select_related("media_asset").order_by("position", "id")
    for attachment in attachments:
        asset = attachment.media_asset
        media.append({
            "asset_id": str(attachment.media_asset_id),
            "asset_version_id": str(asset.current_version_id or ""),
            "asset_path": asset.file.name if asset.file else "",
            "asset_size": asset.file_size,
            "asset_type": asset.media_type,
            "position": attachment.position,
            "alt_text": attachment.alt_text,
            "overrides": attachment.platform_overrides,
        })
    platform_variants = []
    for pp in post.platform_posts.order_by("id"):
        platform_variants.append({
            "platform_post_id": str(pp.id),
            "social_account_id": str(pp.social_account_id),
            "title": pp.platform_specific_title,
            "caption": pp.platform_specific_caption,
            "first_comment": pp.platform_specific_first_comment,
            "media": pp.platform_specific_media,
            # Provider responses are merged into platform_extra after publishing.
            # Hash only editorial selections so one successful channel does not
            # invalidate approvals while its sibling channels are still queued.
            "editorial_options": editorial_platform_options(pp.platform_extra),
        })
    return {
        "title": post.title,
        "caption": post.caption,
        "first_comment": post.first_comment,
        "media": media,
        "platforms": platform_variants,
    }


def _has_copy(snapshot):
    return bool(snapshot["caption"].strip() or any((p["caption"] or "").strip() for p in snapshot["platforms"]))


def _has_visual(snapshot):
    return bool(snapshot["media"] or any(p["media"] for p in snapshot["platforms"]))


def _actor_membership(actor, post):
    from apps.members.models import WorkspaceMembership

    if not actor or not getattr(actor, "pk", None) or not getattr(actor, "is_authenticated", False):
        return None
    membership = WorkspaceMembership.objects.filter(
        user_id=actor.pk, workspace_id=post.workspace_id,
    ).select_related("custom_role").first()
    return membership if membership and membership.effective_permissions.get("approve_posts", False) else None


@transaction.atomic
def approve_component(post, actor, component, approved):
    """Bind one decision to an exact snapshot under a row lock.

    Locks parent Post so parallel post content saves cannot silently reuse an
    approval. Changes to PostMedia still get caught at dispatch by fingerprint.
    """
    from apps.composer.models import Post

    if component not in ("copy", "visual"):
        raise ValueError("Componente inválida")
    post = Post.objects.select_for_update().get(pk=post.pk)
    membership = _actor_membership(actor, post)
    if membership is None:
        raise PermissionError("Sem permissão para aprovar esta publicação")
    # Client accounts may not see or act on internal drafts.
    if not membership.effective_permissions.get("create_posts", False):
        if not post.platform_posts.filter(status="pending_client").exists():
            raise PermissionError("Esta publicação ainda não está disponível para aprovação do cliente")
    if not rise_dual_approval_enabled(post.workspace_id):
        raise ValueError("A aprovação dupla RISE não está ativa nesta marca")
    if post.platform_posts.filter(status__in=LOCKED_STATES).exists():
        raise ValueError("A publicação já está em envio ou publicada; crie uma nova versão")

    snapshot = editorial_snapshot(post)
    digest = snapshot_digest(snapshot)
    if approved and component == "copy" and not _has_copy(snapshot):
        raise ValueError("É necessário texto antes de aprovar")
    if approved and component == "visual" and not _has_visual(snapshot):
        raise ValueError("É necessário um ficheiro visual antes de aprovar")

    gate, _ = RiseApprovalGate.objects.select_for_update().get_or_create(post_id=post.pk)
    if gate.snapshot_digest and gate.snapshot_digest != digest:
        gate.content_version += 1
        gate.copy_approved = False
        gate.visual_approved = False
    gate.snapshot_digest = digest
    if component == "copy":
        gate.copy_approved = bool(approved)
    else:
        gate.visual_approved = bool(approved)
    gate.save(update_fields=[
        "content_version", "snapshot_digest", "copy_approved", "visual_approved", "updated_at",
    ])
    RiseApprovalHistory.objects.create(
        gate=gate, post_id_at_decision=post.pk, content_version=gate.content_version,
        snapshot_digest=digest, component=component,
        approved=bool(approved), actor=actor,
    )
    return gate


def approval_status(post):
    """Read-only status used by RISE views; no unexpected writes."""
    enabled = rise_dual_approval_enabled(post.workspace_id)
    if not enabled:
        return {"enabled": False, "approved": True, "copy": False, "visual": False, "stale": False}
    gate = RiseApprovalGate.objects.filter(post_id=post.pk).first()
    snapshot = editorial_snapshot(post)
    stale = bool(gate and gate.snapshot_digest != snapshot_digest(snapshot))
    return {
        "enabled": True,
        "approved": bool(gate and gate.approved and not stale and _has_copy(snapshot) and _has_visual(snapshot)),
        "copy": bool(gate and gate.copy_approved and not stale),
        "visual": bool(gate and gate.visual_approved and not stale),
        "stale": stale,
        "version": gate.content_version if gate else 1,
    }


def require_rise_post_approved(post):
    """Fail closed for RISE workspaces unless both components match content."""
    state = approval_status(post)
    if state["enabled"] and not state["approved"]:
        if state["stale"]:
            raise ValueError("RISE: o conteúdo mudou; é necessária nova aprovação de texto e imagem")
        raise ValueError("RISE: é necessária a aprovação do texto e da imagem antes de agendar ou publicar")


def require_rise_publishable(platform_post):
    """Final gate; called immediately before an outbound publish attempt."""
    from apps.composer.models import Post

    # Do not trust a cached post on a long-running publisher worker.
    # Fetch the latest source of truth immediately before outbound I/O.
    fresh_post = Post.objects.get(pk=platform_post.post_id)
    require_rise_post_approved(fresh_post)
