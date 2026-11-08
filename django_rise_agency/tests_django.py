"""Integration tests requiring actual BrightBean + Django + migrations.

Run only after installing the upstream project on a disposable database:
    python manage.py test django_rise_agency.tests_django
These tests MUST NOT be mistaken for the offline tests shipped in /tests.
"""

from django.test import TestCase

from apps.composer.models import Post, PostMedia
from apps.media_library.models import MediaAsset
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace

from .fingerprint import snapshot_digest
from .models import RiseApprovalGate, RiseBrandProfile, RiseRetainer
from .services import editorial_snapshot, require_rise_post_approved


class RiseDjangoIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name="RISE QA Test")
        cls.workspace = Workspace.objects.create(organization=cls.organization, name="Cliente A")
        cls.post = Post.objects.create(workspace=cls.workspace, caption="Teste editorial A")

    def test_opt_in_only(self):
        require_rise_post_approved(self.post)  # Native BrightBean unchanged.
        RiseBrandProfile.objects.create(workspace=self.workspace)
        with self.assertRaises(ValueError):
            require_rise_post_approved(self.post)

    def test_dual_approval_needs_visual(self):
        RiseBrandProfile.objects.create(workspace=self.workspace)
        gate = RiseApprovalGate.objects.create(
            post=self.post,
            snapshot_digest=snapshot_digest(editorial_snapshot(self.post)),
            copy_approved=True,
            visual_approved=True,
        )
        self.assertTrue(gate.approved)
        with self.assertRaises(ValueError):
            require_rise_post_approved(self.post)  # No media attached yet.

    def test_changes_to_caption_invalidate_approval(self):
        RiseBrandProfile.objects.create(workspace=self.workspace)
        asset = MediaAsset.objects.create(
            organization=self.organization,
            workspace=self.workspace,
            filename="image.jpg",
            file="media_library/image.jpg",
            media_type="image",
            file_size=200,
        )
        PostMedia.objects.create(post=self.post, media_asset=asset, position=0)
        digest = snapshot_digest(editorial_snapshot(self.post))
        RiseApprovalGate.objects.create(
            post=self.post, snapshot_digest=digest, copy_approved=True, visual_approved=True
        )
        require_rise_post_approved(self.post)
        self.post.caption = "Texto alterado depois da aprovação"
        self.post.save(update_fields=["caption", "updated_at"])
        with self.assertRaises(ValueError):
            require_rise_post_approved(self.post)

    def test_retainer_per_client(self):
        RiseRetainer.objects.create(workspace=self.workspace, period="2026-11", posts_included=8, stories_included=4)
        other = Workspace.objects.create(organization=self.organization, name="Cliente B")
        RiseRetainer.objects.create(workspace=other, period="2026-11", posts_included=2)
        self.assertEqual(RiseRetainer.objects.filter(workspace=self.workspace).count(), 1)
        self.assertEqual(RiseRetainer.objects.filter(workspace=other).count(), 1)
