"""Offline unit and safety tests (no Django / external API calls)."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apply_brightbean_hooks import PIN, HOOKS, EXPECTED_BLOBS, plan_patches
from django_rise_agency.editorial_policy import (
    client_can_review, editorial_platform_options, has_approved_components,
)
from django_rise_agency.fingerprint import snapshot_digest
from django_rise_agency.policy import ApprovalState
from validate_export import audit


class EditorialPolicyTests(unittest.TestCase):
    def test_requires_copy_visual_and_both_decisions(self):
        state = ApprovalState(1).decision(1, "visual", True)
        self.assertFalse(state.can_publish(True, True))
        state = state.decision(1, "copy", True)
        self.assertTrue(state.can_publish(True, True))
        self.assertFalse(state.can_publish(False, True))

    def test_revision_invalidates_both_approvals(self):
        state = ApprovalState(2).decision(2, "copy", True).decision(2, "visual", True)
        new_state = state.change_version(3)
        self.assertFalse(new_state.can_publish(True, True))
        with self.assertRaises(ValueError):
            new_state.decision(2, "visual", True)

    def test_revocation_cancels_approval(self):
        state = ApprovalState(1).decision(1, "copy", True).decision(1, "visual", True)
        self.assertFalse(state.decision(1, "visual", False).can_publish(True, True))

    def test_input_validation(self):
        with self.assertRaises(ValueError): ApprovalState(0)
        with self.assertRaises(ValueError): ApprovalState(1).decision(1, "other", True)
        with self.assertRaises(ValueError): ApprovalState(2).change_version(2)

    def test_client_visibility(self):
        for statuses in (["draft"], ["pending_review"], ["approved", "scheduled"], []):
            self.assertFalse(client_can_review(statuses))
        self.assertTrue(client_can_review(["pending_client", "pending_review"]))

    def test_component_digest_gate(self):
        digest = "a" * 64
        self.assertTrue(has_approved_components(True, True, digest, digest))
        self.assertFalse(has_approved_components(True, True, digest, "b" * 64))
        self.assertFalse(has_approved_components(True, False, digest, digest))
        self.assertFalse(has_approved_components(False, True, digest, digest))
        self.assertFalse(has_approved_components(True, True, "", ""))


class FingerprintTests(unittest.TestCase):
    def test_stable_key_order(self):
        self.assertEqual(snapshot_digest({"copy": "x", "visual": ["v"]}),
                         snapshot_digest({"visual": ["v"], "copy": "x"}))

    def test_caption_change(self):
        self.assertNotEqual(snapshot_digest({"copy": "A", "visual": ["x"]}),
                            snapshot_digest({"copy": "B", "visual": ["x"]}))

    def test_media_version_change(self):
        base = {"media": [{"asset_id": "x", "asset_version_id": "v1", "asset_size": 100}]}
        updated = copy.deepcopy(base)
        updated["media"][0]["asset_version_id"] = "v2"
        self.assertNotEqual(snapshot_digest(base), snapshot_digest(updated))

    def test_editorial_settings_are_included(self):
        d1 = editorial_platform_options({"privacy_level": "PUBLIC", "status_id": "remote-1"})
        d2 = editorial_platform_options({"privacy_level": "PRIVATE", "status_id": "remote-2"})
        self.assertNotEqual(snapshot_digest(d1), snapshot_digest(d2))

    def test_provider_response_does_not_invalidate(self):
        before = editorial_platform_options({"board_id": "123", "remote_post_id": "old"})
        after = editorial_platform_options({"board_id": "123", "remote_post_id": "new", "status_code": 200})
        self.assertEqual(before, after)
        self.assertEqual(snapshot_digest(before), snapshot_digest(after))


class HookSafetyTests(unittest.TestCase):
    def test_fixed_upstream_revision(self):
        self.assertEqual(len(PIN), 40)
        self.assertTrue(all(len(sha) == 40 for sha in EXPECTED_BLOBS.values()))

    def test_each_hook_has_a_unique_marker(self):
        self.assertEqual(len(HOOKS), len({hook.tag for hook in HOOKS}))
        self.assertEqual(len(HOOKS), 11)
        for hook in HOOKS:
            if hook.tag == "RISE_GUARD_ACCOUNT_SCHEDULE":
                self.assertIn("require_publishable(pp)", hook.replacement)
                self.assertIn("except ValueError as exc", hook.replacement)
            elif hook.tag == "RISE_GUARD_CALENDAR_BULK":
                self.assertIn("pp.transition_to", hook.replacement)
            else:
                self.assertIn(hook.anchor, hook.replacement)
            self.assertIn(hook.tag, hook.replacement)
            self.assertIn(hook.file, EXPECTED_BLOBS)

    def _fake_files(self):
        # Tiny fixtures containing exactly the confirmed source anchors.
        # These are tests of the patch algorithm, NOT Django integration tests.
        sources = {}
        for hook in HOOKS:
            sources.setdefault(hook.file, "")
            sources[hook.file] += ("# spacer\n" + hook.anchor)
        return sources

    def test_plan_creates_all_changes(self):
        result = plan_patches(self._fake_files())
        self.assertEqual(set(result), set(EXPECTED_BLOBS))
        for hook in HOOKS:
            self.assertEqual(result[hook.file].count(hook.tag), 1)

    def test_patch_idempotent(self):
        patched = plan_patches(self._fake_files())
        self.assertEqual(plan_patches(patched), {})

    def test_rejects_ambiguous_anchor(self):
        files = self._fake_files()
        target = HOOKS[0]
        files[target.file] += target.anchor
        with self.assertRaises(RuntimeError):
            plan_patches(files)

    def test_rejects_incomplete_patch(self):
        files = self._fake_files()
        path = "apps/composer/views.py"
        files[path] = files[path].replace(HOOKS[4].anchor, HOOKS[4].replacement, 1)
        with self.assertRaises(RuntimeError):
            plan_patches(files)

    def test_bulk_guard_precedes_state_mutation(self):
        hook = next(h for h in HOOKS if h.tag == "RISE_GUARD_CALENDAR_BULK")
        self.assertLess(hook.replacement.index("require_rise_publishable(pp)"),
                        hook.replacement.index('pp.transition_to("scheduled")'))

    def test_publisher_gate_precedes_outbound_dispatch(self):
        hook = next(h for h in HOOKS if h.tag == "RISE_GUARD_DISPATCH")
        self.assertIn("_fail_permanently", hook.replacement)
        self.assertIn("return {", hook.replacement)


class ExportValidationTests(unittest.TestCase):
    @staticmethod
    def valid(tables=None):
        return {"metadata": {"schema": "rise-wordpress-1.11-export-v1"},
                "tables": tables or {"records": [], "membership": [], "versions": [], "events": []},
                "counts": {}}

    def test_accepts_empty(self):
        self.assertTrue(audit(self.valid())["ok"])

    def test_secrets_rejected(self):
        d = self.valid({"records": [{"id": 1, "kind": "integrations", "payload": {"access_token": "secret"}}],
                        "membership": [], "versions": [], "events": []})
        self.assertFalse(audit(d)["ok"])

    def test_approvals_mismatch_is_warning(self):
        d = self.valid({"records": [{"id": 1, "kind": "clients"},
                                     {"id": 2, "kind": "content", "client_id": 1, "version": 1, "status": "published"}],
                        "membership": [], "versions": [], "events": []})
        a = audit(d)
        self.assertTrue(a["ok"])
        self.assertEqual(a["summary"]["approval_state_warnings"], 1)

    def test_mismatched_counts_rejected(self):
        d = self.valid()
        d["counts"]["records"] = 5
        self.assertFalse(audit(d)["ok"])


if __name__ == "__main__":
    unittest.main()
