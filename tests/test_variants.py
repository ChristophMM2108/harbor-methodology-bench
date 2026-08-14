from pathlib import Path

from harbor_methodology_bench.inject import copy_task, inject_snapshot
from harbor_methodology_bench.validate import validate_task


def make_task(root: Path) -> Path:
    task = root / "source" / "example"
    task.mkdir(parents=True)
    (task / "task.toml").write_text("[task]\n")
    (task / "instruction.md").write_text("original\n")
    return task


def test_baseline_is_identical(tmp_path: Path) -> None:
    source = make_task(tmp_path)
    generated = tmp_path / "generated"
    copy_task(source, generated)
    assert validate_task(source, generated, None) == []


def test_snapshot_is_preserved_without_changing_source(tmp_path: Path) -> None:
    source = make_task(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "AGENTS.md").write_text("use toolkit\n")
    (snapshot / ".agents").mkdir()
    (snapshot / ".agents" / "skill.txt").write_text("skill\n")
    generated = tmp_path / "generated"
    copy_task(source, generated)
    inject_snapshot(snapshot, generated, source)
    assert validate_task(source, generated, snapshot) == []


def test_snapshot_collision_is_archived_without_overwriting_task(tmp_path: Path) -> None:
    source = make_task(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "instruction.md").write_text("wrong\n")
    generated = tmp_path / "generated"
    copy_task(source, generated)
    inject_snapshot(snapshot, generated, source)
    assert (generated / "instruction.md").read_text() == "original\n"
    assert (generated / ".methodology-bench/toolkit-collisions/instruction.md").read_text() == "wrong\n"
