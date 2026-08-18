#!/usr/bin/env python3
"""Run Archipelago Generate against this repo's built wikipelago.apworld.

Used by GitHub Actions. Locally:

  python world/ci_generate.py --ap-root PATH/TO/Archipelago \\
      --apworld world/APWorld/wikipelago.apworld
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CASES = (
    {
        "id": "en-default",
        "seed": 42,
        "values": {
            "name": "CI-EN",
        },
    },
    {
        "id": "fr-goal-pool",
        "seed": 43,
        "values": {
            "name": "CI-FR",
            "wikipedia_language": "fr",
        },
    },
    {
        "id": "pl-branches",
        "seed": 44,
        "values": {
            "name": "CI-PL",
            "wikipedia_language": "pl",
            "branch_count": "2",
            "branch_length": "3",
        },
    },
)


def _replace_yaml_key(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(\s*){re.escape(key)}:\s*.*$", re.MULTILINE)
    for match in pattern.finditer(text):
        line = match.group(0)
        if line.lstrip().startswith("#"):
            continue
        start, end = match.span()
        return text[:start] + f"{match.group(1)}{key}: {value}" + text[end:]
    raise SystemExit(f"Could not set YAML key {key!r}")


def _write_player_yaml(template: str, dest: Path, values: dict[str, str]) -> None:
    text = template
    for key, value in values.items():
        text = _replace_yaml_key(text, key, value)
    dest.write_text(text, encoding="utf-8")


def _run_generate(ap_root: Path, players: Path, output: Path, seed: int) -> None:
    env = os.environ.copy()
    env["SKIP_REQUIREMENTS_UPDATE"] = "1"
    cmd = [
        sys.executable,
        str(ap_root / "Generate.py"),
        "--player_files_path",
        str(players),
        "--outputpath",
        str(output),
        "--seed",
        str(seed),
    ]
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(
        cmd,
        cwd=ap_root,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(f"Generate.py failed with exit {result.returncode}")
    zips = sorted(output.glob("*.zip"))
    if not zips:
        raise SystemExit(f"Generate produced no zip in {output}")
    print(f"Generated: {zips[-1].name}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ap-root", required=True, type=Path, help="Archipelago source checkout")
    parser.add_argument("--apworld", required=True, type=Path, help="Built wikipelago.apworld")
    parser.add_argument(
        "--yaml",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "yaml" / "Wikipelago.yaml",
        help="Player YAML template",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("generate-work"),
        help="Scratch directory for player files and output zips",
    )
    args = parser.parse_args()

    ap_root = args.ap_root.resolve()
    apworld = args.apworld.resolve()
    yaml_path = args.yaml.resolve()
    work = args.work_dir.resolve()

    if not (ap_root / "Generate.py").is_file():
        raise SystemExit(f"Generate.py not found in {ap_root}")
    if not apworld.is_file():
        raise SystemExit(f"Missing apworld: {apworld}")
    if not yaml_path.is_file():
        raise SystemExit(f"Missing YAML template: {yaml_path}")

    dest_apworld = ap_root / "worlds" / "wikipelago.apworld"
    dest_apworld.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apworld, dest_apworld)
    print(f"Installed {apworld.name} -> {dest_apworld}", flush=True)

    template = yaml_path.read_text(encoding="utf-8")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    for case in CASES:
        case_id = case["id"]
        players = work / case_id / "players"
        output = work / case_id / "output"
        players.mkdir(parents=True)
        output.mkdir(parents=True)
        _write_player_yaml(template, players / f"{case_id}.yaml", case["values"])
        print(f"=== Generate {case_id} (seed {case['seed']}) ===", flush=True)
        _run_generate(ap_root, players, output, int(case["seed"]))

    print(f"All {len(CASES)} Generate cases passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
