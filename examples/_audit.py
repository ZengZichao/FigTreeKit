"""Machine-readable audit dumps for the two archived example workflows.

Per-clade verdicts and annotation accounting have to be inspectable after the
run, not only printed, so the workflows emit these files alongside their
outputs.

Two artefacts are written next to the workflow outputs:

``<prefix>_audit.json``
    aggregate counts (groups assessed, exclusive, non-exclusive, unmapped,
    tips), the completeness-audit result, the annotation counts written into
    the exported NEXUS, and the environment stamp.

``<prefix>_groups.csv``
    one row per assessed taxonomic group: name, tip count, verdict, the
    intruder/unmapped taxa that caused a refusal, and the assigned colour.
"""
from __future__ import annotations

import ast
import csv
import json
import re
import platform
from datetime import datetime, timezone
from pathlib import Path


def environment_stamp() -> dict:
    import figtreekit
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "figtreekit_version": getattr(figtreekit, "__version__", "unknown"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def count_written_annotations(nexus_path: Path) -> dict:
    """Count the FigTree annotations actually present in the exported NEXUS."""
    text = Path(nexus_path).read_text(encoding="utf-8", errors="ignore")
    return {
        "!color": text.count("!color="),
        "!hilight": text.count("!hilight="),
        "!font": text.count("!font="),
        "!stroke": text.count("!stroke="),
        "!collapse": text.count("!collapse="),
        "!cartoon": text.count("!cartoon="),
    }


def write_audit(prefix: Path, *, rank: str, groups: dict, completeness: dict,
                nexus_path: Path, collapsed=None,
                extra: dict | None = None) -> dict:
    """Write ``<prefix>_audit.json`` and ``<prefix>_groups.csv``.

    *collapsed* is the collection of group names the workflow actually
    submitted for collapse.  Pass an empty collection for a colour-only
    workflow; omit it (None) only when the distinction is not meaningful.
    """
    collapsed_set = None if collapsed is None else {str(c) for c in collapsed}
    mono = groups.get("monophyletic", {}) or {}
    nonmono = groups.get("non_monophyletic", {}) or {}
    unmapped = groups.get("unmapped", {}) or {}
    summary = groups.get("summary", {}) or {}
    intruders_by_group = _intruders_from_warnings(groups.get("analyzer_warnings", []) or [])

    def items(container):
        if isinstance(container, dict):
            return sorted(container.items())
        return [(str(v), {}) for v in sorted(container)]

    rows = []
    for name, info in items(mono):
        rows.append(_group_row(name, "exclusive", info, accepted=True,
                               collapsed=collapsed_set))
    for name, info in items(nonmono):
        rows.append(_group_row(name, "non-exclusive", info, accepted=False, collapsed=collapsed_set,
                               intruders=intruders_by_group.get(name, [])))
    for name, info in items(unmapped):
        rows.append(_group_row(name, "unmapped", info, accepted=False, collapsed=collapsed_set))

    csv_path = Path(f"{prefix}_groups.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = ["rank", "group", "tip_count", "verdict", "collapse_applied",
                      "intruder_taxa", "unmapped_tips_in_mrca", "colour"]
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    written = count_written_annotations(nexus_path)
    exclusive_rows = [r for r in rows if r["verdict"] == "exclusive"]
    payload = {
        "workflow": str(extra.get("workflow_script", "")) if extra else "",
        "rank": rank,
        "environment": environment_stamp(),
        "completeness_audit": {
            k: v for k, v in (completeness or {}).items()
            if isinstance(v, (int, float, str, bool)) or k == "rank_coverage"
        },
        "groups_assessed": summary.get("total_groups", len(mono) + len(nonmono)),
        "single_taxon_groups": summary.get("single_taxon_groups"),
        "multi_tip_groups": summary.get("multi_tip_groups"),
        "multi_tip_monophyletic": summary.get("multi_tip_monophyletic"),
        "monophyly_rate_percent": round(float(summary.get("monophyly_rate", 0.0)), 2),
        "groups_exclusive": len(mono),
        "groups_non_exclusive": len(nonmono),
        "groups_unmapped": len(unmapped),
        "multi_tip_exclusive_groups": sum(1 for r in exclusive_rows
                                          if r["tip_count"] > 1),
        "singleton_exclusive_groups": sum(1 for r in exclusive_rows
                                          if r["tip_count"] == 1),
        "collapse_requested": (None if collapsed_set is None else len(collapsed_set)),
        "annotations_written_to_nexus": written,
        "nexus_path": _rel(nexus_path),
        "per_group_csv": _rel(csv_path),
        "note": (
            "groups_assessed counts taxa mapped at this rank. collapse_applied means "
            "the workflow submitted that group for collapse, which is narrower than "
            "the monophyly verdict: single-taxon groups are trivially exclusive, and "
            "the styler skips a collapse whose MRCA has no children, so they are "
            "reported as exclusive but not collapsed. annotations_written_to_nexus is "
            "counted from the exported NEXUS, not from the verdicts, so "
            "collapse_requested and !collapse can be compared directly."
        ),
    }
    if extra:
        payload.update(extra)
    if collapsed_set is not None:
        mismatch = written["!collapse"] - len(collapsed_set)
        payload["collapse_annotation_difference"] = mismatch
        if mismatch:
            print(f"[audit] WARNING {abs(mismatch)} group(s) submitted for collapse "
                  f"produced no !collapse annotation (requested {len(collapsed_set)}, "
                  f"written {written['!collapse']}); a group whose single tip is "
                  f"already inside an earlier collapse can resolve to an unintended "
                  f"node, so this difference must be explained, not ignored")
    json_path = Path(f"{prefix}_audit.json")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"[audit] wrote {json_path} and {csv_path}")
    return payload


