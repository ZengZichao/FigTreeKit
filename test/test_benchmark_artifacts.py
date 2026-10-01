"""Check the committed measurement files against each other and their provenance.

``benchmarks/`` holds the numbers the paper quotes, committed to the
repository so they travel with the code. ``MANIFEST.in`` calls them
"canonical machine-stamped measurement files". That makes them an artifact
with an implied contract: they were produced by one run of the benchmark
suite, in one environment, recorded together.

Nothing enforced that. The files were regenerated only by hand, so a stale
copy, a hand-edited cell, a truncated paste or a row deleted from one CSV
would sit next to its provenance record and contradict it without a word.
These tests read the provenance record (``benchmark_meta.json``,
``gtdb_results.json``) and assert the data files still describe the run that
record claims - same sizes, same seeds, same repeat count, same number of
fitted points, same degrees of freedom.

Deliberately *not* asserted: that a fresh run reproduces the timings. Timings
are a property of one frozen machine (an Apple M5, a specific JDK and
interpreter), so CI cannot reproduce them and must not try. What CI can check
is that the files are internally coherent and honestly stamped, which is what
drift actually looks like.

See also ``test_jar_provenance.py``, which does the same job for the two
FigTree binaries.
"""

import csv
import json
import re
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH = REPO_ROOT / "benchmarks"

META = BENCH / "benchmark_meta.json"
RESULTS = BENCH / "results.csv"
SLOPES = BENCH / "slope_summary.json"
GTDB = BENCH / "gtdb_results.json"

# Every measurement file, with the type of each column. Declaring the schema
# here rather than inferring it is the point: a column silently changing type,
# or a text label being pasted into a numeric field, has to be a failure.
SCHEMA = {
    "results.csv": {
        "str": ["shape"],
        "int": ["n_taxa", "seed", "repeats", "peak_memory_bytes"],
        "float": [
            "parse_mean_s",
            "parse_sem_s",
            "export_mean_s",
            "export_sem_s",
            "total_mean_s",
            "total_sem_s",
            "export_median_s",
            "export_iqr_s",
        ],
    },
    "results_shapes.csv": {
        "str": ["shape"],
        "int": ["n_taxa"],
        "float": [
            "export_mean_s",
            "export_sem_s",
            "export_median_s",
            "export_iqr_s",
        ],
    },
    "results_annotations.csv": {
        "str": ["annotations"],
        "int": ["n_taxa", "a"],
        "float": [
            "export_mean_s",
            "export_sem_s",
            "export_median_s",
            "export_iqr_s",
        ],
    },
    "competitive_results.csv": {
        "str": [],
        "int": ["n_taxa", "n_trees"],
        "float": [
            "figtreekit_export_mean_s",
            "figtreekit_export_sem_s",
            "biophylo_export_mean_s",
            "biophylo_export_sem_s",
            "ratio",
            "ratio_sem_s",
            "ratio_min",
            "ratio_max",
        ],
    },
    "stage_breakdown.csv": {
        "str": [],
        "int": ["n_taxa"],
        "float": ["parse_s", "annotate_s", "export_s", "render_s"],
    },
}

REQUIRED_META_KEYS = [
    "timestamp",
    "platform",
    "cpu",
    "python",
    "biopython",
    "java",
    "commit",
    "git_dirty",
    "sizes",
    "repeats",
    "seeds",
    "figtreekit_version",
    "statistical_unit",
]

# A 40-character git object name, as recorded by `git rev-parse HEAD`.
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


def _load_json(path):
    if not path.is_file():
        pytest.fail(f"measurement file is missing: {path.relative_to(REPO_ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # raise, not pytest.fail: this function has a return on the success path,
        # so a failure branch that merely called pytest.fail would leave the
        # function able to fall off the end, and CodeQL reports that as
        # "explicit returns mixed with implicit (fall through) returns".
        # pytest.fail does raise, but saying so explicitly keeps the control
        # flow checkable instead of relying on that.
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} is not valid JSON: {exc}") from exc


