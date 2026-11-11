"""Evidence-based competitive intelligence observations per workspace."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_rise_agency", "0003_reports_integrations"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RiseCompetitorObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("competitor_name", models.CharField(max_length=150)),
                ("platform", models.CharField(choices=[
                    ("website", "Website"), ("facebook", "Facebook"),
                    ("instagram", "Instagram"), ("linkedin", "LinkedIn"), ("other", "Outro"),
                ], max_length=20)),
                ("source_url", models.URLField(max_length=1000)),
                ("observed_on", models.DateField()),
                ("observation", models.TextField(max_length=4000)),
                ("opportunity", models.TextField(blank=True, default="", max_length=4000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rise_competitor_observations", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rise_competitor_observations", to="workspaces.workspace")),
            ],
            options={"ordering": ["-observed_on", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="risecompetitorobservation",
            index=models.Index(fields=["workspace", "observed_on"], name="rise_comp_ws_observed_idx"),
        ),
    ]
