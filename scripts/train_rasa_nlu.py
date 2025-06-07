"""Train Rasa NLU model and copy it to models/rasa_nlu."""

from __future__ import annotations

import pathlib
import shutil
import subprocess


def main() -> None:
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    rasa_dir = base_dir / "rasa"
    models_dir = base_dir / "models" / "rasa_nlu"
    models_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["rasa", "train", "nlu"], cwd=rasa_dir, check=True)

    trained_models = sorted((rasa_dir / "models").glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not trained_models:
        raise RuntimeError("No trained Rasa model found")
    latest = trained_models[0]
    dest = models_dir / latest.name
    shutil.copy(latest, dest)
    print(f"Model copied to {dest}")


if __name__ == "__main__":
    main()