def _load_csv(path):
    if not path.is_file():
        pytest.fail(f"measurement file is missing: {path.relative_to(REPO_ROOT)}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        pytest.fail(
            f"{path.relative_to(REPO_ROOT)} has a header but no data rows; a "
            "committed measurement file with no measurements is a broken record"
        )
    return rows[0], rows[1:]


class TestProvenanceRecord:
    """The machine stamp must be complete enough to identify the run."""

    def test_meta_records_the_run(self):
        meta = _load_json(META)
        missing = [k for k in REQUIRED_META_KEYS if k not in meta]
        assert not missing, (
            f"benchmark_meta.json is missing {missing}; the record no longer "
            "identifies the environment the published numbers came from"
        )

    def test_meta_commit_is_a_sha1(self):
        meta = _load_json(META)
        assert _SHA1_RE.match(meta["commit"]), (
            f"benchmark_meta.json commit {meta['commit']!r} is not a 40-char "
            "git object name, so the measurement run cannot be located"
        )

    def test_gtdb_record_is_stamped(self):
        gtdb = _load_json(GTDB)
        for key in (
            "timestamp",
            "platform",
            "commit",
            "figtreekit_version",
            "stamp_source",
            "run_relationship",
        ):
            assert key in gtdb, f"gtdb_results.json is missing {key!r}"
        assert _SHA1_RE.match(gtdb["commit"]), (
            f"gtdb_results.json commit {gtdb['commit']!r} is not a 40-char " "git object name"
        )

    def test_gtdb_datasets_are_complete(self):
        gtdb = _load_json(GTDB)
        datasets = gtdb["datasets"]
        assert datasets, "gtdb_results.json records no datasets"
        # peak_memory_bytes was renamed to peak_memory_bytes_recorded when
        # the file was corrected by hand for a MiB/MB mix-up, so either name
        # is accepted; the required set is what a measurement needs to be
        # quotable.
        required = {
            "file",
            "dataset",
            "n_taxa",
            "parse_time_s",
            "export_time_s",
            "total_time_s",
            "peak_memory_MB",
            "heap_per_taxon_kB",
        }
        for entry in datasets:
            missing = sorted(required - set(entry))
            assert not missing, f"GTDB entry {entry.get('file')} missing {missing}"
            assert entry["n_taxa"] > 0
            assert "peak_memory_bytes_recorded" in entry or "peak_memory_bytes" in entry, (
                f"GTDB entry {entry['file']} records no memory figure in bytes, "
                "so peak_memory_MB cannot be checked"
            )

    def test_gtdb_memory_units_agree(self):
        """peak_memory_MB must be the SI megabyte form of the recorded bytes.

        This file already carries a `memory_unit_note` recording a previous
        MiB/MB confusion, and a 1.048576x error in a published heap figure is
        exactly the kind of drift that survives review. peak_memory_MB is
        rounded to one decimal, hence the tolerance.
        """
        gtdb = _load_json(GTDB)
        for entry in gtdb["datasets"]:
            raw = entry.get("peak_memory_bytes_recorded") or entry.get("peak_memory_bytes")
            if not raw:
                continue
            expected = raw / 1_000_000
            actual = entry["peak_memory_MB"]
            assert abs(actual - expected) < 0.06, (
                f"GTDB entry {entry['file']}: peak_memory_MB={actual} but "
                f"{raw} bytes is {expected:.4f} MB (SI); if this figure is "
                "really in MiB the file has reintroduced the unit mix-up its "
                "own memory_unit_note warns about"
            )


