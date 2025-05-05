# nlp_processor.py
import cohere
import os
from dotenv import load_dotenv
import json
import logging
import dateparser
from datetime import datetime, timedelta
import pytz
try:
    import tzlocal # Use tzlocal for better local timezone detection
except ImportError:
    tzlocal = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("COHERE_API_KEY")
co = None
if API_KEY:
    try: co = cohere.Client(API_KEY); logger.info("Cohere client initialized.")
    except Exception as e: logger.error(f"Failed to initialize Cohere client: {e}", exc_info=True)
else: logger.warning("COHERE_API_KEY not found. NLP disabled.")

INTENTS = ["create_event", "delete_event", "update_event", "list_events", "check_availability", "unknown"]

def get_local_timezone_name():
    """Gets IANA timezone name using tzlocal or fallback."""
    try:
        if tzlocal:
            tz_name = tzlocal.get_localzone_name(); pytz.timezone(tz_name); logger.info(f"Local timezone (tzlocal): {tz_name}"); return tz_name
        else: raise RuntimeError("tzlocal not imported")
    except Exception as e:
        logger.warning(f"tzlocal failed ({e}), using fallback.")
        try: tz_name_fallback = datetime.now().astimezone().tzname(); pytz.timezone(tz_name_fallback); logger.warning(f"Fallback timezone: {tz_name_fallback}"); return tz_name_fallback
        except Exception as e2: logger.error(f"Timezone detection failed ({e2}). Defaulting to UTC."); return 'UTC'

def parse_natural_language_time(time_str, timezone_str=None):
    """Parses natural language time string into aware datetime object."""
    if not time_str: return None
    if not timezone_str: timezone_str = get_local_timezone_name()
    settings = {'PREFER_DATES_FROM': 'future', 'TIMEZONE': timezone_str, 'RETURN_AS_TIMEZONE_AWARE': True}
    try:
        logger.debug(f"Parsing time: '{time_str}' (TZ: {timezone_str})")
        parsed_dt = dateparser.parse(time_str, settings=settings)
        if parsed_dt:
            if parsed_dt.tzinfo is None: # Ensure aware
                 logger.warning(f"Dateparser gave naive dt for '{time_str}', localizing to {timezone_str}")
                 try: local_tz = pytz.timezone(timezone_str); parsed_dt = local_tz.localize(parsed_dt)
                 except Exception as loc_e: logger.error(f"Localization failed: {loc_e}")
            logger.info(f"Parsed '{time_str}' -> {parsed_dt}")
            return parsed_dt
        else: logger.warning(f"Dateparser failed for '{time_str}' (TZ: {timezone_str})"); return None
    except Exception as e: logger.error(f"Dateparser error for '{time_str}': {e}", exc_info=True); return None

def extract_calendar_details(text):
    """Uses Cohere Generate for intent/entity extraction or fallback."""
    if not co: # Fallback if Cohere unavailable
        logger.warning("Cohere unavailable, using basic keyword matching.")
        txt = text.lower()
        if any(k in txt for k in ["create", "schedule", "book", "add"]): return {"intent": "create_event", "original_text": text}
        if any(k in txt for k in ["delete", "cancel", "remove"]): return {"intent": "delete_event", "original_text": text}
        if any(k in txt for k in ["update", "change", "reschedule"]): return {"intent": "update_event", "original_text": text}
        if any(k in txt for k in ["free", "available", "availability"]): return {"intent": "check_availability", "original_text": text}
        if any(k in txt for k in ["what", "show", "list", "events", "calendar", "today", "tomorrow", "week"]): return {"intent": "list_events", "original_text": text}
        return {"intent": "unknown", "original_text": text}

    # Cohere Prompt
    prompt = f"""Analyze the user's calendar request. Identify intent and extract details.
User Request: "{text}"
Possible Intents: {', '.join(INTENTS)}
Desired JSON Output: {{ "intent": "...", "summary": "...", "time_expression": "...", "attendees": ["...", "..."], "target_event_description": "..." }}
Examples:
- User: "schedule meeting with bob@x.com tomorrow 4pm about project" -> {{"intent": "create_event", "summary": "meeting about project", "time_expression": "tomorrow 4pm", "attendees": ["bob@x.com"], "target_event_description": null}}
- User: "cancel budget review next Tuesday" -> {{"intent": "delete_event", "summary": null, "time_expression": "next Tuesday", "attendees": null, "target_event_description": "budget review next Tuesday"}}
- User: "what's on today" -> {{"intent": "list_events", "summary": null, "time_expression": "today", "attendees": null, "target_event_description": null}}
- User: "create event tomorrow 7 pm" -> {{"intent": "create_event", "summary": null, "time_expression": "tomorrow 7 pm", "attendees": null, "target_event_description": null}}
- User: "Am I free this afternoon?" -> {{"intent": "check_availability", "summary": null, "time_expression": "this afternoon", "attendees": null, "target_event_description": null}}
Provide ONLY the JSON object. Use null for missing fields. Use "unknown" intent if unclear.
"""
    try:
        logger.debug("Sending request to Cohere Generate...")
        response = co.generate(model='command-r-plus', prompt=prompt, max_tokens=350, temperature=0.1)
        gen_text = response.generations[0].text.strip()
        logger.debug(f"Cohere raw response:\n{gen_text}")
        json_start, json_end = gen_text.find('{'), gen_text.rfind('}')
        if json_start != -1 and json_end != -1: json_str = gen_text[json_start : json_end + 1]
        else: logger.error(f"No JSON block in Cohere response:\n{gen_text}"); return {"intent": "unknown", "error": "Malformed NLP response"}
        logger.debug(f"Extracted JSON:\n{json_str}")
        data = json.loads(json_str)
        data["original_text"] = text
        if data.get("intent") not in INTENTS: logger.warning(f"Invalid intent '{data.get('intent')}' received."); data["intent"] = "unknown"
        if data.get("time_expression"):
            tz = get_local_timezone_name()
            data["parsed_start_time"] = parse_natural_language_time(data["time_expression"], tz)
            data["used_timezone"] = tz
        else: data["parsed_start_time"], data["used_timezone"] = None, None
        logger.info(f"🧠 NLP Result: {json.dumps(data, indent=2, default=str)}")
        return data
    except json.JSONDecodeError as e: logger.error(f"JSON parse error: {e}\nText: {json_str}", exc_info=True); return {"intent": "unknown", "error": "JSON parse failed"}
    except Exception as e: logger.error(f"Cohere NLP error: {e}", exc_info=True); return {"intent": "unknown", "error": f"NLP error: {e}"}

# if __name__ == '__main__':
#     # ... (testing code) ...