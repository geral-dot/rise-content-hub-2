#!/usr/bin/env python3
"""Audit a RISE WordPress 1.11 JSON export without changing any target DB.
Usage: python validate_export.py /path/rise-legacy.json [--report report.json]
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

SENSITIVE = ("password", "passwd", "secret", "token", "api_key", "apikey", "client_secret", "credential", "authorization", "auth_code")
REQUIRED_TABLES = ("records", "membership", "versions", "events")


def audit(data):
    errors, warnings = [], []
    if data.get("metadata", {}).get("schema") != "rise-wordpress-1.11-export-v1":
        errors.append("Esquema de exportação desconhecido.")
    tables = data.get("tables", {})
    for name in REQUIRED_TABLES:
        if name not in tables:
            errors.append(f"Falta a tabela obrigatória: {name}.")
    records = tables.get("records", [])
    seen = set()
    types = Counter()
    clients = set()
    contents = {}
    for record in records:
        rid = int(record.get("id", -1))
        if rid in seen:
            errors.append(f"ID de registo duplicado: {rid}.")
        seen.add(rid)
        kind = record.get("kind")
        types[kind] += 1
        if kind == "clients":
            clients.add(rid)
        if kind == "content":
            contents[rid] = record
        if kind == "integrations":
            errors.append("A exportação inclui um registo de integração potencialmente sensível.")
    for record in records:
        if record.get("kind") not in ("clients", "integrations"):
            cid = int(record.get("client_id") or 0)
            if cid not in clients:
                warnings.append(f"Registo {record.get('id')} sem cliente existente (ID {cid}).")
    versions_by_content = defaultdict(set)
    for v in tables.get("versions", []):
        cid, version = int(v.get("content_id") or 0), int(v.get("version") or 0)
        if cid not in contents:
            warnings.append(f"Versão órfã para conteúdo {cid}.")
        if version in versions_by_content[cid]:
            errors.append(f"Versão duplicada: conteúdo {cid}, versão {version}.")
        versions_by_content[cid].add(version)
    events = defaultdict(list)
    for ev in tables.get("events", []):
        rid = int(ev.get("content_id") or 0)
        if rid and rid not in contents:
            warnings.append(f"Evento {ev.get('id')} refere conteúdo inexistente {rid}.")
        if ev.get("event_type") in ("component_approve", "component_changes"):
            events[(rid, int(ev.get("version") or 0))].append(ev)
    pending = published = dual_mismatch = 0
    for rid, post in contents.items():
        status = post.get("status")
        pending += status in ("pending", "review")
        published += status == "published"
        parts = {"visual": False, "copy": False}
        for ev in sorted(events[(rid, int(post.get("version") or 0))], key=lambda r: int(r.get("id") or 0)):
            d = ev.get("detail") or {}
            if isinstance(d, dict) and d.get("component") in parts:
                parts[d["component"]] = ev.get("event_type") == "component_approve"
        if status in ("approved", "scheduled", "published") and not all(parts.values()):
            dual_mismatch += 1
            warnings.append(f"Conteúdo {rid} com estado {status}, mas sem ambas as aprovações registadas na versão atual.")
    # Check keys, not freeform text; text may legitimately mention the terms.
    def check_keys(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(x in k.lower() for x in SENSITIVE):
                    errors.append(f"Possível segredo numa chave exportada: {path}/{k}")
                else:
                    check_keys(v, f"{path}/{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_keys(v, f"{path}/{i}")
    check_keys(tables)
    counts_declared = data.get("counts", {})
    for table, rows in tables.items():
        if table in counts_declared and len(rows) != counts_declared[table]:
            errors.append(f"Contagem incongruente em {table}.")
    return {
        "ok": not errors,
        "summary": {
            "records": len(records),
            "clients": len(clients),
            "contents": len(contents),
            "published": published,
            "pending_review": pending,
            "approval_state_warnings": dual_mismatch,
            "other_types": dict(types),
            "tables": {k: len(v) for k, v in tables.items()},
        },
        "errors": errors[:100], "warnings": warnings[:200],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("export", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    with args.export.open(encoding="utf-8") as f:
        results = audit(json.load(f))
    output = json.dumps(results, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output)
    raise SystemExit(0 if results["ok"] else 2)


if __name__ == "__main__":
    main()