class TestMeasurementFiles:
    """Shape, typing and row structure of the committed CSVs."""

    @pytest.mark.parametrize("filename", sorted(SCHEMA))
    def test_rows_are_rectangular(self, filename):
        header, rows = _load_csv(BENCH / filename)
        width = len(header)
        for number, row in enumerate(rows, start=2):
            assert len(row) == width, (
                f"{filename} line {number} has {len(row)} fields, header has "
                f"{width}; the file has been hand-edited or truncated"
            )

    @pytest.mark.parametrize("filename", sorted(SCHEMA))
    def test_columns_have_declared_types(self, filename):
        header, rows = _load_csv(BENCH / filename)
        schema = SCHEMA[filename]
        expected_columns = set(schema["str"]) | set(schema["int"]) | set(schema["float"])
        assert set(header) == expected_columns, (
            f"{filename} columns {header} do not match the declared schema "
            f"{sorted(expected_columns)}; update SCHEMA deliberately if the "
            "measurement format really changed"
        )
        for number, row in enumerate(rows, start=2):
            record = dict(zip(header, row))
            for name in header:
                raw = record[name]
                try:
                    if name in schema["int"]:
                        int(raw)
                    elif name in schema["float"]:
                        float(raw)
                except ValueError:
                    pytest.fail(
                        f"{filename} line {number}: column {name!r} holds "
                        f"{raw!r}, which is not a "
                        f"{'integer' if name in schema['int'] else 'float'}"
                    )

    @pytest.mark.parametrize("filename", sorted(SCHEMA))
    def test_measurements_are_positive(self, filename):
        """A zero or negative timing is a failed measurement, not a fast one."""
        header, rows = _load_csv(BENCH / filename)
        # Every duration column in these files is suffixed _s; the count-like
        # columns (n_taxa, seed, repeats, n_trees, a) are not.
        timing_columns = [name for name in header if name.endswith("_s")]
        assert timing_columns, f"{filename} declares no duration columns"
        for number, row in enumerate(rows, start=2):
            record = dict(zip(header, row))
            for name in timing_columns:
                value = float(record[name])
                assert value > 0, (
                    f"{filename} line {number}: {name} is {value}; a "
                    "non-positive measurement means that run failed, and it "
                    "must not be committed as a result"
                )

    def test_sem_is_never_larger_than_the_mean(self):
        """A SEM above its own mean is arithmetically impossible."""
        header, rows = _load_csv(RESULTS)
        for number, row in enumerate(rows, start=2):
            record = dict(zip(header, row))
            for mean_name in ("parse_mean_s", "export_mean_s", "total_mean_s"):
                sem_name = mean_name.replace("_mean_s", "_sem_s")
                mean = float(record[mean_name])
                sem = float(record[sem_name])
                assert sem <= mean, (
                    f"results.csv line {number}: {sem_name}={sem} exceeds " f"{mean_name}={mean}"
                )

    def test_no_duplicate_measurements(self):
        """One (n_taxa, seed) per row: a duplicate means a lost tree."""
        header, rows = _load_csv(RESULTS)
        record = [dict(zip(header, row)) for row in rows]
        keys = [(r["n_taxa"], r["seed"]) for r in record]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        assert not duplicates, (
            f"results.csv repeats (n_taxa, seed) pairs {duplicates}; the "
            "statistical unit is one independently generated tree per pair"
        )


class TestResultsAgainstProvenance:
    """results.csv must describe exactly the run benchmark_meta.json records."""

    def test_row_count_matches_sizes_times_seeds(self):
        meta = _load_json(META)
        _, rows = _load_csv(RESULTS)
        expected = len(meta["sizes"]) * len(meta["seeds"])
        assert len(rows) == expected, (
            f"results.csv has {len(rows)} rows but benchmark_meta.json "
            f"records {len(meta['sizes'])} sizes x {len(meta['seeds'])} seeds "
            f"= {expected} independent trees"
        )

    def test_sizes_match(self):
        meta = _load_json(META)
        header, rows = _load_csv(RESULTS)
        seen = sorted({int(dict(zip(header, r))["n_taxa"]) for r in rows})
        assert seen == sorted(meta["sizes"]), (
            f"results.csv covers n_taxa {seen}, benchmark_meta.json records "
            f"sizes {sorted(meta['sizes'])}"
        )

    def test_seeds_match(self):
        meta = _load_json(META)
        header, rows = _load_csv(RESULTS)
        seen = sorted({int(dict(zip(header, r))["seed"]) for r in rows})
        assert seen == sorted(meta["seeds"]), (
            f"results.csv uses seeds {seen}, benchmark_meta.json records "
            f"{sorted(meta['seeds'])}"
        )

    def test_repeats_match(self):
        meta = _load_json(META)
        header, rows = _load_csv(RESULTS)
        seen = {int(dict(zip(header, r))["repeats"]) for r in rows}
        assert seen == {meta["repeats"]}, (
            f"results.csv records repeats {sorted(seen)}, "
            f"benchmark_meta.json records {meta['repeats']}"
        )


