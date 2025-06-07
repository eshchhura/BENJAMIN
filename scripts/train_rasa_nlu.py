"""Train and evaluate the Rasa NLU model.

This script validates the training data, trains the NLU pipeline and
evaluates the resulting model. The latest trained model is copied to
``models/rasa_nlu/`` for use by Jarvis.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess


def _run(cmd: list[str], cwd: pathlib.Path) -> None:
    """Run a subprocess and raise ``RuntimeError`` on failure.

    Args:
        cmd: Command and arguments to execute.
        cwd: Directory in which to run the command.

    Raises:
        RuntimeError: If the command exits with a non-zero status.
    """

    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed with code {result.returncode}")


def main() -> None:
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    rasa_dir = base_dir / "rasa"
    models_dir = base_dir / "models" / "rasa_nlu"
    models_dir.mkdir(parents=True, exist_ok=True)

    _run(["rasa", "data", "validate"], cwd=rasa_dir)
    _run(["rasa", "train", "nlu", "--config", "config.yml", "--data", "data"], cwd=rasa_dir)
    _run(["rasa", "test", "nlu", "--model", "models"], cwd=rasa_dir)

    trained_models = sorted(
        (rasa_dir / "models").glob("*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not trained_models:
        raise RuntimeError("No trained Rasa model found")
    latest = trained_models[0]
    dest = models_dir / latest.name
    shutil.copy(latest, dest)
    print(f"Model copied to {dest}")


if __name__ == "__main__":
    main()
