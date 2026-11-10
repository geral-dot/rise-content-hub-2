"""Monthly KPI reporting and encrypted optional connector secrets for RISE."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.common.encryption


class Migration(migrations.Migration):
    dependencies = [
        ("django_rise_agency", "0002_riseeditorialassignment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="RiseMonthlyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(help_text="AAAA-MM", max_length=7)),
                ("followers", models.PositiveBigIntegerField(blank=True, null=True)),
                ("reach", models.PositiveBigIntegerField(blank=True, null=True)),
                ("impressions", models.PositiveBigIntegerField(blank=True, null=True)),
                ("interactions", models.PositiveBigIntegerField(blank=True, null=True)),
                ("link_clicks", models.PositiveBigIntegerField(blank=True, null=True)),
                ("leads", models.PositiveBigIntegerField(blank=True, null=True)),
                ("conversions", models.PositiveBigIntegerField(blank=True, null=True)),
                ("ad_spend", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("data_source", models.CharField(blank=True, default="", max_length=300)),
                ("summary", models.TextField(blank=True, default="")),
                ("conclusions", models.TextField(blank=True, default="")),
                ("next_steps", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rise_report_updates", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rise_reports", to="workspaces.workspace")),
            ],
            options={"ordering": ["-period"]},
        ),
        migrations.CreateModel(
            name="RiseServiceCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("openai", "OpenAI"), ("mailchimp", "Mailchimp")], max_length=25)),
                ("secret", apps.common.encryption.EncryptedTextField(blank=True, default="")),
                ("data_center", models.CharField(blank=True, default="", max_length=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rise_service_credentials", to="organizations.organization")),
            ],
        ),
        migrations.AddConstraint(model_name="risemonthlyreport", constraint=models.UniqueConstraint(fields=("workspace", "period"), name="rise_monthly_report_unique")),
        migrations.AddConstraint(model_name="riseservicecredential", constraint=models.UniqueConstraint(fields=("organization", "provider"), name="rise_service_org_provider")),
    ]
