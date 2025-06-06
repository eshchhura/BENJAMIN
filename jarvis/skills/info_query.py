# jarvis/skills/info_query.py
# -----------------------------------
# Handles “What's the weather tomorrow?”, “Give me latest news about X”, “Define term Y”:
# uses web APIs (weather, news) or BeautifulSoup scraping.
# -----------------------------------

import logging
import requests
from jarvis.config import Config

logger = logging.getLogger(__name__)

def can_handle(intent: str) -> bool:
    return intent in {"weather_query", "news_query", "define_term"}

def handle(intent: str, params: dict, context: dict) -> str:
    cfg = Config()
    try:
        if intent == "weather_query":
            location = params.get("location", "New York")  # default to config or user location
            api_key = cfg.get("api_keys", "weather")
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={api_key}&units=metric"
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                # Summarize next day’s forecast:
                tomorrow = data["list"][0]  # simplistic: first entry
                temp = tomorrow["main"]["temp"]
                desc = tomorrow["weather"][0]["description"]
                return f"Tomorrow in {location}, it will be {desc} with a temperature of {temp}°C."
            else:
                return f"Could not fetch weather for {location}."
        
        elif intent == "news_query":
            topic = params.get("topic", "")
            if not topic:
                return "What topic would you like the latest news on?"
            # Example: use NewsAPI.org (you need an API key)
            api_key = cfg.get("api_keys", "news_api_key")
            url = f"https://newsapi.org/v2/everything?q={topic}&sortBy=publishedAt&pageSize=3&apiKey={api_key}"
            resp = requests.get(url)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                if not articles:
                    return f"No recent news found for {topic}."
                headlines = [f"• {a['title']} ({a['source']['name']})" for a in articles]
                return "Here are the latest headlines:\n" + "\n".join(headlines)
            else:
                return f"Could not fetch news on {topic}."
        
        elif intent == "define_term":
            term = params.get("term")
            if not term:
                return "Which term would you like me to define?"
            # Example: use dictionaryapi.dev
            resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{term}")
            if resp.status_code == 200:
                meanings = resp.json()[0].get("meanings", [])
                if meanings:
                    definition = meanings[0]["definitions"][0]["definition"]
                    return f"{term.capitalize()}: {definition}"
                else:
                    return f"No definition found for '{term}'."
            else:
                return f"Could not retrieve definition for '{term}'."
        
        else:
            return "Info query helper received an unknown intent."
    except Exception as e:
        logger.exception("Error in info_query.handle: %s", e)
        return "Sorry, I couldn’t complete the information request."
