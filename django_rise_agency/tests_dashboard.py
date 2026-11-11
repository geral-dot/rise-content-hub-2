"""Testes de isolamento da vista de agência (sem contas sociais reais)."""

from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.composer.models import PlatformPost, Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.organizations.models import Organization
from apps.social_accounts.models import SocialAccount
from apps.workspaces.models import Workspace

from .dashboard import agency_dashboard


class AgencyDashboardTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(email="rise-dashboard@example.test", password="test-only")
        self.org = Organization.objects.create(name="RISE")
        self.other_org = Organization.objects.create(name="Other")
        self.org_member = OrgMembership.objects.create(
            user=self.user, organization=self.org, org_role=OrgMembership.OrgRole.MEMBER
        )
        self.ours = Workspace.objects.create(organization=self.org, name="Cliente A")
        self.unauthorized = Workspace.objects.create(organization=self.org, name="Cliente privado")
        self.external = Workspace.objects.create(organization=self.other_org, name="Outra organização")
        WorkspaceMembership.objects.create(
            user=self.user, workspace=self.ours, workspace_role=WorkspaceMembership.WorkspaceRole.EDITOR
        )
        Post.objects.create(workspace=self.ours, caption="publicação A")
        Post.objects.create(workspace=self.unauthorized, caption="publicação privada")
        Post.objects.create(workspace=self.external, caption="publicação externa")

    def request(self, membership=None):
        req = self.factory.get("/rise/")
        req.user = self.user
        req.org = self.org
        req.org_membership = self.org_member if membership is None else membership
        return req

    def context(self, request):
        with patch("django_rise_agency.dashboard.render", return_value=HttpResponse("ok")) as render:
            response = agency_dashboard(request)
            self.assertEqual(response.status_code, 200)
            return render.call_args.args[2]

    def test_member_only_sees_assigned_workspace_and_counts(self):
        data = self.context(self.request())
        self.assertEqual(data["client_count"], 1)
        self.assertEqual([x["workspace"].name for x in data["clients"]], ["Cliente A"])
        self.assertEqual(data["summary"]["posts"], 1)
        self.assertFalse(data["clients"][0]["can_approve"])

    def test_admin_sees_other_workspaces_in_same_org_only(self):
        self.org_member.org_role = OrgMembership.OrgRole.ADMIN
        self.org_member.save(update_fields=["org_role"])
        data = self.context(self.request())
        self.assertEqual({x["workspace"].name for x in data["clients"]}, {"Cliente A", "Cliente privado"})
        self.assertEqual(data["summary"]["posts"], 2)
        row = next(x for x in data["clients"] if x["workspace"].name == "Cliente privado")
        self.assertFalse(row["has_access"])

    def test_forged_organization_membership_is_rejected(self):
        other_user = User.objects.create_user(email="outsider@example.test", password="test-only")
        foreign_membership = OrgMembership.objects.create(
            user=other_user, organization=self.other_org, org_role=OrgMembership.OrgRole.OWNER
        )
        with self.assertRaises(Http404):
            self.context(self.request(membership=foreign_membership))

    def test_status_totals_count_unique_editorial_posts_not_channel_variants(self):
        post = Post.objects.filter(workspace=self.ours).first()
        facebook = SocialAccount.objects.create(
            workspace=self.ours, platform="facebook",
            account_platform_id="fb-test-1", account_name="Cliente A Facebook",
        )
        instagram = SocialAccount.objects.create(
            workspace=self.ours, platform="instagram",
            account_platform_id="ig-test-1", account_name="Cliente A Instagram",
        )
        PlatformPost.objects.create(post=post, social_account=facebook, status="scheduled")
        PlatformPost.objects.create(post=post, social_account=instagram, status="scheduled")
        data = self.context(self.request())
        self.assertEqual(data["clients"][0]["scheduled"], 1)
        self.assertEqual(data["summary"]["scheduled"], 1)
        self.assertEqual(data["summary"]["posts"], 1)

    def test_daily_actions_are_limited_to_authorized_workspace(self):
        from apps.composer.models import PlatformPost
        from django.utils import timezone

        one = Post.objects.filter(workspace=self.ours).first()
        other = Post.objects.filter(workspace=self.unauthorized).first()
        account_a = SocialAccount.objects.create(
            workspace=self.ours, platform="facebook",
            account_platform_id="daily-fb-1", account_name="Authorized",
        )
        account_b = SocialAccount.objects.create(
            workspace=self.unauthorized, platform="facebook",
            account_platform_id="daily-fb-2", account_name="Private",
        )
        one.scheduled_at = timezone.now()
        one.save(update_fields=["scheduled_at"])
        PlatformPost.objects.create(post=one, social_account=account_a, status="failed")
        PlatformPost.objects.create(post=other, social_account=account_b, status="failed")
        data = self.context(self.request())
        self.assertEqual(len(data["daily_actions"]), 1)
        self.assertEqual(data["daily_actions"][0]["post"].pk, one.pk)

    def test_daily_actions_do_not_duplicate_post_across_channels(self):
        from apps.composer.models import PlatformPost

        post = Post.objects.filter(workspace=self.ours).first()
        for platform, native_id in (("facebook", "daily-fb-3"), ("instagram", "daily-ig-3")):
            account = SocialAccount.objects.create(
                workspace=self.ours, platform=platform,
                account_platform_id=native_id, account_name=platform,
            )
            PlatformPost.objects.create(post=post, social_account=account, status="pending_client")
        data = self.context(self.request())
        self.assertEqual(len(data["daily_actions"]), 1)
