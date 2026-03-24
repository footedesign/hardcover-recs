from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv("PIPELINE_DATA_ROOT", "/data"))
RELEASES_DIR = DATA_ROOT / "releases"
CURRENT_LINK = DATA_ROOT / "current"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("init", "refresh"), default="refresh")
    return parser.parse_args()


def live_artifacts_exist() -> bool:
    return (CURRENT_LINK / "hardcover.db").is_file() and (CURRENT_LINK / "svd_model.npz").is_file()


def release_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_step(script_name: str, env: dict[str, str]) -> None:
    command = [sys.executable, str(PROJECT_ROOT / "scripts" / script_name)]
    subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


def switch_current_symlink(target_dir: Path) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_link = DATA_ROOT / ".current.tmp"
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    tmp_link.symlink_to(Path("releases") / target_dir.name)
    os.replace(tmp_link, CURRENT_LINK)


def validate_release(release_dir: Path) -> None:
    db_path = release_dir / "hardcover.db"
    model_path = release_dir / "svd_model.npz"
    if not db_path.is_file():
        raise RuntimeError(f"Pipeline did not produce database at {db_path}")
    if not model_path.is_file():
        raise RuntimeError(f"Pipeline did not produce model at {model_path}")


def prune_old_releases(keep: int = 2) -> None:
    if not RELEASES_DIR.exists():
        return
    releases = sorted((path for path in RELEASES_DIR.iterdir() if path.is_dir()), key=lambda path: path.name)
    while len(releases) > keep:
        old = releases.pop(0)
        if CURRENT_LINK.exists() and old.resolve() == CURRENT_LINK.resolve():
            continue
        shutil.rmtree(old, ignore_errors=True)


def main() -> None:
    args = parse_args()

    if args.mode == "init" and live_artifacts_exist():
        print("pipeline: current release already exists; skipping init")
        return

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    new_release = RELEASES_DIR / release_id()
    new_release.mkdir(parents=True, exist_ok=False)

    env = os.environ.copy()
    env["HARDCOVER_DB_PATH"] = str(new_release / "hardcover.db")
    env["HARDCOVER_MODEL_PATH"] = str(new_release / "svd_model.npz")

    try:
        run_step("init_db.py", env)
        run_step("fetch_ratings.py", env)
        run_step("train_svd.py", env)
        run_step("rebuild_search_index.py", env)
        validate_release(new_release)
        switch_current_symlink(new_release)
        prune_old_releases()
        print(f"pipeline: activated release {new_release.name}")
    except Exception:
        shutil.rmtree(new_release, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