def _as_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _intruders_from_warnings(warnings) -> dict:
    """Map group name -> intruder taxa from the analyzer warning strings."""
    out = {}
    for w in warnings:
        m = re.match(r"Group \'?([^\']+?)\'? is not monophyletic\. Intruders: (\[.*\])", str(w))
        if m:
            try:
                out[m.group(1)] = ast.literal_eval(m.group(2))
            except Exception:
                out[m.group(1)] = [m.group(2)]
    return out


def _rel(path) -> str:
    """Record artefacts by name, not by this machine's absolute path."""
    try:
        return Path(path).name
    except Exception:
        return str(path)


def group_tip_count(info) -> int:
    """Number of mapped tips a group covers, as the analyzer reported it."""
    d = info if isinstance(info, dict) else {}
    tips = (d.get("tips") or d.get("tip_count") or d.get("n_tips")
            or d.get("clade_size") or d.get("taxa") or d.get("members"))
    if isinstance(tips, (list, set, tuple)):
        return len(tips)
    if isinstance(tips, (int, float, str)) and str(tips).strip() != "":
        return _as_int(tips, 0)
    return 0


def _group_row(name: str, verdict: str, info, accepted: bool, intruders=None,
               collapsed=None) -> dict:
    d = info if isinstance(info, dict) else {}
    tip_count = group_tip_count(info)
    if intruders is None:
        intruders = (d.get("intruders") or d.get("intruder_taxa")
                     or d.get("extra_taxa") or [])
    unmapped_in = d.get("unmapped_in_mrca") or d.get("unmapped") or []
    return {
        "group": name,
        "tip_count": tip_count,
        "verdict": verdict,
        # "was a collapse actually requested for this group" -- NOT "did the
        # monophyly test pass".  A group can be exclusive and still be left
        # expanded (single-taxon groups, or a colour-only workflow), and the
        # exported NEXUS is the arbiter.
        "collapse_applied": "yes" if (collapsed is not None
                                      and name in collapsed) else "no",
        "intruder_taxa": ";".join(map(str, intruders)) if isinstance(intruders, (list, tuple, set)) else str(intruders or ""),
        "unmapped_tips_in_mrca": ";".join(map(str, unmapped_in)) if isinstance(unmapped_in, (list, tuple, set)) else str(unmapped_in or ""),
        "colour": d.get("colour") or d.get("color") or "",
    }
