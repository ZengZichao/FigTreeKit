# Security Policy

## Supported versions

Only the latest release line is supported. Security fixes are made to
`main` and released as a patch of the current minor (e.g. `v1.1.x`).
Older releases do not receive backports; upgrade to the latest tag on
PyPI instead.

## Reporting a vulnerability

Please use **GitHub's private vulnerability reporting** for this
repository (Security tab → "Report a vulnerability"). That keeps the
report, the discussion and the fix coordination out of the public issue
tracker until a release is ready.

If private reporting is unavailable for some reason, email
**zengzichao@sjtu.edu.cn** with `[FigTreeKit security]` in the subject.
Please do not open a public issue for anything you believe is
exploitable.

You can expect an initial response within **7 days**. If the report is
accepted, the fix lands on `main`, a patch release is cut, and the
reporter is credited in the release notes unless they ask otherwise.

## Scope

In scope:

- Anything in the parsing / styling / rendering pipeline that lets a
  crafted tree file (Newick, Nexus, BEAST output) execute code, escape
  the output directory, or corrupt files outside the user's intent.
  Tree files are untrusted input: they routinely arrive by email and
  from collaborators.
- Supply-chain integrity of the shipped artifacts: the two jars
  (`figtreekit/figtree_patched.jar`, `_figtree_patch/figtree_original.jar`)
  are pinned by SHA-256 in `_figtree_patch/BUILD_PROVENANCE.md` and
  re-verified on every CI run by `test/test_jar_provenance.py`. A
  mismatch between the recorded hash and the shipped jar is a security
  report, not a build accident.
- The release path: `v*` tags are immutable (a repository ruleset
  blocks updates and deletions), and PyPI publishing uses OIDC Trusted
  Publishing bound to the `pypi` environment.

Out of scope:

- The upstream FigTree application itself; the patched files under
  `_figtree_patch/src/` are analyzed upstream and shipped only as a
  compiled jar. Report upstream issues to the FigTree project.
- Denial-of-service on pathological but bounded inputs (very large or
  very deep trees) unless it crosses into the memory-corruption class.
- Vulnerabilities in transitive Python dependencies — Dependabot
  watches those; report them upstream and they will land here via the
  weekly updates.

## Automated scanning

- Dependabot security updates and secret scanning with push protection
  are enabled on this repository.
- CodeQL analyzes Python on every push and pull request and weekly.
- `v*` release tags cannot be rewritten or deleted once pushed.
