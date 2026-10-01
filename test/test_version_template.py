"""Guard the build-time version template against the no-SCM case.

``pyproject.toml`` writes ``figtreekit/_version.py`` from
``version_file_template``, a plain ``str.format`` template. Its inputs are not
all guaranteed to exist: when setuptools_scm cannot read the SCM - a source
tree with no ``.git``, a Docker build context, an unpacked sdist - it falls
back to ``fallback_version`` and the resulting ``ScmVersion`` has ``node`` and
``node_date`` set to ``None``.

A format specifier on either attribute then raises

    TypeError: unsupported format string passed to NoneType.__format__

and the build dies. A ``str.format`` template has no way to say "use this if
present, else empty", so the constraint has to be enforced by a test rather
than by the template.

This is not hypothetical: the Dockerfile does ``COPY . /app`` and then
``pip install -e .``, which is exactly a no-SCM build, and it failed that way
in CI. See test_jar_provenance.py for the binary-provenance counterpart.
"""

import ast
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# figtreekit/__init__.py imports these three in one statement:
#     from ._version import __version__, __version_date__, __git_hash__
# A template missing any of them raises ImportError there, and the package
# then silently reports a hardcoded fallback version instead of failing.
REQUIRED_NAMES = ("__version__", "__version_date__", "__git_hash__")


def _scm_config():
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["tool"]["setuptools_scm"]


class _NoScm:
    """Stands in for the ScmVersion setuptools_scm builds with no SCM."""

    node = None
    node_date = None
    node_sha = None
    dirty = None
    distance = None
    exact = False
    preformatted = None
    branch = None
    describe = None
    tag = None
    time = None


def _render(config, scm):
    return config["version_file_template"].format(
        version="1.2.3", version_tuple=(1, 2, 3), scm_version=scm
    )


def _rendered_assignments(rendered):
    """Top-level ``name = <literal>`` bindings in the rendered template.

    Parsed rather than executed. The template is repository data, and exec on
    repository data is both a code-scanning finding and a bad habit; ast gives
    the same answer - is this valid Python, and does it bind these names to
    these values - without running anything.
    """
    tree = ast.parse(rendered)
    assigned = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            assigned[target.id] = ast.literal_eval(node.value)
        except ValueError:
            # __version_tuple__ is a tuple literal and parses fine; a non-literal
            # binding simply is not asserted on.
            continue
    return assigned


class TestVersionTemplateSurvivesMissingScm:
    def test_renders_when_scm_metadata_is_absent(self):
        """The exact failure the Docker build hit."""
        config = _scm_config()
        try:
            rendered = _render(config, _NoScm())
        except TypeError as exc:
            raise AssertionError(
                "version_file_template raises when setuptools_scm falls back "
                f"to fallback_version: {exc}\n"
                "A format specifier such as {scm_version.node_date:%Y-%m-%d} "
                "cannot survive node_date being None. Either drop the "
                "specifier or move the derivation into figtreekit/__init__.py, "
                "but do not leave it in the template."
            ) from exc
        else:
            # else, not a statement after except: on the except path `rendered`
            # was never bound, and CodeQL reports reaching the assert with it
            # uninitialised ("Potentially uninitialized local variable").
            assert "__version__" in rendered

    def test_no_format_specifier_on_optional_scm_attributes(self):
        """Prose form of the same rule, to keep the failure readable."""
        template = _scm_config()["version_file_template"]
        for attribute in ("node", "node_date", "node_sha", "time"):
            placeholder = "{scm_version." + attribute
            index = template.find(placeholder)
            while index != -1:
                after = template[index + len(placeholder) :]
                closing = after.find("}")
                segment = after[:closing] if closing != -1 else after
                assert "{" not in segment and "!" not in segment, (
                    f"{{scm_version.{attribute}}} carries a conversion or nested "
                    f"field ({segment!r}). These attributes are None when "
                    "there is no SCM, so only a bare {scm_version.attr} is safe."
                )
                index = template.find(placeholder, index + 1)

    def test_defines_every_name_the_package_imports(self):
        assigned = _rendered_assignments(_render(_scm_config(), _NoScm()))
        for name in REQUIRED_NAMES:
            assert name in assigned, (
                f"the generated _version.py would not define {name}; "
                "figtreekit/__init__.py imports all three in one statement and "
                f"would fall through to a hardcoded version (defines {sorted(assigned)})"
            )

    def test_generated_file_is_valid_python_with_a_usable_version(self):
        assigned = _rendered_assignments(_render(_scm_config(), _NoScm()))
        assert assigned["__version__"] == "1.2.3"
        # The two optional fields must be empty strings, never the literal
        # text "None" that a bare {scm_version.node} would render.
        assert assigned["__git_hash__"] == ""
        assert assigned["__version_date__"] == ""

    def test_project_uses_version_file_not_the_deprecated_write_to(self):
        config = _scm_config()
        assert "write_to" not in config, (
            "write_to is deprecated and documented as broken for sdist builds; "
            "use version_file, which resolves against this file"
        )
        assert config["version_file"] == "figtreekit/_version.py"

    def test_build_system_floor_matches_the_pep639_license_fields(self):
        """license/license-files below need setuptools>=77, not >=61."""
        with PYPROJECT.open("rb") as handle:
            pyproject = tomllib.load(handle)
        project = pyproject["project"]
        floors = {}
        for requirement in pyproject["build-system"]["requires"]:
            for specifier in requirement.split(","):
                specifier = specifier.strip()
                if specifier.startswith("setuptools>"):
                    floors["setuptools"] = int(specifier.split(">=")[1])
        assert floors["setuptools"] >= 77, (
            f"build-system requires setuptools>={floors['setuptools']} but the "
            "project uses the PEP 639 `license`/`license-files` fields, which "
            "need >=77"
        )
        assert "license" in project
