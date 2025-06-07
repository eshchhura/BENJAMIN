# jarvis/skills/coding_helper.py
# -----------------------------------
# Provides code assistance: e.g., “fix this error”, “generate boilerplate for a Flask app”,
# “explain this traceback”. Can integrate a local code LLM (StarCoder, CodeGen) or use Howdoi.
# -----------------------------------

import subprocess
import logging

logger = logging.getLogger(__name__)

def can_handle(intent: str) -> bool:
    return intent in {"explain_error", "generate_code", "search_stackoverflow"}

def handle(request: dict) -> dict:
    intent = request.get("intent", "")
    params = request.get("entities", {})
    context = request.get("context", {})
    """
    - explain_error: expects 'error_message' entity
    - generate_code: expects 'framework' or 'task' entity (e.g., 'flask_api')
    - search_stackoverflow: expects 'question' entity
    Returns a textual explanation or code snippet.
    """
    try:
        if intent == "explain_error":
            err = params.get("error_message")
            if not err:
                return {"text": "Please tell me the error message you want me to explain."}
            # Simple heuristic: run a web search or local knowledge base?
            # For now, echo back.
            return {"text": f"The error '{err}' indicates ... [stub explanation]."}
        
        elif intent == "generate_code":
            task = params.get("task")
            if not task:
                return {"text": "Please specify what code you want generated (e.g., 'Flask app')."}
            # Example: call a local code LLM via CLI or Python API
            # subprocess.run(["starcoder", "--prompt", f"Generate {task} code"])
            return {"text": f"Here is a boilerplate for {task}:\n\n```python\n# [stub code]```"}

        elif intent == "search_stackoverflow":
            question = params.get("question")
            if not question:
                return {"text": "What programming question should I search on Stack Overflow?"}
            # Use Howdoi: pip install howdoi
            try:
                output = subprocess.check_output(["howdoi", question, "--num_answers", "1"])
                return {"text": output.decode("utf-8")}
            except Exception:
                return {"text": "I couldn't fetch an answer from Stack Overflow right now."}
        
        else:
            return {"text": "Coding helper received an unknown intent."}
    except Exception as e:
        logger.exception("Error in coding_helper.handle: %s", e)
        return {"text": "An error occurred while processing your coding request."}
