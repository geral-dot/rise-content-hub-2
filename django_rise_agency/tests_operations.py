"""RISE reporting, connector and AI regression tests, with no remote API calls."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.composer.models import Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace

from .models import RiseMonthlyReport, RiseServiceCredential


class RiseOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="rise-report@example.test",
            password="test-only",
            tos_accepted_at=timezone.now(),
        )
        cls.org_member = OrgMembership.objects.get(user=cls.user)
        cls.org = cls.org_member.organization
        cls.ws = Workspace.objects.create(organization=cls.org, name="Cliente A")
        cls.ws_membership = WorkspaceMembership.objects.create(
            user=cls.user,
            workspace=cls.ws,
            workspace_role=WorkspaceMembership.WorkspaceRole.OWNER,
        )
        cls.foreign_org = Organization.objects.create(name="Organização Privada")
        cls.foreign_ws = Workspace.objects.create(organization=cls.foreign_org, name="Cliente confidencial")

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, name, workspace=None):
        kw = {"client_id": (workspace or self.ws).pk} if name != "integrations" else {}
        return reverse("rise_agency:" + name, kwargs=kw)

    def test_report_save_and_download_pdf(self):
        res = self.client.post(
            self.url("report_save"),
            {
                "period": "2026-11",
                "followers": "500",
                "reach": "2400",
                "leads": "4",
                "ad_spend": "129.90",
                "data_source": "Meta Business Suite",
                "summary": "O alcance cresceu.",
                "conclusions": "Focar segmentos com intenção.",
                "next_steps": "Testar nova campanha.",
            },
        )
        self.assertEqual(res.status_code, 302)
        obj = RiseMonthlyReport.objects.get(workspace=self.ws, period="2026-11")
        self.assertEqual(obj.followers, 500)
        self.assertEqual(obj.ad_spend, Decimal("129.90"))
        report = self.client.get(self.url("report_detail") + "?period=2026-11")
        self.assertContains(report, "Meta Business Suite")
        pdf = self.client.get(self.url("report_pdf") + "?period=2026-11")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn("attachment", pdf["Content-Disposition"])
        self.assertEqual(pdf["Cache-Control"], "private, no-store")

    def test_report_compares_with_previous_available_month_without_inventing_values(self):
        RiseMonthlyReport.objects.create(
            workspace=self.ws,
            period="2026-09",
            followers=100,
            reach=800,
            data_source="Fonte setembro",
        )
        RiseMonthlyReport.objects.create(
            workspace=self.ws,
            period="2026-11",
            followers=125,
            data_source="Fonte novembro",
        )
        response = self.client.get(self.url("report_detail") + "?period=2026-11")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comparação com 2026-09")
        self.assertContains(response, "+25")
        self.assertNotContains(response, "Anterior: 800")

    def test_kpis_require_source_and_no_fabricated_zero(self):
        response = self.client.post(self.url("report_save"), {"period": "2026-11", "reach": "100"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RiseMonthlyReport.objects.filter(workspace=self.ws).exists())
        response = self.client.post(self.url("report_save"), {"period": "2026-11", "data_source": ""})
        self.assertEqual(response.status_code, 302)
        report = RiseMonthlyReport.objects.get(workspace=self.ws)
        self.assertIsNone(report.reach)

    def test_reports_never_expose_other_organizations(self):
        self.assertEqual(self.client.get(self.url("report_detail", self.foreign_ws)).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.url("report_save", self.foreign_ws), {"period": "2026-11", "data_source": "privado"}
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(self.url("report_pdf", self.foreign_ws)).status_code, 404)

    def test_client_member_cannot_see_internal_kpis(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        self.ws_membership.workspace_role = WorkspaceMembership.WorkspaceRole.CLIENT
        self.ws_membership.save(update_fields=["workspace_role"])
        self.assertEqual(self.client.get(self.url("report_detail")).status_code, 404)
        self.assertEqual(self.client.post(self.url("report_save"), {"period": "2026-11"}).status_code, 404)

    def test_integration_secrets_are_encrypted_and_never_rendered(self):
        secret = "mailchimp-sample-key-us21"
        res = self.client.post(
            reverse("rise_agency:save_integration"),
            {"provider": "mailchimp", "secret": secret, "data_center": "us21"},
        )
        self.assertEqual(res.status_code, 302)
        row = RiseServiceCredential.objects.get(organization=self.org, provider="mailchimp")
        self.assertEqual(row.secret, secret)
        page = self.client.get(reverse("rise_agency:integrations"))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, secret)
        self.assertContains(page, "Credencial presente")
        # Never permit data-center input to turn an outbound call into SSRF.
        res = self.client.post(
            reverse("rise_agency:save_integration"),
            {"provider": "mailchimp", "secret": secret, "data_center": "evil.example.com"},
        )
        self.assertEqual(res.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.data_center, "us21")

    @patch("django_rise_agency.integrations.httpx.Client")
    def test_mailchimp_reads_audiences_without_sending_any_campaign(self, mock_client):
        RiseServiceCredential.objects.create(
            organization=self.org,
            provider="mailchimp",
            secret="example-us21",
            data_center="us21",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"lists": [{"id": "123", "name": "Clientes da RISE"}]}
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        response = self.client.get(reverse("rise_agency:mailchimp_read"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clientes da RISE")
        mock_client.return_value.__enter__.return_value.get.assert_called_once()
        args = mock_client.return_value.__enter__.return_value.get.call_args
        self.assertIn("us21.api.mailchimp.com", args.args[0])

    def test_ai_requires_configured_key(self):
        res = self.client.get(self.url("ai_editor"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "ainda não está ligada")
        res = self.client.post(
            self.url("ai_generate"),
            {"topic": "Lançamento", "objective": "Apresentar um produto", "network": "linkedin"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Post.objects.filter(workspace=self.ws).count(), 0)

    @patch("django_rise_agency.integrations.httpx.post")
    def test_ai_generates_real_draft_without_publishing(self, mock_post):
        RiseServiceCredential.objects.create(organization=self.org, provider="openai", secret="test-key-only")
        response_mock = MagicMock()
        response_mock.json.return_value = {"choices": [{"message": {"content": "Texto para a marca."}}]}
        mock_post.return_value = response_mock
        res = self.client.post(
            self.url("ai_generate"),
            {"topic": "Novidade", "objective": "Explicar uma vantagem concreta", "network": "linkedin"},
        )
        self.assertEqual(res.status_code, 302)
        post = Post.objects.get(workspace=self.ws)
        self.assertEqual(post.caption, "Texto para a marca.")
        self.assertEqual(post.platform_posts.count(), 0)
        mock_post.assert_called_once()

    def test_integration_page_links_only_to_authorized_workspace(self):
        page = self.client.get(reverse("rise_agency:integrations"))
        self.assertEqual(page.status_code, 200)
        connect_url = reverse("social_accounts:connect", kwargs={"workspace_id": self.ws.pk})
        self.assertContains(page, connect_url)
        foreign_url = reverse("social_accounts:connect", kwargs={"workspace_id": self.foreign_ws.pk})
        self.assertNotContains(page, foreign_url)

    def test_admin_only_integration_configuration(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        self.assertEqual(self.client.get(reverse("rise_agency:integrations")).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("rise_agency:save_integration"),
                {"provider": "mailchimp", "secret": "sample-not-a-token", "data_center": "us21"},
            ).status_code,
            404,
        )
        self.assertFalse(RiseServiceCredential.objects.filter(organization=self.org).exists())
