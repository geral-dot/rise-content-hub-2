"""Testes de autorização para configurações exclusivas da RISE."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import OrgMembership
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace

from .models import RiseBrandProfile, RiseRetainer


class RiseClientSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email="agency-admin@example.test", password="test-only")
        cls.user.tos_accepted_at = timezone.now()
        cls.user.save(update_fields=["tos_accepted_at"])
        cls.org = Organization.objects.create(name="RISE Agência")
        cls.ws = Workspace.objects.create(organization=cls.org, name="Marca 1")
        cls.external_org = Organization.objects.create(name="Organização Externa")
        cls.external_ws = Workspace.objects.create(organization=cls.external_org, name="Marca Secreta")
        cls.org_member = OrgMembership.objects.create(
            user=cls.user, organization=cls.org, org_role=OrgMembership.OrgRole.ADMIN
        )

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, ws):
        return reverse("rise_agency:client_settings", kwargs={"client_id": ws.pk})

    def test_admin_can_save_retainer_and_editorial_rules(self):
        res = self.client.post(
            self.url(self.ws),
            {
                "period": "2026-11",
                "posts_included": "8",
                "stories_included": "4",
                "notes": "Teste",
                "voice_guidelines": "Tom de voz",
                "enforce_dual_approval": "on",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(RiseRetainer.objects.get(workspace=self.ws, period="2026-11").posts_included, 8)
        profile = RiseBrandProfile.objects.get(workspace=self.ws)
        self.assertTrue(profile.enforce_dual_approval)
        self.assertEqual(profile.voice_guidelines, "Tom de voz")

    def test_member_cannot_change_contract(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        response = self.client.post(
            self.url(self.ws),
            {"period": "2026-11", "posts_included": "99", "stories_included": "0"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(RiseRetainer.objects.filter(workspace=self.ws).exists())

    def test_no_cross_organization_access(self):
        self.assertEqual(self.client.get(self.url(self.external_ws)).status_code, 404)

    def test_invalid_period_or_negative_quantities_do_not_write(self):
        response = self.client.post(
            self.url(self.ws),
            {"period": "2026-33", "posts_included": "-1", "stories_included": "5"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RiseRetainer.objects.filter(workspace=self.ws).exists())
