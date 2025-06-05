# jarvis/skills/file_manager.py
# -----------------------------------
# Handles intents like “open file X”, “list files in folder Y”, “move file A to B”.
# Uses Python’s os, shutil, subprocess for platform-agnostic file operations.
# -----------------------------------

import os
import shutil
import subprocess
import logging
from jarvis.config import Config

logger = logging.getLogger(__name__)

def can_handle(intent: str) -> bool:
    """
    Return True if this module supports the given intent.
    Example intents: 'open_file', 'search_file', 'move_file'
    """
    return intent in {"open_file", "search_file", "move_file"}

def handle(intent: str, params: dict, context: dict) -> str:
    """
    Execute file operations based on intent and parameters.
    Args:
        intent: The recognized intent name (e.g., 'open_file')
        params: Extracted entities (e.g., {'file_name': 'report.docx'})
        context: Dialogue context (unused here but may contain defaults, cwd, etc.)
    Returns:
        A user-friendly response string to speak/print.
    """
    base_dir = os.getcwd()  # Example: use project root or config value
    try:
        if intent == "open_file":
            filename = params.get("file_name")
            if not filename:
                return "Please specify which file you want to open."
            file_path = os.path.join(base_dir, filename)
            if not os.path.exists(file_path):
                return f"I couldn't find a file named {filename}."
            # Cross-platform open:
            if os.name == "nt":  # Windows
                os.startfile(file_path)
            elif os.uname().sysname == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux and others
                subprocess.run(["xdg-open", file_path])
            return f"Opened file {filename}."
        
        elif intent == "search_file":
            query = params.get("query")
            if not query:
                return "Please tell me what filename or pattern to search for."
            matches = []
            for root, dirs, files in os.walk(base_dir):
                for f in files:
                    if query.lower() in f.lower():
                        matches.append(os.path.join(root, f))
            if not matches:
                return f"No files matching '{query}' were found."
            # Return up to 3 matches
            response = "Here are some files I found:\n" + "\n".join(matches[:3])
            return response

        elif intent == "move_file":
            src = params.get("source")
            dest = params.get("destination")
            if not src or not dest:
                return "I need both a source and a destination to move a file."
            src_path = os.path.join(base_dir, src)
            dest_path = os.path.join(base_dir, dest)
            if not os.path.exists(src_path):
                return f"I couldn't find {src} to move."
            # Ensure destination folder exists
            dest_folder = os.path.dirname(dest_path)
            if not os.path.isdir(dest_folder):
                os.makedirs(dest_folder, exist_ok=True)
            shutil.move(src_path, dest_path)
            return f"Moved {src} to {dest}."
        
        else:
            return "File manager received an unknown intent."
    except Exception as e:
        logger.exception("Error in file_manager.handle: %s", e)
        return "Oops, something went wrong while handling your file request."
