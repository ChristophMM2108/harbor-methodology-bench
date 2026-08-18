#!/usr/bin/env python3
"""
Harbor Methodology Bench — Results Reporting & Telemetry Aggregator.
Parses result.json files across jobs and computes summary tables and metric comparisons.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import Any


CONFIG_MARKERS = ("CLAUDE.md", "AGENTS.md")


def registered_skills(task_path: Path) -> list[str]:
    """Skill names the generator installed for this variant, if discoverable."""
    manifest = task_path / ".methodology-bench-manifest.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list((data.get("environment") or {}).get("skills_registered") or [])


MAX_AGENT_LOG_BYTES = 32 * 1024 * 1024


def _agent_log_text(agent_dir: Path) -> str:
    """Concatenate the agent's own top-level logs, including its native stream."""
    chunks: list[str] = []
    budget = MAX_AGENT_LOG_BYTES
    for path in sorted(agent_dir.glob("*")):
        if not path.is_file() or budget <= 0:
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace")[:budget])
        except OSError:
            continue
        budget -= path.stat().st_size
    return "\n".join(chunks)


def parse_adherence(trial_dir: Path, task_path: Path) -> dict[str, Any]:
    """Separate what the agent *had* from what the agent *used*.

    `skills_available` reads the agent CLI's own startup log, so it reflects the
    skills the CLI registered at runtime. `skills_invoked` and
    `config_markers_seen` look only at agent-authored trajectory steps, because a
    CLI's system prompt mentions `AGENTS.md` unconditionally and would otherwise
    register as adherence.

    Note that Claude Code loads a project `CLAUDE.md` silently into its system
    prompt. An empty `config_markers_seen` therefore means the agent never
    referred to the file by name, not that the file was absent — presence is
    what preflight proves.
    """
    agent_dir = trial_dir / "agent"
    trajectory = agent_dir / "trajectory.json"
    expected_skills = registered_skills(task_path)
    adherence: dict[str, Any] = {
        "trajectory_found": trajectory.is_file(),
        "config_markers_seen": [],
        "skills_available": [],
        "skills_invoked": [],
        "skill_tool_calls": 0,
    }
    if agent_dir.is_dir() and expected_skills:
        logs = _agent_log_text(agent_dir)
        adherence["skills_available"] = sorted(
            name for name in expected_skills if name in logs
        )
    if not trajectory.is_file():
        return adherence
    try:
        data = json.loads(trajectory.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return adherence
    text = "\n".join(
        json.dumps(step)
        for step in (data.get("steps") or [])
        if step.get("source") not in ("system", "user")
    )
    adherence["config_markers_seen"] = [m for m in CONFIG_MARKERS if m in text]
    adherence["skills_invoked"] = sorted(name for name in expected_skills if name in text)
    adherence["skill_tool_calls"] = text.count('"name": "Skill"') + text.count('"name":"Skill"')
    return adherence


def parse_trial_result(result_path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as err:
        print(f"Warning: Failed to parse {result_path}: {err}")
        return None

    config = data.get("config", {})
    task_cfg = config.get("task", {})
    task_path_str = task_cfg.get("path") or ""
    task_parts = Path(task_path_str).parts

    # Derive variant and task name from generated/<variant>/<task_name>
    if len(task_parts) >= 2:
        variant = task_parts[-2]
        task_name = task_parts[-1]
    else:
        variant = "unknown"
        task_name = task_path_str or result_path.parent.name

    agent_info = data.get("agent_info") or {}
    agent_name = agent_info.get("name") or config.get("agent", {}).get("name") or "unknown"
    model_info = agent_info.get("model_info") or {}
    model_name = model_info.get("name") or config.get("agent", {}).get("model_name") or "unknown"

    # Verifier reward
    verifier_result = data.get("verifier_result") or {}
    rewards = verifier_result.get("rewards") or {}
    reward_val = float(rewards.get("reward", 0.0) if isinstance(rewards, dict) else 0.0)
    success = reward_val > 0.0

    # Timing
    started_at_str = data.get("started_at")
    finished_at_str = data.get("finished_at")
    duration_sec: float | None = None
    if started_at_str and finished_at_str:
        try:
            t0 = datetime.datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
            t1 = datetime.datetime.fromisoformat(finished_at_str.replace("Z", "+00:00"))
            duration_sec = max(0.0, (t1 - t0).total_seconds())
        except Exception:
            duration_sec = None

    # Agent result metrics
    agent_res = data.get("agent_result") or {}
    n_input_tokens = agent_res.get("n_input_tokens") or 0
    n_output_tokens = agent_res.get("n_output_tokens") or 0
    n_cache_tokens = agent_res.get("n_cache_tokens") or 0
    total_tokens = n_input_tokens + n_output_tokens + n_cache_tokens
    cost_usd = float(agent_res.get("cost_usd") or 0.0)

    # Exception
    exception_info = data.get("exception_info") or {}
    exception_type = exception_info.get("exception_type") if exception_info else None
    exception_msg = exception_info.get("exception_message") if exception_info else None

    adherence = parse_adherence(result_path.parent, Path(task_path_str))

    return {
        "job_name": result_path.parent.parent.name,
        "trial_name": result_path.parent.name,
        "task_name": task_name,
        "variant": variant,
        "agent": agent_name,
        "model": model_name,
        "reward": reward_val,
        "success": success,
        "duration_sec": duration_sec,
        "input_tokens": n_input_tokens,
        "output_tokens": n_output_tokens,
        "cache_tokens": n_cache_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "exception_type": exception_type,
        "exception_msg": exception_msg,
        "skills_available": bool(adherence["skills_available"]),
        "referenced_project_config": bool(adherence["config_markers_seen"]),
        "used_toolkit_skill": bool(adherence["skills_invoked"]) or adherence["skill_tool_calls"] > 0,
        "adherence": adherence,
    }


def find_all_trials(jobs_dir: Path, pattern: str = "*") -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for job_path in sorted(jobs_dir.glob(pattern)):
        if not job_path.is_dir():
            continue
        # Check trial subdirectories (e.g. jobs/<job_name>/<trial_name>/result.json)
        for trial_res in sorted(job_path.glob("*/result.json")):
            parsed = parse_trial_result(trial_res)
            if parsed:
                trials.append(parsed)
    return trials


def generate_markdown_report(trials: list[dict[str, Any]]) -> str:
    if not trials:
        return "# Benchmark Results Report\n\nNo trial results found."

    lines: list[str] = [
        "# Harbor Methodology Bench — Results Report",
        f"\n**Total Trials Collected**: {len(trials)}",
        f"**Generated At**: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n",
        "## 1. Matrix Summary (By Agent & Methodology Condition)",
        "",
        "| Agent | Model | Condition | Trials | Successes | Success Rate | Mean Reward | Avg Time (s) | Total Cost ($) | Skills Available | Skills Used | Config Referenced |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    # Aggregate by (agent, model, variant)
    cells: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for t in trials:
        key = (t["agent"], t["model"], t["variant"])
        cells.setdefault(key, []).append(t)

    for (agent, model, variant), group in sorted(cells.items()):
        n_trials = len(group)
        n_success = sum(1 for x in group if x["success"])
        success_rate = (n_success / n_trials * 100.0) if n_trials > 0 else 0.0
        mean_reward = sum(x["reward"] for x in group) / n_trials if n_trials > 0 else 0.0
        valid_durations = [x["duration_sec"] for x in group if x["duration_sec"] is not None]
        avg_dur = (sum(valid_durations) / len(valid_durations)) if valid_durations else 0.0
        total_cost = sum(x["cost_usd"] for x in group)
        available = sum(1 for x in group if x.get("skills_available"))
        used_skill = sum(1 for x in group if x.get("used_toolkit_skill"))
        referenced = sum(1 for x in group if x.get("referenced_project_config"))

        lines.append(
            f"| `{agent}` | `{model}` | **{variant.upper()}** | {n_trials} | {n_success} | "
            f"{success_rate:.1f}% | {mean_reward:.2f} | {avg_dur:.1f}s | ${total_cost:.4f} | "
            f"{available}/{n_trials} | {used_skill}/{n_trials} | {referenced}/{n_trials} |"
        )

    lines.extend([
        "",
        "## 2. Per-Task Breakdown",
        "",
        "| Task | Condition | Agent | Reward | Success | Duration | Exception |",
        "|---|---|---|---:|:---:|---:|---|",
    ])

    for t in sorted(trials, key=lambda x: (x["task_name"], x["agent"], x["variant"])):
        dur_str = f"{t['duration_sec']:.1f}s" if t["duration_sec"] is not None else "N/A"
        succ_str = "✓ PASS" if t["success"] else "✗ FAIL"
        exc_str = f"`{t['exception_type']}`" if t["exception_type"] else "-"
        lines.append(
            f"| `{t['task_name']}` | **{t['variant']}** | `{t['agent']}` | {t['reward']:.2f} | "
            f"{succ_str} | {dur_str} | {exc_str} |"
        )

    methodology = [t for t in trials if t["variant"] not in ("baseline", "unknown")]
    if methodology:
        lines.extend([
            "",
            "## 3. Methodology Adherence (toolkit conditions only)",
            "",
            "| Task | Condition | Agent | Skills Available | Skills Invoked | Skill Tool Calls | Config Referenced |",
            "|---|---|---|---:|---|---:|---|",
        ])
        for t in sorted(methodology, key=lambda x: (x["task_name"], x["agent"], x["variant"])):
            detail = t.get("adherence") or {}
            markers = ", ".join(detail.get("config_markers_seen") or []) or "-"
            invoked = ", ".join(detail.get("skills_invoked") or []) or "-"
            available = len(detail.get("skills_available") or [])
            lines.append(
                f"| `{t['task_name']}` | **{t['variant']}** | `{t['agent']}` | {available} | "
                f"{invoked} | {detail.get('skill_tool_calls', 0)} | {markers} |"
            )

    # Exceptions summary if any
    exceptions = [t for t in trials if t["exception_type"]]
    if exceptions:
        lines.extend([
            "",
            "## 4. Exceptions & Failures",
            "",
            "| Job | Task | Agent | Exception Type | Details |",
            "|---|---|---|---|---|",
        ])
        for t in exceptions:
            short_msg = (t["exception_msg"] or "").replace("\n", " ")[:80]
            lines.append(
                f"| `{t['job_name']}` | `{t['task_name']}` | `{t['agent']}` | `{t['exception_type']}` | {short_msg} |"
            )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Harbor trial results and generate summary reports.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"), help="Path to jobs directory (default: jobs)")
    parser.add_argument("--pattern", type=str, default="*", help="Job directory glob pattern (e.g. 'pilot-*' or '*')")
    parser.add_argument("--json-out", type=Path, default=None, help="Save structured JSON summary to path")
    parser.add_argument("--md-out", type=Path, default=None, help="Save markdown report to path")
    args = parser.parse_args()

    jobs_dir = args.jobs_dir
    if not jobs_dir.exists():
        print(f"Error: Jobs directory {jobs_dir} does not exist.")
        return

    trials = find_all_trials(jobs_dir, pattern=args.pattern)
    print(f"Found {len(trials)} trial(s) in {jobs_dir} (pattern='{args.pattern}')\n")

    md_report = generate_markdown_report(trials)

    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md_report, encoding="utf-8")
        print(f"✓ Markdown report saved to {args.md_out}")
    else:
        print(md_report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        summary_data = {
            "total_trials": len(trials),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trials": trials,
        }
        args.json_out.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
        print(f"✓ JSON summary saved to {args.json_out}")


if __name__ == "__main__":
    main()
