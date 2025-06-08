#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Simple launcher script for Benjamin assistant.
# -----------------------------------------------------------------------------

# Activate virtual environment (adjust path if needed):
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
elif [ -f "env/bin/activate" ]; then
  source env/bin/activate
else
  echo "Warning: no virtual environment found. Proceeding with system Python."
fi

# Export environment variables if using python-dotenv:
# export $(grep -v '^#' .env | xargs)

# Run the main entry point
python -m jarvis.main
