# jarvis/skills/smart_home.py
# -----------------------------------
# Integrates with Home Assistant (via REST API) or direct device libraries (philips Hue, WeMo).
# Handles intents like “turn on living room lights”, “set thermostat to 72 degrees”.
# -----------------------------------

import logging
import requests
from jarvis.config import Config

logger = logging.getLogger(__name__)

def can_handle(intent: str) -> bool:
    return intent in {"turn_on_light", "turn_off_light", "set_thermostat", "get_sensor_status"}

def handle(request: dict) -> dict:
    intent = request.get("intent", "")
    params = request.get("entities", {})
    context = request.get("context", {})
    """
    Uses Home Assistant’s REST API to perform actions. Requires host + token from config.
    """
    cfg = Config()
    ha_host = cfg.get("home_assistant", "host")
    token = cfg.get("home_assistant", "access_token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        if intent in {"turn_on_light", "turn_off_light"}:
            light_name = params.get("device")  # e.g., "living_room_light"
            if not light_name:
                return {"text": "Which light should I control?"}
            action = "turn_on" if intent == "turn_on_light" else "turn_off"
            service = f"/api/services/light/{action}"
            data = {"entity_id": f"light.{light_name}"}
            resp = requests.post(f"{ha_host}{service}", json=data, headers=headers)
            if resp.status_code == 200:
                return {"text": f"{action.replace('_', ' ').capitalize()} {light_name}."}
            else:
                return {"text": f"Failed to {action.replace('_', ' ')} {light_name}."}
        
        elif intent == "set_thermostat":
            temp = params.get("temperature")
            if not temp:
                return {"text": "What temperature should I set the thermostat to?"}
            service = "/api/services/climate/set_temperature"
            # Assuming a default climate entity; modify as needed
            data = {"entity_id": "climate.home_thermostat", "temperature": float(temp)}
            resp = requests.post(f"{ha_host}{service}", json=data, headers=headers)
            if resp.status_code == 200:
                return {"text": f"Thermostat set to {temp}°."}
            else:
                return {"text": f"Couldn’t set thermostat to {temp}°."}
        
        elif intent == "get_sensor_status":
            sensor = params.get("sensor")  # e.g., "front_door"
            if not sensor:
                return {"text": "Which sensor status would you like?"}
            resp = requests.get(f"{ha_host}/api/states/sensor.{sensor}", headers=headers)
            if resp.status_code == 200:
                state = resp.json().get("state")
                return {"text": f"Sensor {sensor} is currently '{state}'."}
            else:
                return {"text": f"Could not retrieve status for {sensor}."}
        
        else:
            return {"text": "Smart home helper received an unknown intent."}
    except Exception as e:
        logger.exception("Error in smart_home.handle: %s", e)
        return {"text": "Sorry, I couldn’t complete the smart home request."}
