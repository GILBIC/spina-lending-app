"""Optional deterministic whole-file pytest sharding for CI.

Load with ``-p tools.pytest_ci_shard``. Both shard environment variables must
be present; without them pytest collection is unchanged.
"""

import os
from pathlib import Path

import pytest

_SHARD = pytest.StashKey[tuple[int, int]]()
_SUMMARY = pytest.StashKey[str]()


def pytest_configure(config: pytest.Config) -> None:
    index = os.environ.get("SPINA_TEST_SHARD_INDEX")
    count = os.environ.get("SPINA_TEST_SHARD_COUNT")
    if index is None and count is None:
        return
    if index is None or count is None:
        raise pytest.UsageError(
            "Set SPINA_TEST_SHARD_INDEX and SPINA_TEST_SHARD_COUNT together."
        )
    try:
        shard_index, shard_count = int(index), int(count)
    except ValueError:
        raise pytest.UsageError(
            "SPINA_TEST_SHARD_INDEX and SPINA_TEST_SHARD_COUNT must be integers."
        ) from None
    if shard_count <= 0 or not 0 <= shard_index < shard_count:
        raise pytest.UsageError(
            "SPINA_TEST_SHARD_COUNT must be positive and "
            "SPINA_TEST_SHARD_INDEX must be in [0, count)."
        )
    config.stash[_SHARD] = shard_index, shard_count


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if _SHARD not in config.stash:
        return
    index, count = config.stash[_SHARD]
    # Root-relative POSIX paths are stable across runners and collection order.
    paths = {
        item: Path(os.path.relpath(item.path, config.rootpath)).as_posix()
        for item in items
    }
    files = sorted(set(paths.values()))
    selected_files = set(files[index::count])
    selected = [item for item in items if paths[item] in selected_files]
    deselected = [item for item in items if paths[item] not in selected_files]
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    config.stash[_SUMMARY] = (
        f"Spina CI shard index {index} of {count}: selected {len(selected)} tests "
        f"in {len(selected_files)} files; deselected {len(deselected)} tests"
    )


def pytest_report_collectionfinish(config: pytest.Config) -> str | None:
    return config.stash.get(_SUMMARY, None)
