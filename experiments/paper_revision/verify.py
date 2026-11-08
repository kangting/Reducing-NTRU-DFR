"""Regenerate the revision calculations and compare them with the paper."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np


ROOT = Path(__file__).resolve().parent
COMMANDS = (
    (("security_audit.py",), "security_results.json"),
    (("rank_check.py", "--out", "rank_check.json"), "rank_check.json"),
    (("ablation_check.py",), "ablation_check.json"),
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare(got, expected, field):
    """Compare exact fields verbatim and allow roundoff in numeric diagnostics."""
    require(type(got) is type(expected), f"{field}: type differs")
    if isinstance(expected, dict):
        require(got.keys() == expected.keys(), f"{field}: keys differ")
        for key in expected:
            compare(got[key], expected[key], f"{field}.{key}")
    elif isinstance(expected, list):
        require(len(got) == len(expected), f"{field}: length differs")
        for i, (value, reference) in enumerate(zip(got, expected)):
            compare(value, reference, f"{field}[{i}]")
    elif isinstance(expected, float):
        require(math.isclose(got, expected, rel_tol=1e-12, abs_tol=1e-12),
                f"{field}: {got} differs from {expected}")
    else:
        require(got == expected, f"{field}: exact field differs")


def check_paper(work):
    paper = load(ROOT / "paper_values.json")
    rows = {row["profile"]: row for row in load(work / "security_results.json")["rows"]}
    for profile, expected in paper["table_iii"].items():
        summary = rows[profile]["summary"]
        key, ct, msg = (summary[group] for group in
                        ("ordinary_key", "ordinary_ciphertext", "factored_message"))
        conditional = summary["old_conditional"]
        actual = [
            f"{key['C']:.3f}", f"{ct['C']:.3f}",
            f"{msg['C']:.3f}" if profile.startswith("D") else None,
            f"{conditional['C']:.3f}", conditional["route"],
            f"{conditional['coverage']['log2']:.3f}",
        ]
        require(actual == expected, f"Table III {profile}: {actual} != {expected}")
        route_ids = [key["route"], ct["route"]]
        if profile.startswith("D"):
            route_ids.append(msg["route"])
        route_ids.append(conditional["route"])
        print(f"Table III {profile}: PASS ({', '.join(route_ids)})")

    for profile, route_id, *expected in paper["table_vi"]:
        route = rows[profile]["routes"][route_id]
        actual = [
            f"{route['C']:.3f}", f"{route['Q_at_C']:.3f}", route["d"], route["beta"],
            f"{route['coverage']['log2']:.3f}",
        ]
        require(actual == expected, f"Table VI {profile}/{route_id}: {actual} != {expected}")
        print(f"Table VI {profile}/{route_id}: PASS")

    for profile, expected in paper["f_only"].items():
        route = rows[profile]["routes"]["affine_f"]
        actual = [f"{100 * route['coverage']['value']:.2f}", f"{route['C']:.3f}"]
        require(actual == expected, f"Section VI-B {profile} f-only: {actual} != {expected}")

    ablation = load(work / "ablation_check.json")
    for profile, field, expected in paper["ablation_exponents"]:
        actual = f"{ablation[profile][field]['minus_log2']:.3f}"
        require(actual == expected, f"Appendix C {profile}/{field}: {actual} != {expected}")
    print("Appendix C: PASS (reported exponents and exact certificate fields)")

    for row in load(work / "rank_check.json")["profile_tests"]:
        profile = row["profile"]
        actual = f"{row['conditional_rank_loss_probability']['minus_log2_probability']:.3f}"
        expected = paper["rank_exception_exponents"][profile]
        require(actual == expected, f"Appendix D-C {profile}: {actual} != {expected}")
    print("Appendix D-C: PASS (rank checks and exception exponents)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="new directory for generated JSON files")
    args = parser.parse_args()
    if args.out and args.out.exists():
        parser.error("--out must name a new directory")

    manifest = load(ROOT / "manifest.json")
    for name, expected in manifest["files"].items():
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        require(digest == expected, f"SHA-256 differs for {name}")
    print(f"{manifest['artifact']} {manifest['version']}", flush=True)
    print(f"Python {sys.version.split()[0]}, NumPy {np.__version__}", flush=True)
    print("Manifest: PASS", flush=True)

    env = os.environ.copy()
    env.pop("PYTHONOPTIMIZE", None)
    with tempfile.TemporaryDirectory(prefix="ntru-revision-audit-") as folder:
        work = Path(folder)
        for path in (ROOT / "reproduction").iterdir():
            if path.suffix == ".py" or path.name == "security_inputs.json":
                shutil.copy2(path, work / path.name)
        for command, name in COMMANDS:
            completed = subprocess.run(
                [sys.executable, *command], cwd=work, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                check=False,
            )
            if completed.returncode:
                sys.stderr.write(completed.stdout)
                completed.check_returncode()
            compare(load(work / name), load(ROOT / "expected" / name), name)
            print(f"{command[0]}: PASS ({name} matches expected output)", flush=True)
        check_paper(work)
        if args.out:
            args.out.mkdir(parents=True)
            for _, name in COMMANDS:
                shutil.copy2(work / name, args.out / name)
    print("All revision audit checks passed.")


if __name__ == "__main__":
    main()
