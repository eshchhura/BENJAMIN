# Jarvis Assistant (Python-Based)

**Overview:**  
This repository contains a modular, “Jarvis-style” personal assistant that supports voice and terminal interaction, intent recognition, skill modules (file management, scheduling, coding help, smart home control, information queries), continuous learning (pattern mining & RL), and persistent memory (short-term & long-term).

**Directory Structure:**  
- `config/`             : YAML configurations (general settings, logging).  
- `scripts/`            : Utility scripts (e.g., launching Jarvis, training models).  
- `jarvis/`             : Main source code (interfaces, NLU, skills, memory, learning, utils).  
- `tests/`              : Unit tests for core components.  

**Getting Started:**  
1. Create a virtual environment (e.g., `python3 -m venv venv && source venv/bin/activate`).  
2. Install dependencies: `pip install -r requirements.txt`.  
3. Populate `config/config.yaml` with your API keys, device names, etc.
4. To try a simple chat window run: `python -m jarvis` or `python -m jarvis.chat_app`.
   Voice/terminal mode is still available via `bash scripts/run_jarvis.sh`.
5. Train the spaCy based NLU model with `python scripts/train_spacy_nlu.py` (optional).

**Modules Breakdown:**  
- `interfaces/`         : Voice & terminal I/O, wake-word listening.
- `nlu/`                : spaCy-based intent classification & dialogue state.
- `skills/`             : Feature-specific modules.
- `memory/`             : Short-term & long-term memory backends.  
- `learning/`           : Online pattern mining & reinforcement learning for proactive behaviors.  
- `utils/`              : Logging, common helpers.  

For more details, see `docs/` (design documents, architecture diagrams).

## Running Tests
Before executing the test suite, make sure all dependencies are installed:

```
pip install -r requirements.txt
```

Then run the tests with:

```
pytest
```
