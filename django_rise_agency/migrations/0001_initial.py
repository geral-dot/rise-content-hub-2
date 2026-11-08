"""Initial RISE additive tables for BrightBean pinned 1d11c520.

Authored explicitly for a source-only integration kit; MUST be checked with
`python manage.py makemigrations --check --dry-run` on the full upstream tree.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("workspaces", "0003_alter_workspace_primary_color_and_more"),
        ("composer", "0023_platformpost_youtube_video_checked_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiseBrandProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("voice_guidelines", models.TextField(blank=True)),
                ("enforce_dual_approval", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="rise_profile", to="workspaces.workspace")),
            ],
        ),
        migrations.CreateModel(
            name="RiseApprovalGate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_version", models.PositiveIntegerField(default=1)),
                ("snapshot_digest", models.CharField(blank=True, default="", max_length=64)),
                ("copy_approved", models.BooleanField(default=False)),
                ("visual_approved", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("post", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="rise_gate", to="composer.post")),
            ],
        ),
        migrations.CreateModel(
            name="RiseRetainer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(help_text="AAAA-MM", max_length=7)),
                ("posts_included", models.PositiveIntegerField(default=0)),
                ("stories_included", models.PositiveIntegerField(default=0)),
                ("notes", models.TextField(blank=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rise_retainers", to="workspaces.workspace")),
            ],
        ),
        migrations.CreateModel(
            name="RiseLegacySnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_table", models.CharField(max_length=40)),
                ("source_id", models.PositiveBigIntegerField()),
                ("source_client_id", models.PositiveBigIntegerField(default=0)),
                ("source_kind", models.CharField(blank=True, max_length=40)),
                ("checksum_sha256", models.CharField(max_length=64)),
                ("snapshot", models.JSONField()),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="RiseApprovalHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content_version", models.PositiveIntegerField()),
                ("snapshot_digest", models.CharField(max_length=64)),
                ("component", models.CharField(choices=[("copy", "Texto"), ("visual", "Imagem")], max_length=8)),
                ("approved", models.BooleanField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post_id_at_decision", models.UUIDField(editable=False, null=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rise_approval_decisions", to=settings.AUTH_USER_MODEL)),
                ("gate", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="history", to="django_rise_agency.riseapprovalgate")),
            ],
        ),
        migrations.AddConstraint(
            model_name="riseretainer", constraint=models.UniqueConstraint(fields=("workspace", "period"), name="rise_retainer_work_period"),
        ),
        migrations.AddConstraint(
            model_name="riselegacysnapshot", constraint=models.UniqueConstraint(fields=("source_table", "source_id"), name="rise_legacy_table_id"),
        ),
    ]
