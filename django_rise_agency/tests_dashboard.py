"""Testes de isolamento da vista de agência (sem contas sociais reais)."""
from unittest.mock import patch

from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.composer.models import Post
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.organizations.models import Organization
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
