"""Verify the two FigTree JARs against the provenance record.

``_figtree_patch/BUILD_PROVENANCE.md`` records a SHA-256 for both binaries in
the project: the stock FigTree 1.4.4 build used as an independent acceptance
oracle, and the patched build that ships inside the wheel. That record is the
only statement of where these two binaries came from.

Until now nothing checked it. The document was declarative: no test, no CI
step, and no build hook recomputed either hash, so a swapped, truncated or
corrupted JAR would have been installed, tested and published without a
single failure. These tests close that gap by deriving the expected values
*from the document itself* rather than restating them here, which means
editing the document is the only way to change what is accepted, and that
change shows up as a diff.
"""

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_DOC = REPO_ROOT / "_figtree_patch" / "BUILD_PROVENANCE.md"

STOCK_JAR = REPO_ROOT / "_figtree_patch" / "figtree_original.jar"
PATCHED_JAR = REPO_ROOT / "figtreekit" / "figtree_patched.jar"

# Rows of the provenance tables look like:
#   | File | `_figtree_patch/figtree_original.jar` |
#   | SHA-256 | `0d488f82...` |
# A row is bound to its File row by scanning the table body in order and
# remembering the most recent File cell, so the extraction survives edits to
# unrelated rows or to the surrounding prose.
_ROW_RE = re.compile(r"^\|(?P<body>.*)\|\s*$")
_FILE_RE = re.compile(r"File\s*\|\s*`(?P<path>[^`]+)`")
_SHA_RE = re.compile(r"SHA-256\s*\|\s*`(?P<sha>[0-9a-f]{64})`")


def _documented_hashes() -> dict:
    """Map every ``File`` path in the doc to the SHA-256 recorded next to it."""
    if not PROVENANCE_DOC.is_file():
        pytest.fail(f"provenance document is missing: {PROVENANCE_DOC}")

    hashes = {}
    current_file = None
    for line in PROVENANCE_DOC.read_text(encoding="utf-8").splitlines():
        row = _ROW_RE.match(line)
        if not row:
            continue
        body = row.group("body")
        file_match = _FILE_RE.search(body)
        if file_match:
            current_file = file_match.group("path").strip()
            continue
        sha_match = _SHA_RE.search(body)
        if sha_match and current_file:
            hashes[current_file] = sha_match.group("sha")
    return hashes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _recorded(path: str) -> str:
    """The SHA-256 the provenance document records for ``path``."""
    hashes = _documented_hashes()
    if path not in hashes:
        pytest.fail(
            f"BUILD_PROVENANCE.md records no SHA-256 for {path!r}; it records "
            f"one for {sorted(hashes) or 'nothing'}. The jar cannot be "
            "verified against a document that does not describe it."
        )
    return hashes[path]


class TestProvenanceDocument:
    """The provenance document itself must stay machine-readable."""

    def test_document_records_both_jars(self):
        hashes = _documented_hashes()
        documented = set(hashes)
        assert "_figtree_patch/figtree_original.jar" in documented, (
            "BUILD_PROVENANCE.md no longer documents the stock FigTree jar; "
            f"it documents {sorted(documented)}"
        )
        assert "figtreekit/figtree_patched.jar" in documented, (
            "BUILD_PROVENANCE.md no longer documents the patched FigTree jar; "
            f"it documents {sorted(documented)}"
        )

    def test_documented_hashes_are_well_formed(self):
        for path, sha in _documented_hashes().items():
            assert re.fullmatch(r"[0-9a-f]{64}", sha), f"{path}: {sha!r}"


class TestJarHashes:
    """The committed binaries must match the recorded hashes."""

    def test_stock_jar_matches_recorded_hash(self):
        recorded = _recorded("_figtree_patch/figtree_original.jar")
        assert STOCK_JAR.is_file(), f"stock jar is missing: {STOCK_JAR}"
        actual = _sha256(STOCK_JAR)
        assert actual == recorded, (
            f"{STOCK_JAR.relative_to(REPO_ROOT)} does not match the SHA-256 "
            f"recorded in BUILD_PROVENANCE.md.\n"
            f"  recorded: {recorded}\n"
            f"  actual:   {actual}\n"
            "If this is an intended change, rebuild the jar, update the "
            "document in the same commit, and say why in the PR description."
        )

    def test_patched_jar_matches_recorded_hash(self):
        recorded = _recorded("figtreekit/figtree_patched.jar")
        assert PATCHED_JAR.is_file(), f"patched jar is missing: {PATCHED_JAR}"
        actual = _sha256(PATCHED_JAR)
        assert actual == recorded, (
            f"{PATCHED_JAR.relative_to(REPO_ROOT)} does not match the SHA-256 "
            f"recorded in BUILD_PROVENANCE.md.\n"
            f"  recorded: {recorded}\n"
            f"  actual:   {actual}\n"
            "If this is an intended change, rebuild the jar, update the "
            "document in the same commit, and say why in the PR description."
        )

    def test_the_two_jars_differ(self):
        """A patched jar identical to stock would mean the patch never landed."""
        assert _sha256(STOCK_JAR) != _sha256(PATCHED_JAR)

    def test_patched_jar_is_shipped_in_the_package(self):
        """The wheel's package-data must actually contain the built jar."""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert 'figtreekit = ["figtree_patched.jar"]' in pyproject, (
            "pyproject.toml no longer declares figtree_patched.jar as "
            "package-data, so the renderer would ship without its binary"
        )
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        assert "recursive-include figtreekit *.py *.typed *.jar" in manifest, (
            "MANIFEST.in no longer includes *.jar under figtreekit/, so the "
            "patched jar would be missing from the sdist"
        )