class TestSlopeSummary:
    """The fitted summary must match the measurements it was fitted to."""

    def _fits(self):
        slopes = _load_json(SLOPES)
        fits = {k: v for k, v in slopes.items() if isinstance(v, dict)}
        assert fits, "slope_summary.json contains no fit records"
        return fits

    def test_fits_are_well_formed(self):
        for name, fit in self._fits().items():
            for key in ("slope", "se", "ci95", "n_points", "df", "unit"):
                assert key in fit, f"slope_summary.json[{name!r}] missing {key!r}"
            low, high = fit["ci95"]
            assert low <= fit["slope"] <= high, (
                f"slope_summary.json[{name!r}] slope {fit['slope']} lies outside "
                f"its own 95% interval [{low}, {high}]"
            )
            assert fit["df"] == fit["n_points"] - 2, (
                f"slope_summary.json[{name!r}] has df={fit['df']} for "
                f"n_points={fit['n_points']}; the record states the intervals "
                "are Student-t on n-2 degrees of freedom"
            )

    def test_pooled_fit_uses_every_tree(self):
        _, rows = _load_csv(RESULTS)
        pooled = self._fits()["export_vs_taxa_loglog"]
        assert pooled["n_points"] == len(rows), (
            f"the pooled export fit claims {pooled['n_points']} points but "
            f"results.csv holds {len(rows)} trees"
        )

    @pytest.mark.parametrize(
        "name",
        [
            "export_vs_taxa_loglog_per_size_medians",
            "memory_vs_taxa_loglog",
            "memory_vs_taxa_loglog_per_size_medians",
        ],
    )
    def test_per_size_fits_use_every_size(self, name):
        meta = _load_json(META)
        fit = self._fits()[name]
        assert fit["n_points"] == len(meta["sizes"]), (
            f"slope_summary.json[{name!r}] claims {fit['n_points']} points but "
            f"the run measured {len(meta['sizes'])} sizes"
        )


def test_recorded_version_is_reported():
    """Surface, without failing, how far the published numbers trail HEAD.

    The frozen measurement session behind these files is not reproducible
    outside it, so a version mismatch cannot be fixed by re-running anything -
    it needs that machine. Asserting equality here would produce a red build
    nobody can clear. Reporting it keeps the drift visible instead.
    """
    meta = _load_json(META)
    gtdb = _load_json(GTDB)
    try:
        from figtreekit import __version__ as current
    except Exception:  # pragma: no cover - package not importable
        current = None

    recorded = meta["figtreekit_version"]
    if current and recorded != current:
        warnings.warn(
            f"benchmarks/ was measured on figtreekit {recorded} "
            f"(commit {meta['commit'][:12]}); the tree is now {current}. The "
            "published timings were produced by that older commit and were not "
            "refreshed. Re-measure on the frozen environment to refresh them, "
            "or confirm the article's numbers still describe current behaviour.",
            UserWarning,
            stacklevel=2,
        )
    assert recorded == gtdb["figtreekit_version"], (
        f"benchmark_meta.json was recorded on {recorded} but gtdb_results.json "
        f"says {gtdb['figtreekit_version']}; the two were measured in the same "
        "session and must agree"
    )
