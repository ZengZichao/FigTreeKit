# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Newick and Nexus parsing utilities."""

# Copyright (C) 2024-2026 Zeng Zichao
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import re
import warnings
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import CompatibilityWarning, ParseError

__all__ = [
    "find_unquoted_semicolon",
    "extract_tree_value",
    "extract_trees_block_content",
    "find_tree_declaration_spans",
    "parse_nexus_content",
    "extract_taxa_from_newick",
    "apply_parsed_setting",
    "load_existing_figtree_block",
    "extract_bracket_comments",
    "reinsert_bracket_comments",
]


def find_unquoted_semicolon(content: str) -> int:
    """Find the position of a semicolon not inside single quotes.

    Handles doubled-quote escaping (``''``) per Nexus specification.

    Returns:
        Index of the semicolon, or ``-1`` if not found.
    """
    in_quote = False
    i = 0
    while i < len(content):
        char = content[i]
        if char == "'":
            if i + 1 < len(content) and content[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
        elif char == ';' and not in_quote:
            return i
        i += 1
    return -1


def extract_tree_value(content: str) -> Optional[str]:
    """Extract the Newick tree value from a ``tree NAME = <value>;`` declaration.

    Handles semicolons inside ``[...]`` metadata brackets and quoted strings.

    Returns:
        The tree string (without trailing semicolon), or ``None`` if not found.
    """
    bracket_depth = 0
    in_quote = False
    i = 0
    last_semicolon = -1

    while i < len(content):
        char = content[i]
        if char == "'" and not in_quote:
            in_quote = True
        elif char == "'" and in_quote:
            if i + 1 < len(content) and content[i + 1] == "'":
                i += 1
            else:
                in_quote = False
        elif char == '[' and not in_quote:
            bracket_depth += 1
        elif char == ']' and not in_quote and bracket_depth > 0:
            bracket_depth -= 1
        elif char == ';' and not in_quote and bracket_depth == 0:
            last_semicolon = i
            break
        i += 1

    if last_semicolon != -1:
        return content[:last_semicolon]
    return None


def extract_trees_block_content(trees_block: str) -> str:
    """Extract content between ``begin trees;`` and ``end;`` markers."""
    content = trees_block.strip()
    # Remove begin trees; prefix
    content = re.sub(r'^\s*begin\s+trees\s*;', '', content, flags=re.IGNORECASE).strip()
    # Remove end; suffix
    content = re.sub(r'\bend\s*;\s*$', '', content, flags=re.IGNORECASE).strip()
    return content


_TREE_NAME_PATTERN = re.compile(
    r"tree\s+(?:'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|\S+)\s*=\s*",
    re.IGNORECASE,
)


def find_tree_declaration_spans(trees_content: str) -> List[Tuple[int, int]]:
    """Locate every ``tree NAME = <newick>;`` declaration via a character scan.

    Instead of a regular expression, this uses an explicit scanner that
    tracks three pieces of state while walking the trees block:

    * **quote state** — single or double quotes (with doubled-quote ``''`` /
      ``""`` escaping per the Nexus specification), so a semicolon inside a
      quoted tree name does not terminate the declaration;
    * **bracket-comment depth** — a parenthesis-style depth counter for
      ``[...]`` comments at arbitrary nesting depth, so a semicolon inside a
      BEAST metadata comment does not terminate the declaration;
    * **tree-delimiting semicolons** — only a ``;`` outside both quotes and
      comments ends a tree declaration.

    Args:
        trees_content: The raw content of a Nexus ``begin trees; ... end;``
            block (with or without the begin/end markers).

    Returns:
        A list of ``(start, end)`` spans (end exclusive) covering each full
        tree declaration including its trailing semicolon, in file order.
    """
    spans: List[Tuple[int, int]] = []
    n = len(trees_content)
    search_from = 0
    while True:
        decl = _TREE_NAME_PATTERN.search(trees_content, search_from)
        if decl is None:
            break
        j = decl.end()
        in_quote: Optional[str] = None
        bracket_depth = 0
        while j < n:
            char = trees_content[j]
            if in_quote is not None:
                if char == in_quote:
                    # Doubled quote escape ('' or "") stays inside the quote.
                    if j + 1 < n and trees_content[j + 1] == in_quote:
                        j += 2
                        continue
                    in_quote = None
            elif char in ("'", '"'):
                in_quote = char
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                if bracket_depth > 0:
                    bracket_depth -= 1
            elif char == ';' and bracket_depth == 0:
                break
            j += 1
        if j >= n:
            # Unterminated declaration: take the remainder of the block.
            spans.append((decl.start(), n))
            break
        spans.append((decl.start(), j + 1))
        search_from = j + 1
    return spans


def parse_nexus_content(content: str, tree_index: int = 0) -> Dict[str, Any]:
    """Parse Nexus format content and extract blocks.

    Args:
        content: Nexus format content string.
        tree_index: Index of the tree to process (0-based). Default is 0 (first tree).

    Returns:
        Dictionary with keys: ``taxa_block``, ``tree_block``, ``translate_block``,
        ``tree_content``, ``all_trees``, ``figtree_block``.
    """
    result: Dict[str, Any] = {
        'taxa_block': None,
        'tree_block': None,
        'translate_block': None,
        'tree_content': None,
        'all_trees': [],
        'figtree_block': None,
    }

    # Use re.IGNORECASE on original content so match positions are correct
    taxa_match = re.search(r'\bbegin\s+taxa\s*;(.*?)\bend\s*;', content, re.DOTALL | re.IGNORECASE)
    if taxa_match:
        result['taxa_block'] = content[taxa_match.start():taxa_match.end()]

    trees_match = re.search(r'\bbegin\s+trees\s*;(.*?)\bend\s*;', content, re.DOTALL | re.IGNORECASE)
    if not trees_match:
        return result

    result['tree_block'] = content[trees_match.start():trees_match.end()]
    tree_block = result['tree_block']

    # Extract translate block
    translate_match = re.search(
        r'\btranslate\s+(.+?)(?=;tree\b|;end\b|;)', tree_block, re.DOTALL | re.IGNORECASE
    )
    if translate_match:
        translate_start = tree_block.lower().find('translate')
        translate_content = tree_block[translate_start:]
        translate_end = find_unquoted_semicolon(translate_content)
        if translate_end != -1:
            result['translate_block'] = translate_content[:translate_end + 1]

    # Extract ALL tree declarations with their full content
    all_tree_matches = list(re.finditer(
        r'tree\s+(\S+)\s*=\s*', tree_block, re.DOTALL | re.IGNORECASE
    ))
    result['all_trees'] = [m.group(0) for m in all_tree_matches]

    if all_tree_matches:
        # Validate tree_index
        if tree_index < 0 or tree_index >= len(all_tree_matches):
            warnings.warn(
                f"tree_index={tree_index} is out of range (0-{len(all_tree_matches)-1}). "
                f"Using first tree (index 0).",
                CompatibilityWarning,
            )
            tree_index = 0

        # Extract specified tree value
        selected_match = all_tree_matches[tree_index]
        tree_start = selected_match.end()
        tree_value = extract_tree_value(tree_block[tree_start:])
        result['tree_content'] = tree_value.strip() if tree_value else None

        if len(all_tree_matches) > 1:
            warnings.warn(
                f"Multiple trees detected ({len(all_tree_matches)}). "
                f"Processing tree at index {tree_index}. "
                f"All trees will be preserved in output.",
                CompatibilityWarning,
            )

    # Extract existing figtree block
    figtree_match = re.search(r'\bbegin\s+figtree\s*;(.*?)\bend\s*;', content, re.DOTALL | re.IGNORECASE)
    if figtree_match:
        result['figtree_block'] = content[figtree_match.start():figtree_match.end()]

    return result


# ── Square-bracket comment stripping ────────────────────────────────────
# NHX / bootstrap / posterior annotations use ``[...]`` comments.  A regex
# pattern handles only a fixed nesting depth, so the project standard is
# this depth-tracking scan, which removes balanced pairs at *any* depth.
# This is the single canonical implementation — callers must use it instead
# of inlining ad-hoc variants, otherwise behaviour drifts between modules.
def strip_square_bracket_comments(text: str) -> str:
    """Remove square-bracket comments from a tree/label string.

    Handles arbitrarily nested brackets correctly (e.g. ``[a[b]c]``).
    Returns *text* unchanged if there are no bracket comments.
    """
    if '[' not in text:
        return text
    result: List[str] = []
    depth = 0
    for ch in text:
        if ch == '[':
            depth += 1
        elif ch == ']':
            if depth > 0:
                depth -= 1
            else:
                result.append(ch)
        elif depth == 0:
            result.append(ch)
    return ''.join(result)


def extract_taxa_from_newick(tree_content: str) -> List[str]:
    """Extract terminal taxa names from a Newick string using Bio.Phylo.

    Falls back to regex-based extraction if Bio.Phylo is unavailable or fails.

    Returns:
        List of unique taxa names (terminal nodes only).
    """
    try:
        from Bio import Phylo
        import io

        content = strip_square_bracket_comments(tree_content)
        trees = list(Phylo.parse(io.StringIO(content), 'newick'))
        if not trees:
            warnings.warn(
                "Bio.Phylo returned no trees, falling back to regex-based "
                "taxa extraction. Results may differ.",
                CompatibilityWarning,
            )
            return _fallback_extract_taxa(content)

        taxa: List[str] = []
        seen: set = set()

        for clade in trees[0].get_terminals():
            name = clade.name
            if name and name not in seen:
                if re.match(r'^\d*\.\d+$', name):
                    continue
                if ' ' in name or "'" in name or ';' in name:
                    escaped_name = name.replace("'", "''")
                    taxa.append(f"'{escaped_name}'")
                else:
                    taxa.append(name)
                seen.add(name)

        return taxa

    except Exception as e:
        warnings.warn(
            f"Bio.Phylo parsing failed ({type(e).__name__}: {e}), "
            f"falling back to regex-based taxa extraction. Results may differ.",
            CompatibilityWarning,
        )
        return _fallback_extract_taxa(tree_content)


def _fallback_extract_taxa(content: str) -> List[str]:
    """Regex-based fallback for taxa extraction from Newick strings.

    Handles:
    - Doubled-quote escaping ('') in taxon names
    - Taxa at the root of a tree (not just after '(' or ',')
    - Numeric-only taxon names (common in BEAST output)
    - Taxa starting with digits (e.g., '9606_Taxon_001')
    - Filters float-like names (e.g., '0.5') that are likely branch lengths
    """
    content = strip_square_bracket_comments(content)
    taxa: List[str] = []
    seen: set = set()

    # Quoted names - handle doubled-quote escaping ('')
    # Match quoted strings, handling '' as escaped quote
    i = 0
    while i < len(content):
        if content[i] == "'":
            # Start of quoted string
            j = i + 1
            name_chars = []
            while j < len(content):
                if content[j] == "'":
                    # Check for doubled quote
                    if j + 1 < len(content) and content[j + 1] == "'":
                        name_chars.append("'")
                        j += 2
                        continue
                    else:
                        # End of quoted string
                        break
                else:
                    name_chars.append(content[j])
                j += 1
            
            if j < len(content):  # Found closing quote
                name = ''.join(name_chars)
                if name and name not in seen:
                    # Don't filter numeric names - they're valid taxa
                    escaped_name = name.replace("'", "''")
                    taxa.append(f"'{escaped_name}'")
                    seen.add(name)
            i = j + 1
        else:
            i += 1

    # Unquoted taxa names - match after '(', ',', or at start of string
    # Also handle numeric names and names starting with digits
    pattern = r'(?:^|[\(,])\s*([^\(\)\[\]\:\,\s]+)(?=\s*[\:\),;])'
    for match in re.finditer(pattern, content):
        name = match.group(1)
        if name.startswith("'"):
            continue
        if name and name not in seen:
            # Filter float-like names (e.g., '0.5') that are likely branch lengths
            # But allow pure integer names (e.g., '1', '2') common in BEAST output
            if re.match(r'^\d*\.\d+$', name):
                continue
            taxa.append(name)
            seen.add(name)

    return taxa


def apply_parsed_setting(settings: Any, key: str, value: str) -> None:
    """Apply a single parsed setting from an existing figtree block.

    Modifies ``settings`` in place.
    """
    value = value.strip()

    parsed_value: Any = value
    if value.lower() in ('true', 'false'):
        parsed_value = value.lower() == 'true'
    elif value == 'null':
        parsed_value = None
    elif value.startswith('"') and value.endswith('"'):
        # Unescape backslash-escaped characters (reverse of serialize_value)
        inner = value[1:-1]
        parsed_value = (
            inner
            .replace('\\\\', '\x00')  # \\ → sentinel
            .replace('\\"', '"')       # \" → "
            .replace('\x00', '\\')     # sentinel → \
        )
    elif value.startswith('#'):
        parsed_value = value
    else:
        try:
            if '.' in value or 'e' in value.lower():
                parsed_value = float(value)
            else:
                parsed_value = int(value)
        except ValueError:
            parsed_value = value

    # Delegate to the public FigTreeSettings.set() API rather than mutating
    # __dict__ directly; it routes the value to the right category dict (or
    # to _custom when the category is unknown).
    settings.set(key, parsed_value)


def load_existing_figtree_block(settings: Any, figtree_block: str) -> None:
    """Load existing figtree settings from a parsed block into ``settings``."""
    for line in figtree_block.split('\n'):
        line = line.strip()
        if not line or line.startswith('begin figtree') or line.startswith('end;'):
            continue
        for match in re.finditer(r'set\s+([^=]+?)\s*=\s*([^;]+);', line):
            apply_parsed_setting(settings, match.group(1).strip(), match.group(2).strip())


# ── Bracket-comment preservation (moved from styler.py) ─────────────────
# Newick bracket comments ([&posterior=0.95], NHX, etc.) are stripped by
# Bio.Phylo during parsing. These two functions extract comments with their
# attachment points before parsing and re-insert them after serialization,
# so BEAST metadata survives the round trip.

def extract_bracket_comments(newick: str) -> List[Dict[str, Any]]:
    """Extract bracket comments from a Newick string, preserving their positions.

    Returns a list of dicts with keys: 'taxon_name', 'comment', 'position_type'
    where position_type is one of 'after_name', 'after_branch_length',
    'after_internal_node' (comment directly follows ``)``), or 'unattached'
    (e.g. a root attribute such as ``[&R]`` before the first parenthesis).
    """
    comments = []
    # Pattern to match taxon names followed by bracket comments
    # Matches: 'Taxon Name'[&comment] or TaxonName[&comment]
    # Also matches: :0.123[&comment] (after branch length)

    # First, find all bracket comments with their positions
    i = 0
    in_quote = None  # None, "'", or '"'
    current_name = ''
    last_name = ''
    last_branch_length = ''
    after_close_paren = False

    while i < len(newick):
        char = newick[i]

        if char in ("'", '"') and in_quote is None:
            in_quote = char
            current_name += char
        elif char == "'" and in_quote == "'":
            if i + 1 < len(newick) and newick[i + 1] == "'":
                current_name += "''"
                i += 2
                continue
            else:
                in_quote = None
                current_name += char
        elif char == '"' and in_quote == '"':
            if i + 1 < len(newick) and newick[i + 1] == '"':
                current_name += '""'
                i += 2
                continue
            else:
                in_quote = None
                current_name += char
        elif char == '[' and in_quote is None:
            # Start of bracket comment
            bracket_start = i
            depth = 1
            i += 1
            while i < len(newick) and depth > 0:
                if newick[i] == '[':
                    depth += 1
                elif newick[i] == ']':
                    depth -= 1
                i += 1
            bracket_comment = newick[bracket_start:i]

            # Determine what this comment is attached to
            if current_name.strip():
                # Attached to a taxon name
                name = current_name.strip().strip("'").strip('"')
                comments.append({
                    'taxon_name': name,
                    'comment': bracket_comment,
                    'position_type': 'after_name'
                })
                last_name = name
            elif last_branch_length:
                # Attached to a branch length
                comments.append({
                    'taxon_name': None,
                    'comment': bracket_comment,
                    'position_type': 'after_branch_length',
                    'branch_length': last_branch_length
                })
            elif after_close_paren:
                # Attached to an internal node (follows ')').  Recorded so
                # that the caller can warn — this position cannot currently
                # be re-inserted reliably.
                comments.append({
                    'taxon_name': None,
                    'comment': bracket_comment,
                    'position_type': 'after_internal_node',
                })
            else:
                # Root-level/block attribute (e.g. '[&R]' before the first
                # parenthesis) or otherwise unattached.
                comments.append({
                    'taxon_name': None,
                    'comment': bracket_comment,
                    'position_type': 'unattached',
                })

            current_name = ''
            last_branch_length = ''
            after_close_paren = False
            continue
        elif char == ':':
            # Branch length follows
            i += 1
            bl_start = i
            while i < len(newick) and newick[i] not in '(),;[':
                i += 1
            last_branch_length = newick[bl_start:i]
            current_name = ''
            after_close_paren = False
            continue
        elif char in '(),;':
            # Reset tracking; ')' marks a potential internal-node attachment
            # point for a following bracket comment.
            after_close_paren = (char == ')')
            current_name = ''
            last_branch_length = ''
            last_name = ''
        else:
            if in_quote is None and char not in ' \t\n\r':
                current_name += char
            elif in_quote is not None:
                current_name += char

        i += 1

    return comments


def _comment_survived(comment: str, result: str) -> bool:
    """True if *comment* (or its inner text) is present in *result*.

    Newly injected FigTree attributes may be MERGED into the original
    comment (e.g. ``[&support=90,!color=#00ff00]``), so an exact bracketed
    match is not required — the inner attribute text suffices.
    """
    if comment in result:
        return True
    inner = comment.strip()
    if inner.startswith('[') and inner.endswith(']'):
        inner = inner[1:-1]
    return bool(inner) and inner in result


def reinsert_bracket_comments(newick: str, comments: List[Dict[str, Any]]) -> str:
    """Re-insert bracket comments into a serialized Newick string.

    Uses taxon names to locate insertion points. To avoid mis-matching
    when one taxon name is a substring of another (e.g., 'A' vs 'AA'),
    we try both quoted and unquoted patterns and require the match to be
    followed by a valid Newick separator (: , ) ;).
    """
    if not comments:
        return newick

    result = newick

    # Process comments attached to taxon names
    for comment_info in comments:
        if comment_info['position_type'] == 'after_name':
            taxon_name = comment_info['taxon_name']
            bracket_comment = comment_info['comment']

            if not taxon_name:
                continue

            # Check if the comment is already present (from new annotations
            # or from Biopython's Clade.comment round-trip, possibly merged
            # with injected attributes).
            if _comment_survived(bracket_comment, result):
                continue

            # Build candidate patterns: try quoted first, then unquoted
            # This handles the case where Bio.Phylo may or may not quote the name
            escaped_name = taxon_name.replace("'", "''")
            has_special = ' ' in taxon_name or "'" in taxon_name

            # Pattern 1: quoted name followed by separator
            quoted_pattern = f"'{re.escape(escaped_name)}'(?=\\s*[:\\),;])"
            # Pattern 2: unquoted name followed by separator (word boundary)
            unquoted_pattern = r'(?<![A-Za-z0-9_])' + re.escape(taxon_name) + r'(?=\s*[:\),;])'

            inserted = False
            # Try quoted pattern first
            match = re.search(quoted_pattern, result)
            if match:
                insert_pos = match.end()
                result = result[:insert_pos] + bracket_comment + result[insert_pos:]
                inserted = True

            # If not inserted and name doesn't require quoting, try unquoted
            if not inserted and not has_special:
                match = re.search(unquoted_pattern, result)
                if match:
                    insert_pos = match.end()
                    result = result[:insert_pos] + bracket_comment + result[insert_pos:]
                    inserted = True

            if not inserted:
                warnings.warn(
                    f"Could not locate taxon '{taxon_name}' in serialized tree "
                    f"to re-insert bracket comment. Comment may be lost.",
                    CompatibilityWarning,
                )

        elif comment_info['position_type'] == 'after_branch_length':
            # The comment may already have survived via Biopython's
            # ``Clade.comment`` round-trip; only warn when it is truly lost.
            if _comment_survived(comment_info['comment'], result):
                continue
            # Bracket comments attached to branch lengths (e.g., :0.123[&posterior=0.95])
            # cannot be reliably re-inserted via text matching because Bio.Phylo may
            # alter branch length precision during serialization.
            warnings.warn(
                f"Bracket comment attached to branch length "
                f"'{comment_info.get('branch_length', '?')}' could not be preserved "
                f"during annotation injection. BEAST posterior probabilities or other "
                f"metadata attached to branch lengths will be lost. Consider attaching "
                f"critical metadata to taxon names instead.",
                CompatibilityWarning,
            )

        elif comment_info['position_type'] in ('after_internal_node', 'unattached'):
            # Already preserved through the Clade.comment round-trip?
            if _comment_survived(comment_info['comment'], result):
                continue
            # Comments attached to internal nodes (after ')') or unattached
            # root-level attributes cannot be re-located reliably after
            # serialization; emit an explicit warning instead of failing
            # silently.
            where = (
                'an internal node'
                if comment_info['position_type'] == 'after_internal_node'
                else 'the tree root or block level'
            )
            warnings.warn(
                f"Bracket comment {comment_info.get('comment', '[&...]')!r} attached "
                f"to {where} could not be preserved during annotation "
                f"injection and will be lost.",
                CompatibilityWarning,
            )

    return result
