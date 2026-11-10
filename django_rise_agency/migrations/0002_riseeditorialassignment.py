"""Explicit editorial classification for accurate retainer consumption.

Legacy posts remain unclassified until a RISE team member reviews them.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_rise_agency", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RiseEditorialAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(help_text="AAAA-MM", max_length=7)),
                ("format", models.CharField(choices=[("post", "Post"), ("story", "Story")], max_length=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "post",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rise_assignment",
                        to="composer.post",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rise_editorial_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="riseeditorialassignment",
            index=models.Index(fields=["period", "format"], name="rise_assgn_period_format_idx"),
        ),
    ]
