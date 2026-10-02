"""Exercise CI sharding through real pytest collection in isolated subprocesses."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = "SPINA_TEST_SHARD_INDEX"
COUNT = "SPINA_TEST_SHARD_COUNT"
NODE = re.compile(r"^(?:[a-z]+/)*test_[a-z]+\.py::test_case_\d+$", re.MULTILINE)


@pytest.fixture
def suite(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    for name, size in [("a", 4), ("b", 2), ("c", 3), ("d", 1), ("e", 2)]:
        (tmp_path / f"test_{name}.py").write_text(
            "\n".join(f"def test_case_{n}():\n    assert True\n" for n in range(size)),
            encoding="utf-8",
        )
    return tmp_path


def collect(suite, settings=None, reverse=False):
    env = os.environ.copy()
    for key in [INDEX, COUNT, "PYTEST_ADDOPTS", "PYTEST_PLUGINS"]:
        env.pop(key, None)
    env.update(PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    env.update(settings or {})
    files = sorted(suite.rglob("test_*.py"), reverse=reverse)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tools.pytest_ci_shard",
            "-c",
            str(suite / "pytest.ini"),
            "--collect-only",
            "--import-mode=importlib",
            "-q",
            *map(str, files),
        ],
        cwd=suite,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def nodes(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return set(NODE.findall(result.stdout))


def test_unset_leaves_all_tests_unchanged(suite):
    result = collect(suite)
    assert len(nodes(result)) == 12
    assert "Spina CI shard" not in result.stdout
    assert "deselected" not in result.stdout


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_shards_cover_all_tests_once_keep_files_whole_and_are_deterministic(
    suite, count
):
    all_nodes = nodes(collect(suite))
    shards = []
    for index in range(count):
        settings = {INDEX: str(index), COUNT: str(count)}
        result = collect(suite, settings)
        selected = nodes(result)
        assert selected == nodes(collect(suite, settings, reverse=True))
        selected_files = {node.split("::")[0] for node in selected}
        expected_files = {
            f"test_{name}.py" for n, name in enumerate("abcde") if n % count == index
        }
        assert selected_files == expected_files
        for file in selected_files:
            assert {
                node for node in all_nodes if node.startswith(file + "::")
            } <= selected
        assert (
            f"Spina CI shard index {index} of {count}: selected {len(selected)} tests in {len(selected_files)} files"
            in result.stdout
        )
        assert f"deselected {12 - len(selected)} tests" in result.stdout
        assert all(not selected & other for other in shards)
        shards.append(selected)
    assert set().union(*shards) == all_nodes


@pytest.mark.parametrize(
    "settings",
    [
        {INDEX: "0"},
        {COUNT: "2"},
        {INDEX: "", COUNT: "2"},
        {INDEX: "1.0", COUNT: "2"},
        {INDEX: "0", COUNT: "bad"},
        {INDEX: "0", COUNT: "0"},
        {INDEX: "0", COUNT: "-1"},
        {INDEX: "-1", COUNT: "2"},
        {INDEX: "2", COUNT: "2"},
    ],
)
def test_invalid_settings_fail_before_collection(suite, settings):
    result = collect(suite, settings)
    assert result.returncode == 4, result.stdout + result.stderr
    assert "SPINA_TEST_SHARD" in result.stderr
    assert not NODE.findall(result.stdout)


def test_empty_shard_keeps_pytest_no_tests_exit_status(suite):
    result = collect(suite, {INDEX: "5", COUNT: "6"})
    assert result.returncode == 5, result.stdout + result.stderr
    assert "selected 0 tests in 0 files; deselected 12 tests" in result.stdout


def test_nested_paths_with_same_basename_use_relative_posix_file_keys(suite):
    for folder in ["alpha", "zeta"]:
        nested = suite / folder
        nested.mkdir()
        (nested / "test_a.py").write_text(
            "def test_case_0():\n    assert True\n", encoding="utf-8"
        )
    selected = nodes(collect(suite, {INDEX: "0", COUNT: "2"}))
    assert {node.split("::")[0] for node in selected} == {
        "alpha/test_a.py",
        "test_b.py",
        "test_d.py",
        "zeta/test_a.py",
    }
    assert selected == nodes(collect(suite, {INDEX: "0", COUNT: "2"}, reverse=True))


def test_eight_shards_cover_larger_suite_once_without_splitting_files(suite):
    for name in "fghijkl":
        (suite / f"test_{name}.py").write_text(
            "def test_case_0():\n    assert True\n\ndef test_case_1():\n    assert True\n",
            encoding="utf-8",
        )
    all_nodes = nodes(collect(suite))
    assert len(all_nodes) == 26
    shards = []
    for index in range(8):
        settings = {INDEX: str(index), COUNT: "8"}
        selected = nodes(collect(suite, settings))
        assert selected
        assert selected == nodes(collect(suite, settings, reverse=True))
        files = {node.split("::")[0] for node in selected}
        assert files == {
            f"test_{name}.py" for n, name in enumerate("abcdefghijkl") if n % 8 == index
        }
        assert selected == {node for node in all_nodes if node.split("::")[0] in files}
        assert all(not selected & previous for previous in shards)
        shards.append(selected)
    assert set().union(*shards) == all_nodes
