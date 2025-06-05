"""train_spacy_nlu.py

Utility script to train a spaCy pipeline for intent recognition.
Training data should be provided in `data/nlu/` as a JSONL file with the
format used by spaCy's `spacy train` command. This is a simple example
and can be expanded as needed.
"""

from __future__ import annotations

import pathlib
import spacy
from spacy.util import load_config


def main() -> None:
    base_dir = pathlib.Path.cwd()
    config_path = base_dir / "config" / "spacy_config.cfg"
    data_path = base_dir / "data" / "nlu"
    output_path = base_dir / "models" / "spacy_nlu"

    cfg = load_config(config_path)
    nlp = spacy.util.load_model_from_config(cfg)

    nlp.initialize(lambda: [("train", spacy.tokens.DocBin().from_disk(data_path / "train.spacy")),
                            ("dev", spacy.tokens.DocBin().from_disk(data_path / "dev.spacy"))])

    nlp.to_disk(output_path)
    print(f"spaCy NLU model trained and saved to {output_path}")


if __name__ == "__main__":
    main()

