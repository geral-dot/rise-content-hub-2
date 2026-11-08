#!/usr/bin/env python3
"""Strict, dry-run-first BrightBean Studio overlay installer for RISE.

Only targets official BrightBean commit 1d11c520. Always validates git blob
SHA1 of each original source file, exact unique anchors, and all files BEFORE
writing any change. Stores .rise-backup copies, then atomic file replacement.
DOES NOT access accounts, databases, websites, APIs or media.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

PIN = "1d11c52007a3f714979ff1b071d153e69a8c274a"
EXPECTED_BLOBS = {
    "config/settings/base.py": "d357a9b8f2b6d900a4b37c12ee272fec85083787",
    "config/urls.py": "e41a8cf36c6341f43fafa6a517ac1ce5caba1155",
    "apps/composer/services.py": "702ece18d46d8398c68e97eb46f4b79da1bdde78",
    "apps/composer/views.py": "f390473ced3d3a79010ca33d1173e3aac20a5dc3",
    "apps/approvals/services.py": "99799c2c2c6c70003eb14732a83c6054fb18012b",
    "apps/publisher/engine.py": "7c8ce7b71013b70d2f3637d51ea00c144fb16471",
    "apps/calendar/views.py": "e83f12d1df7a6d46d7b399798d4ccd941f1caf8a",
}


@dataclass(frozen=True)
class Hook:
    file: str
    anchor: str
    replacement: str
    tag: str


def injected(file, anchor, fragment, tag):
    if tag not in fragment:
        raise ValueError("O marcador tem de estar no código adicionado")
    return Hook(file, anchor, anchor + fragment, tag)


HOOKS = [
    injected(
        "config/settings/base.py",
        '    "apps.client_portal",\n',
        '    "django_rise_agency.apps.RiseAgencyConfig",  # RISE_APP_REGISTERED\n',
        "RISE_APP_REGISTERED",
    ),
    injected(
        "config/urls.py",
        '    path("portal/", include("apps.client_portal.urls")),\n',
        '    path("rise/", include("django_rise_agency.urls")),  # RISE_URLS\n',
        "RISE_URLS",
    ),
    # Agent API: no new post can start in SCHEDULED before approval.
    injected(
        "apps/composer/services.py",
        '    if status == "scheduled":\n        _require_approval_gate_passes(workspace)\n',
        '        # RISE_GUARD_CREATE: newly created content needs client approvals first.\n'
        '        from django_rise_agency.services import rise_dual_approval_enabled\n'
        '        if rise_dual_approval_enabled(workspace.id):\n'
        '            raise ValueError("RISE: crie primeiro um rascunho e obtenha as duas aprovações")\n',
        "RISE_GUARD_CREATE",
    ),
    injected(
        "apps/composer/services.py",
        '        require_publishable(platform_post)\n',
        '        from django_rise_agency.services import require_rise_publishable\n'
        '        require_rise_publishable(platform_post)  # RISE_GUARD_SERVICE_SCHEDULE\n',
        "RISE_GUARD_SERVICE_SCHEDULE",
    ),
    # Composer UI: reject all schedule/queue actions BEFORE saving any editorial change.
    injected(
        "apps/composer/views.py",
        '    if not post_id:\n        post.author = request.user\n',
        '    # RISE_GUARD_COMPOSER: pending approvals never enter scheduled queues.\n'
        '    if action in {"schedule", "publish_now", "add_to_queue", "add_to_queue_priority"}:\n'
        '        from django_rise_agency.services import rise_dual_approval_enabled, require_rise_post_approved\n'
        '        if rise_dual_approval_enabled(workspace.id):\n'
        '            if not post_id:\n'
        '                return JsonResponse({"errors": {"approval": "RISE: guarde como rascunho e solicite aprovação"}}, status=409)\n'
        '            try:\n'
        '                require_rise_post_approved(post)\n'
        '            except ValueError as exc:\n'
        '                return JsonResponse({"errors": {"approval": str(exc)}}, status=409)\n',
        "RISE_GUARD_COMPOSER",
    ),
    injected(
        "apps/composer/views.py",
        '            require_publishable(pp)\n        except ValueError as exc:\n',
        # Replaced after HOOKS construction to keep the try/except boundary.
        '        # RISE_GUARD_ACCOUNT_SCHEDULE\n',
        "RISE_GUARD_ACCOUNT_SCHEDULE",
    ),
    # CSV import: scheduling imported rows is blocked; preserve proposed slot.
    injected(
        "apps/composer/views.py",
        '                    initial_pp_status = "scheduled"\n',
        '                    # RISE_GUARD_CSV: imports never bypass client approval.\n'
        '                    from django_rise_agency.services import rise_dual_approval_enabled\n'
        '                    if rise_dual_approval_enabled(workspace.id):\n'
        '                        post.proposed_publish_at = post.scheduled_at\n'
        '                        post.scheduled_at = None\n'
        '                        initial_pp_status = "draft"\n',
        "RISE_GUARD_CSV",
    ),
    # Native workflow: final client approval requires RISE component approvals.
    injected(
        "apps/approvals/services.py",
        '    two_stage = workspace.approval_workflow_mode == "required_internal_and_client"\n',
        '    # RISE_GUARD_NATIVE_APPROVE: allow internal pass but gate final sign-off.\n'
        '    if not two_stage or any(pp.status != "pending_review" for pp in targets):\n'
        '        from django_rise_agency.services import require_rise_post_approved\n'
        '        require_rise_post_approved(post)\n',
        "RISE_GUARD_NATIVE_APPROVE",
    ),
    # Definitive failure-closed guard before provider dispatch.
    injected(
        "apps/publisher/engine.py",
        '        start_time = time.monotonic()\n'
        '        account = platform_post.social_account\n',
        '        # RISE_GUARD_DISPATCH: last check before attempting external API.\n'
        '        from django_rise_agency.services import require_rise_publishable\n'
        '        try:\n'
        '            require_rise_publishable(platform_post)\n'
        '        except ValueError as exc:\n'
        '            self._fail_permanently(\n'
        '                platform_post, str(exc),\n'
        '                user_message="RISE: publicação bloqueada até nova aprovação de texto e imagem.",\n'
        '                reason="rise-approval-gate",\n'
        '            )\n'
        '            return {"success": False, "error": "RISE: aprovação pendente"}\n',
        "RISE_GUARD_DISPATCH",
    ),
    injected(
        "apps/calendar/views.py",
        '            require_publishable(pp)\n',
        '            from django_rise_agency.services import require_rise_publishable\n'
        '            require_rise_publishable(pp)  # RISE_GUARD_CALENDAR_DRAG\n',
        "RISE_GUARD_CALENDAR_DRAG",
    ),
    injected(
        "apps/calendar/views.py",
        '                if pp.status != "scheduled":\n                    pp.transition_to("scheduled")\n',
        '                # RISE_GUARD_CALENDAR_BULK: all accounts require approval.\n'
        '                from django_rise_agency.services import require_rise_publishable\n'
        '                require_rise_publishable(pp)\n',
        "RISE_GUARD_CALENDAR_BULK",
    ),
]

# The bulk calendar hook must execute BEFORE status transitions (not after).
HOOKS[-1] = Hook(
    "apps/calendar/views.py",
    '                if pp.status != "scheduled":\n                    pp.transition_to("scheduled")\n',
    '                # RISE_GUARD_CALENDAR_BULK: approve before changing any state.\n'
    '                from django_rise_agency.services import require_rise_publishable\n'
    '                require_rise_publishable(pp)\n'
    '                if pp.status != "scheduled":\n                    pp.transition_to("scheduled")\n',
    "RISE_GUARD_CALENDAR_BULK",
)

# Special hook: the call occurs inside a try block, and must stay inside it.
HOOKS[5] = Hook(
    "apps/composer/views.py",
    '            require_publishable(pp)\n        except ValueError as exc:\n',
    '            require_publishable(pp)\n'
    '            from django_rise_agency.services import require_rise_publishable\n'
    '            require_rise_publishable(pp)  # RISE_GUARD_ACCOUNT_SCHEDULE\n'
    '        except ValueError as exc:\n',
    "RISE_GUARD_ACCOUNT_SCHEDULE",
)


def plan_patches(content_by_file):
    """Pure function: returns new source code; refuses partially patched files."""
    by_file = {}
    for hook in HOOKS:
        by_file.setdefault(hook.file, []).append(hook)
    edits = {}
    for name, hooks in by_file.items():
        if name not in content_by_file:
            raise RuntimeError(f"Falta o ficheiro original {name}")
        content = content_by_file[name]
        tags = [h.tag in content for h in hooks]
        if all(tags):
            continue  # already fully patched; idempotent
        if any(tags):
            raise RuntimeError(f"Integração parcial em {name}; rever antes de continuar")
        for h in hooks:
            if content.count(h.anchor) != 1:
                raise RuntimeError(f"Âncora incompatível/ambígua em {name}, {h.tag}: {content.count(h.anchor)}")
            content = content.replace(h.anchor, h.replacement, 1)
        edits[name] = content
    return edits


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE).strip()


def apply(root, write=False):
    root = Path(root).resolve()
    if _git(root, "rev-parse", "HEAD") != PIN:
        raise RuntimeError("É necessário checkout exato do BrightBean commit " + PIN)
    content_by_file = {}
    for name in EXPECTED_BLOBS:
        p = root / name
        if not p.is_file():
            raise RuntimeError("Ficheiro original ausente: " + name)
        content_by_file[name] = p.read_text(encoding="utf-8")

    edits = plan_patches(content_by_file)
    for name in edits:
        sha = _git(root, "hash-object", name)
        if sha != EXPECTED_BLOBS[name]:
            raise RuntimeError(f"Fonte de {name} diferente da versão auditada: {sha}")
        if (root / (name + ".rise-backup")).exists():
            raise RuntimeError(f"Backup antigo já existe para {name}; exige revisão")
    if not edits:
        print("Integração já aplicada em todos os ficheiros; não há alterações.")
        return []
    if not write:
        print("Pré-validação aceite. Ficheiros a modificar:")
        for name in edits:
            print(" -", name)
        return list(edits)
    # Preserve everything before writing any source file. No database/schema
    # operations are run by this installer.
    written = []
    try:
        for name in edits:
            f = root / name
            backup = root / (name + ".rise-backup")
            with backup.open("xb") as out:
                out.write(f.read_bytes())
        for name, modified in edits.items():
            f = root / name
            fd, temp = tempfile.mkstemp(prefix=".rise-", dir=str(f.parent), text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
                    out.write(modified)
                os.chmod(temp, f.stat().st_mode)
                os.replace(temp, f)
                written.append(name)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
    except Exception:
        for name in written:
            (root / name).write_bytes((root / (name + ".rise-backup")).read_bytes())
        raise
    print("Overlay RISE aplicado aos seguintes ficheiros:")
    for name in written:
        print(" -", name)
    print("Ainda é obrigatório executar check/migrate/testes upstream no ambiente Django.")
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brightbean_checkout", type=Path)
    parser.add_argument("--write", action="store_true", help="Aplicar patches; por defeito apenas validar")
    args = parser.parse_args()
    apply(args.brightbean_checkout, write=args.write)
