"""
train_nlu.py

Script to train or update the NLU pipeline (e.g., Rasa) on the assistant’s intents/entities.
"""

import os
import sys
from rasa.model import train  # Rasa training API (example)

def main():
    """
    1. Ensure all NLU training data is in 'data/nlu/'.
    2. Run `rasa train nlu` or equivalent.
    3. Save the generated model under `models/`.
    """
    data_path = os.path.join(os.getcwd(), "data", "nlu")
    config_path = os.path.join(os.getcwd(), "config", "config.yaml")  # Rasa config may be integrated here
    output_path = os.path.join(os.getcwd(), "models", "nlu_model")
    # Example: rasa train nlu -c config/rasa_nlu.yml -u data/nlu -o models
    train(
        domain="domain.yml",
        config="config/rasa_config.yml",
        training_files=data_path,
        output=output_path
    )
    print(f"NLU model trained and saved to {output_path}")

if __name__ == "__main__":
    main()
