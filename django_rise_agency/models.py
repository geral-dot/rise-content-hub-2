"""RISE extensions for BrightBean Studio, commit 1d11c52007a3f714979ff1b071d153e69a8c274a.

Additive tables only; never change BrightBean core DB tables here.
"""
from django.conf import settings
from django.db import models


class RiseBrandProfile(models.Model):
    """Opt-in RISE policy per BrightBean workspace; other workspaces unaffected."""

    workspace = models.OneToOneField(
        "workspaces.Workspace", on_delete=models.CASCADE,
        related_name="rise_profile",
    )
    voice_guidelines = models.TextField(blank=True)
    enforce_dual_approval = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class RiseRetainer(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE,
        related_name="rise_retainers",
    )
    period = models.CharField(max_length=7, help_text="AAAA-MM")
    posts_included = models.PositiveIntegerField(default=0)
    stories_included = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "period"], name="rise_retainer_work_period")
        ]


class RiseApprovalGate(models.Model):
    """Dual sign-off on the *exact* editorial snapshot of a BrightBean post."""

    post = models.OneToOneField(
        "composer.Post", on_delete=models.CASCADE,
        related_name="rise_gate",
    )
    content_version = models.PositiveIntegerField(default=1)
    snapshot_digest = models.CharField(max_length=64, blank=True, default="")
    copy_approved = models.BooleanField(default=False)
    visual_approved = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def approved(self):
        return self.copy_approved and self.visual_approved and bool(self.snapshot_digest)


class RiseApprovalHistory(models.Model):
    # Retain an audit entry if a post is removed, without blocking deletion.
    gate = models.ForeignKey(RiseApprovalGate, on_delete=models.SET_NULL, null=True, blank=True, related_name="history")
    post_id_at_decision = models.UUIDField(null=True, editable=False)
    content_version = models.PositiveIntegerField()
    snapshot_digest = models.CharField(max_length=64)
    component = models.CharField(max_length=8, choices=[("copy", "Texto"), ("visual", "Imagem")])
    approved = models.BooleanField()
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rise_approval_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class RiseLegacySnapshot(models.Model):
    """Non-destructive staging, *not* BrightBean post import."""

    source_table = models.CharField(max_length=40)
    source_id = models.PositiveBigIntegerField()
    source_client_id = models.PositiveBigIntegerField(default=0)
    source_kind = models.CharField(max_length=40, blank=True)
    checksum_sha256 = models.CharField(max_length=64)
    snapshot = models.JSONField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source_table", "source_id"], name="rise_legacy_table_id")
        ]
