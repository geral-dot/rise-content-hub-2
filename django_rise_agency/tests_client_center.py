"""Operação editorial RISE: autorização, consumo de avenças e classificação."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.composer.models import PlatformPost, Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.organizations.models import Organization
from apps.social_accounts.models import SocialAccount
from apps.workspaces.models import Workspace

from .models import RiseEditorialAssignment, RiseRetainer


class ClientCenterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="rise-client-centre@example.test",
            password="test-only",
            tos_accepted_at=timezone.now(),
        )
        cls.org_member = OrgMembership.objects.get(user=cls.user)
        cls.org = cls.org_member.organization
        cls.ws = Workspace.objects.create(organization=cls.org, name="Cliente A")
        cls.membership = WorkspaceMembership.objects.create(
            user=cls.user,
            workspace=cls.ws,
            workspace_role=WorkspaceMembership.WorkspaceRole.OWNER,
        )
        cls.foreign_org = Organization.objects.create(name="Fora")
        cls.foreign_ws = Workspace.objects.create(organization=cls.foreign_org, name="Cliente secreto")
        cls.foreign_post = Post.objects.create(workspace=cls.foreign_ws, caption="Material confidencial")
        cls.post = Post.objects.create(workspace=cls.ws, title="Campanha de teste", caption="Texto de teste")
        cls.another = Post.objects.create(workspace=cls.ws, title="Outra publicação", caption="Copy adicional")
        cls.retainer = RiseRetainer.objects.create(
            workspace=cls.ws, period="2026-11", posts_included=5, stories_included=2
        )

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, ws=None):
        return reverse("rise_agency:client_center", kwargs={"client_id": (ws or self.ws).id})

    def action(self, ws=None):
        return reverse("rise_agency:classify_content", kwargs={"client_id": (ws or self.ws).id})

    def classify(self, post=None, kind="post", period="2026-11"):
        return self.client.post(
            self.action(),
            {"post_id": str((post or self.post).id), "format": kind, "period": period},
        )

    def test_client_centre_shows_only_organization_scoped_information(self):
        res = self.client.get(self.url() + "?period=2026-11")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Cliente A")
        self.assertContains(res, "Campanha de teste")
        self.assertNotContains(res, "Cliente secreto")
        self.assertNotContains(res, "Material confidencial")

    def test_explicit_format_and_period_are_recorded_and_can_be_reassigned(self):
        res = self.classify()
        self.assertEqual(res.status_code, 302)
        item = RiseEditorialAssignment.objects.get(post=self.post)
        self.assertEqual((item.period, item.format), ("2026-11", "post"))
        res = self.client.get(self.url() + "?period=2026-11")
        self.assertEqual(res.context["counts"]["posts"], 1)
        self.assertEqual(res.context["counts"]["stories"], 0)
        self.assertEqual(res.context["posts_remaining"], 4)
        res = self.classify(kind="story")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(RiseEditorialAssignment.objects.filter(post=self.post).count(), 1)
        res = self.client.get(self.url() + "?period=2026-11")
        self.assertEqual(res.context["counts"]["posts"], 0)
        self.assertEqual(res.context["counts"]["stories"], 1)

    def test_one_post_across_multiple_social_accounts_counts_once(self):
        self.classify()
        for idx, platform in enumerate(("facebook", "instagram"), start=1):
            account = SocialAccount.objects.create(
                workspace=self.ws,
                platform=platform,
                account_platform_id=f"test-{idx}",
                account_name=f"Página {idx}",
            )
            PlatformPost.objects.create(
                post=self.post, social_account=account, status=PlatformPost.Status.PUBLISHED
            )
        res = self.client.get(self.url() + "?period=2026-11")
        self.assertEqual(res.context["counts"]["posts"], 1)
        self.assertEqual(res.context["counts"]["posts_published"], 1)

    def test_foreign_organization_is_not_exposed(self):
        self.assertEqual(self.client.get(self.url(self.foreign_ws)).status_code, 404)
        res = self.client.post(
            self.action(self.foreign_ws),
            {"post_id": str(self.foreign_post.id), "period": "2026-11", "format": "post"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertFalse(RiseEditorialAssignment.objects.filter(post=self.foreign_post).exists())

    def test_other_post_in_same_organization_cannot_be_assigned_to_wrong_brand(self):
        another_ws = Workspace.objects.create(organization=self.org, name="Cliente B")
        wrong_post = Post.objects.create(workspace=another_ws, caption="Outro cliente")
        res = self.classify(post=wrong_post)
        self.assertEqual(res.status_code, 404)
        self.assertFalse(RiseEditorialAssignment.objects.filter(post=wrong_post).exists())

    def test_client_membership_cannot_read_internal_editorial_centre_or_classify(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        self.membership.workspace_role = WorkspaceMembership.WorkspaceRole.CLIENT
        self.membership.save(update_fields=["workspace_role"])
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.classify().status_code, 404)

    def test_invalid_period_format_and_post_identifier_cannot_be_written(self):
        self.assertEqual(self.client.get(self.url() + "?period=2026-13").status_code, 400)
        self.assertEqual(self.classify(period="2026-13").status_code, 400)
        self.assertEqual(self.classify(kind="carousel").status_code, 400)
        self.assertEqual(
            self.client.post(self.action(), {"post_id": "invalid", "period": "2026-11", "format": "post"}).status_code,
            400,
        )
        self.assertFalse(RiseEditorialAssignment.objects.filter(post=self.post).exists())

    def test_member_with_editor_role_can_classify_without_editing_contract(self):
        self.org_member.org_role = OrgMembership.OrgRole.MEMBER
        self.org_member.save(update_fields=["org_role"])
        self.membership.workspace_role = WorkspaceMembership.WorkspaceRole.EDITOR
        self.membership.save(update_fields=["workspace_role"])
        res = self.client.get(self.url() + "?period=2026-11")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["can_classify"])
        self.assertFalse(res.context["is_manager"])
        self.assertEqual(self.classify().status_code, 302)
        self.assertFalse(res.context["is_manager"])
