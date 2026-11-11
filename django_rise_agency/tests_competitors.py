"""Regression tests for manually sourced competitor observations."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace

from .models import RiseCompetitorObservation


class CompetitorObservationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="rise-competitive@example.test",
            password="test-only",
            tos_accepted_at=timezone.now(),
        )
        cls.org_member = OrgMembership.objects.get(user=cls.user)
        cls.org = cls.org_member.organization
        cls.ws = Workspace.objects.create(organization=cls.org, name="Marca autorizada")
        cls.ws_member = WorkspaceMembership.objects.create(
            workspace=cls.ws, user=cls.user,
            workspace_role=WorkspaceMembership.WorkspaceRole.OWNER,
        )
        cls.other_org = Organization.objects.create(name="Organização externa")
        cls.other_ws = Workspace.objects.create(organization=cls.other_org, name="Marca privada")

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, workspace=None):
        return reverse("rise_agency:competitors", kwargs={"client_id": (workspace or self.ws).pk})

    def payload(self):
        return {
            "competitor_name": "Marca exemplo",
            "platform": "linkedin",
            "source_url": "https://example.org/publication",
            "observed_on": timezone.localdate().isoformat(),
            "observation": "Publicou um estudo com dados de origem identificada.",
            "opportunity": "Preparar conteúdo educativo original.",
        }

    def test_add_and_display_source_with_date(self):
        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 302)
        record = RiseCompetitorObservation.objects.get(workspace=self.ws)
        self.assertEqual(record.created_by, self.user)
        response = self.client.get(self.url())
        self.assertContains(response, "Marca exemplo")
        self.assertContains(response, "https://example.org/publication")

    def test_other_organization_is_not_readable_or_writable(self):
        self.assertEqual(self.client.get(self.url(self.other_ws)).status_code, 404)
        self.assertEqual(self.client.post(self.url(self.other_ws), self.payload()).status_code, 404)

    def test_future_observations_are_rejected(self):
        from datetime import timedelta

        data = self.payload()
        data["observed_on"] = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(self.url(), data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RiseCompetitorObservation.objects.exists())

    def test_client_role_cannot_access_internal_competitor_research(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        self.ws_member.workspace_role = WorkspaceMembership.WorkspaceRole.CLIENT
        self.ws_member.save(update_fields=["workspace_role"])
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url(), self.payload()).status_code, 404)
