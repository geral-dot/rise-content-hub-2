"""RISE extensions for BrightBean Studio, commit 1d11c52007a3f714979ff1b071d153e69a8c274a.

Additive tables only; never change BrightBean core DB tables here.
"""

from django.conf import settings
from django.db import models

from apps.common.encryption import EncryptedTextField


class RiseBrandProfile(models.Model):
    """Opt-in RISE policy per BrightBean workspace; other workspaces unaffected."""

    workspace = models.OneToOneField(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="rise_profile",
    )
    voice_guidelines = models.TextField(blank=True)
    enforce_dual_approval = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class RiseRetainer(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="rise_retainers",
    )
    period = models.CharField(max_length=7, help_text="AAAA-MM")
    posts_included = models.PositiveIntegerField(default=0)
    stories_included = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "period"], name="rise_retainer_work_period")]


class RiseApprovalGate(models.Model):
    """Dual sign-off on the *exact* editorial snapshot of a BrightBean post."""

    post = models.OneToOneField(
        "composer.Post",
        on_delete=models.CASCADE,
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
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
        constraints = [models.UniqueConstraint(fields=["source_table", "source_id"], name="rise_legacy_table_id")]


class RiseEditorialAssignment(models.Model):
    """Classificação editorial explícita para contabilização de avenças RISE.

    Os posts legados não são classificados automaticamente: a distinção entre
    post e story não pode ser inferida com segurança das variantes por canal.
    """

    class Format(models.TextChoices):
        POST = "post", "Post"
        STORY = "story", "Story"

    post = models.OneToOneField(
        "composer.Post",
        on_delete=models.CASCADE,
        related_name="rise_assignment",
    )
    period = models.CharField(max_length=7, help_text="AAAA-MM")
    format = models.CharField(max_length=8, choices=Format.choices)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rise_editorial_assignments",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["period", "format"], name="rise_assgn_period_format_idx")]

    def __str__(self):
        return f"{self.post_id}: {self.format} {self.period}"


class RiseMonthlyReport(models.Model):
    """Monthly RISE report with manually validated KPI values and narrative.

    Null KPI = unknown, never silently converted to zero. The metrics are
    manually maintained until a verified provider import is implemented.
    """

    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.CASCADE, related_name="rise_reports")
    period = models.CharField(max_length=7, help_text="AAAA-MM")
    followers = models.PositiveBigIntegerField(null=True, blank=True)
    reach = models.PositiveBigIntegerField(null=True, blank=True)
    impressions = models.PositiveBigIntegerField(null=True, blank=True)
    interactions = models.PositiveBigIntegerField(null=True, blank=True)
    link_clicks = models.PositiveBigIntegerField(null=True, blank=True)
    leads = models.PositiveBigIntegerField(null=True, blank=True)
    conversions = models.PositiveBigIntegerField(null=True, blank=True)
    ad_spend = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    data_source = models.CharField(max_length=300, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    conclusions = models.TextField(blank=True, default="")
    next_steps = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rise_report_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "period"], name="rise_monthly_report_unique")]
        ordering = ["-period"]


class RiseServiceCredential(models.Model):
    """Encrypted per-organization tokens for optional API connectors.

    Never expose a secret in templates, forms or logs, and never copy
    credentials from the WordPress site without explicit authorization.
    """

    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        MAILCHIMP = "mailchimp", "Mailchimp"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rise_service_credentials",
    )
    provider = models.CharField(max_length=25, choices=Provider.choices)
    secret = EncryptedTextField(blank=True, default="")
    data_center = models.CharField(max_length=12, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "provider"], name="rise_service_org_provider")]


class RiseCompetitorObservation(models.Model):
    """Human-verified competitor evidence; never fabricate inaccessible metrics."""

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="rise_competitor_observations",
    )
    competitor_name = models.CharField(max_length=150)
    platform = models.CharField(
        max_length=20,
        choices=[
            ("website", "Website"),
            ("facebook", "Facebook"),
            ("instagram", "Instagram"),
            ("linkedin", "LinkedIn"),
            ("other", "Outro"),
        ],
    )
    source_url = models.URLField(max_length=1000)
    observed_on = models.DateField()
    observation = models.TextField(max_length=4000)
    opportunity = models.TextField(max_length=4000, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rise_competitor_observations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_on", "-created_at"]
        indexes = [
            models.Index(fields=["workspace", "observed_on"], name="rise_comp_ws_observed_idx"),
        ]
