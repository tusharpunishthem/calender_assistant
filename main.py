# main.py

# --- Standard Library Imports ---
import logging
from datetime import datetime, time, timedelta
import re # Import regex for email parsing

# --- Third-Party Library Imports ---
import pytz  # For timezone handling

# --- Core Application Components ---
try: from calendar_assistant import CalendarAssistant
except ImportError: CalendarAssistant = None; print("❌ FATAL ERROR: Cannot import CalendarAssistant.")
except Exception as e: CalendarAssistant = None; print(f"❌ FATAL ERROR: Importing CalendarAssistant failed: {e}")

NLP_MODULE_NAME = None; extract_calendar_details = None; parse_natural_language_time = None
try: from nlp_processor import extract_calendar_details, parse_natural_language_time; NLP_MODULE_NAME = 'nlp_processor'; print(f"INFO: Using NLP from '{NLP_MODULE_NAME}.py'.")
except ImportError:
    print(f"INFO: Failed import from nlp_processor, trying nlp_parser...")
    try: from nlp_processor import extract_calendar_details, parse_natural_language_time; NLP_MODULE_NAME = 'nlp_parser'; print(f"INFO: Using NLP from '{NLP_MODULE_NAME}.py'.")
    except ImportError: print("❌ FATAL ERROR: Cannot find NLP functions in 'nlp_processor.py' or 'nlp_parser.py'.")
    except Exception as e: print(f"❌ FATAL ERROR: Importing NLP functions failed: {e}")
except Exception as e: print(f"❌ FATAL ERROR: Importing NLP functions failed: {e}")

try: from voice_assistant import VoiceAssistant
except ImportError: VoiceAssistant = None; print("❌ FATAL ERROR: Cannot import VoiceAssistant.")
except Exception as e: VoiceAssistant = None; print(f"❌ FATAL ERROR: Importing VoiceAssistant failed: {e}")


# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DEFAULT_EVENT_DURATION_MINUTES = 60
FREE_SLOT_DURATION_MINUTES = 30
APPROX_SEARCH_RANGE_DAYS = 7

# --- Instantiate Services ---
logger.info("Initializing CalendarAssistant...")
assistant = CalendarAssistant() if CalendarAssistant else None
logger.info("Initializing VoiceAssistant...")
va = VoiceAssistant() if VoiceAssistant else None
USE_VOICE = False # Global flag

# --- Email Regex ---
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# ===================================
# --- HELPER FUNCTIONS ---
# ===================================
def get_datetime_range_for_nlp(time_expression, parsed_start_time, default_range_days=1):
    """Determines timezone-aware start/end datetime range for queries based on NLP output."""
    if not assistant or not assistant.user_timezone: raise ValueError("Assistant timezone unavailable.")
    try: local_tz = pytz.timezone(assistant.user_timezone)
    except pytz.UnknownTimeZoneError: local_tz = pytz.utc; logger.warning(f"Unknown timezone '{assistant.user_timezone}', using UTC.")
    now = datetime.now(local_tz); start_dt, end_dt = None, None
    logger.debug(f"get_dt_range: expr='{time_expression}', parsed={parsed_start_time}")

    if parsed_start_time and isinstance(parsed_start_time, datetime):
        start_dt_base = parsed_start_time.astimezone(local_tz) if parsed_start_time.tzinfo else local_tz.localize(parsed_start_time)
        start_dt = start_dt_base.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
    elif time_expression:
        time_expr_lower = time_expression.lower()
        if "today" in time_expr_lower: start_dt, end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0), now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif "tomorrow" in time_expr_lower: start_dt, end_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0), (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif "week" in time_expr_lower: start_dt, end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday()), now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday()) + timedelta(days=7)
        else:
            if parse_natural_language_time:
                parsed_generic = parse_natural_language_time(time_expression, assistant.user_timezone)
                if parsed_generic and isinstance(parsed_generic, datetime):
                    parsed_aware = parsed_generic.astimezone(local_tz) if parsed_generic.tzinfo else local_tz.localize(parsed_generic)
                    start_dt, end_dt = parsed_aware.replace(hour=0, minute=0, second=0, microsecond=0), parsed_aware.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                else: logger.warning(f"Could not parse generic time expr: '{time_expression}'")
            else: logger.error("NLP time parse function unavailable.")
    if not start_dt: logger.warning(f"No date range derived, defaulting."); start_dt, end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0), now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=default_range_days)
    if start_dt.tzinfo is None: start_dt = local_tz.localize(start_dt)
    if end_dt.tzinfo is None: end_dt = local_tz.localize(end_dt)
    logger.info(f"Determined query range: Start={start_dt.isoformat()}, End={end_dt.isoformat()}")
    return start_dt, end_dt

def confirm_action(prompt):
    """Gets Yes/No confirmation from user. Returns True/False."""
    while True:
        response, full_prompt = None, f"{prompt} (yes/no): "
        if USE_VOICE: full_prompt = f"{prompt} Please say Yes or No."
        try:
            if USE_VOICE and va and va.tts_ready and va.stt_ready: va.speak(full_prompt); response = va.listen(duration=4, prompt="Confirm:")
            elif USE_VOICE: print(f"🤖 Assistant: {full_prompt} (Voice unavailable)"); response = input("Confirm (yes/no): ")
            else: response = input(full_prompt)
            if response:
                resp_low = response.lower().strip()
                affirmative = ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "proceed", "affirmative"]
                negative = ["no", "n", "nope", "negative", "cancel", "don't", "stop"]
                if any(w == resp_low or resp_low.startswith(w) for w in affirmative): logger.info(f"User CONFIRMED: '{prompt}'"); return True
                if any(w == resp_low or resp_low.startswith(w) for w in negative): logger.info(f"User CANCELLED: '{prompt}'"); return False
                speak_output("Sorry, please answer 'yes' or 'no'.")
            elif response is None and USE_VOICE: logger.warning("Confirm listen returned None.")
            elif not response: print("Please provide an answer.")
        except Exception as e: logger.error(f"Error during confirmation: {e}", exc_info=True); speak_output("Error confirming. Assuming 'no'."); return False

def speak_output(text):
    """Handles TTS or printing assistant output."""
    logger.info(f"Assistant Output: {text}")
    if USE_VOICE and va and va.tts_ready: va.speak(text)
    else: print(f"🤖 Assistant: {text}")

# ===================================
# --- INTENT HANDLER FUNCTIONS ---
# ===================================

def handle_create_event(details):
    """Handles 'create_event': Gathers details, prompts ONLY for TEXT attendee input, creates event."""
    logger.info("--- Handling 'create_event' Intent ---")
    if not assistant or not assistant.service: speak_output("Calendar service unavailable."); return "Calendar service unavailable."
    summary, start_dt, time_expr = details.get("summary"), details.get("parsed_start_time"), details.get("time_expression")
    initial_attendees = details.get("attendees") if isinstance(details.get("attendees"), list) else []
    logger.debug(f"Initial details: summary='{summary}', start_dt={start_dt}, NLP attendees={initial_attendees}")
    try:
        if not summary:
            prompt = "What is the title for this event?"; summary_input = (va.listen(prompt=prompt) if USE_VOICE and va and va.stt_ready else input(prompt + " "))
            if not summary_input or summary_input.isspace(): speak_output("Cancelled: No summary."); return "Cancelled (no summary)."
            summary = summary_input.strip(); logger.debug(f"Got summary: {summary}")
        if not start_dt:
            context = f" (Mentioned: '{time_expr}')" if time_expr else ""; prompt = f"When is '{summary}'?{context} (e.g., 'tmw 3pm')"
            time_input = (va.listen(prompt=prompt) if USE_VOICE and va and va.stt_ready else input(prompt + " "))
            if not time_input or time_input.isspace(): speak_output("Cancelled: No start time."); return "Cancelled (no start time)."
            if not parse_natural_language_time: raise RuntimeError("NLP time parser unavailable.")
            start_dt = parse_natural_language_time(time_input, assistant.user_timezone)
            if not start_dt: speak_output(f"Couldn't understand time '{time_input}'."); return f"Failed: Bad time '{time_input}'."
            logger.debug(f"Got start time: {start_dt.isoformat()}")
        end_dt = start_dt + timedelta(minutes=DEFAULT_EVENT_DURATION_MINUTES); logger.info(f"Default end time: {end_dt.isoformat()}")
        final_attendees = []; prompt_text = ""
        if initial_attendees: prompt_text = (f"NLP suggested: {', '.join(initial_attendees)}.\nTYPE final emails (comma/space sep) or Enter to keep: ")
        else: prompt_text = ("TYPE emails to invite (comma/space sep) or Enter for none: ")
        speak_output("Regarding attendees..."); typed_attendee_input = ""
        try: print(f"🤖 Assistant: {prompt_text}", end=''); typed_attendee_input = input().strip()
        except Exception as input_e: logger.error(f"Error getting typed attendee input: {input_e}", exc_info=True); speak_output("Error asking for attendee emails.") # Use speak_output here
        if typed_attendee_input:
            logger.debug(f"Parsing typed input: '{typed_attendee_input}'"); final_attendees = sorted(list(set(EMAIL_REGEX.findall(typed_attendee_input))))
            if final_attendees: speak_output(f"Using typed attendees: {', '.join(final_attendees)}")
            else: speak_output("No valid emails in typed input. None added.")
        elif initial_attendees: final_attendees = initial_attendees; speak_output(f"Keeping suggested attendees: {', '.join(final_attendees)}")
        else: speak_output("No attendees specified."); final_attendees = []
        attendees = final_attendees
    except Exception as gather_e: logger.error(f"Error gathering details: {gather_e}", exc_info=True); speak_output("Error getting details."); return "Error getting details."
    start_str_confirm = start_dt.strftime('%A, %B %d at %I:%M %p %Z'); speak_output(f"Ready to create: '{summary}' starting {start_str_confirm}.")
    try: result_msg, event_info = assistant.create_event(summary, start_dt, end_dt, attendees)
    except Exception as create_e: logger.error(f"Error calling create_event: {create_e}", exc_info=True); speak_output("Error creating on calendar."); return "Internal error creating."
    if "CONFLICT" in result_msg: speak_output(result_msg); speak_output("Cancelled due to conflict."); logger.warning(f"Create cancelled (conflict): '{summary}'"); return "Cancelled (conflict)."
    if "Error" in result_msg or event_info is None: speak_output(f"Failed: {result_msg}"); logger.error(f"Failed create '{summary}': {result_msg}"); return f"Failed: {result_msg}"
    speak_output(result_msg); logger.info(f"Success create '{summary}'. Link: {event_info}"); return result_msg

def handle_list_events(details):
    """Handles 'list_events' intent."""
    logger.info("--- Handling 'list_events' Intent ---")
    if not assistant or not assistant.service: speak_output("Calendar service unavailable."); return "Calendar service unavailable."
    time_expr, parsed_start = details.get("time_expression"), details.get("parsed_start_time")
    try: start_dt, end_dt = get_datetime_range_for_nlp(time_expr, parsed_start)
    except Exception as e: logger.error(f"Err det range: {e}", exc_info=True); speak_output("Error determining date range."); return "Error determining date range."
    range_fmt = '%A, %b %d'; speak_output(f"Looking for events from {start_dt.strftime(range_fmt)} until {end_dt.strftime(range_fmt)}...")
    try: events_list = assistant.list_events(start_dt, end_dt)
    except Exception as e: logger.error(f"Err list_events: {e}", exc_info=True); speak_output("Error fetching events."); return "Internal error listing."
    if not events_list: speak_output("Couldn't retrieve info."); return "Error: Empty list."
    if "Error" in events_list[0]: speak_output(f"Error listing: {events_list[0]}"); return events_list[0]
    if "No events found" in events_list[0]: speak_output(events_list[0]); return events_list[0]
    speak_output("Found these events:"); output_lines = []
    for event_str in events_list: speak_output(event_str); output_lines.append(event_str)
    return "\n".join(output_lines)

def handle_check_availability(details):
    """Handles 'check_availability' intent."""
    logger.info("--- Handling 'check_availability' Intent ---")
    if not assistant or not assistant.service: speak_output("Calendar service unavailable."); return "Calendar service unavailable."
    time_expr, parsed_start = details.get("time_expression"), details.get("parsed_start_time")
    try: check_date_start, _ = get_datetime_range_for_nlp(time_expr, parsed_start, default_range_days=1)
    except Exception as e: logger.error(f"Err det range: {e}", exc_info=True); speak_output("Error determining date range."); return "Error determining date range."
    day_start, day_end = check_date_start.replace(hour=0, minute=0, second=0, microsecond=0), check_date_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    speak_output(f"Checking {FREE_SLOT_DURATION_MINUTES}-min slots on {day_start.strftime('%A, %B %d')}...")
    try: free_slots = assistant.find_free_slots(day_start, day_end, FREE_SLOT_DURATION_MINUTES)
    except Exception as e: logger.error(f"Err find_free_slots: {e}", exc_info=True); speak_output("Error checking availability."); return "Internal error checking availability."
    if not free_slots: speak_output("Couldn't retrieve availability."); return "Error: Empty list."
    if "Error" in free_slots[0]: speak_output(f"Error checking: {free_slots[0]}"); return free_slots[0]
    if "No free" in free_slots[0]: speak_output(free_slots[0]); return free_slots[0]
    speak_output(f"Found available {FREE_SLOT_DURATION_MINUTES}-minute slots:"); output_lines = []
    for slot_str in free_slots: speak_output(slot_str); output_lines.append(slot_str)
    return "\n".join(output_lines)

def handle_delete_event(details):
    """Handles 'delete_event' intent."""
    logger.info("--- Handling 'delete_event' Intent ---")
    if not assistant or not assistant.service: speak_output("Calendar service unavailable."); return "Calendar service unavailable."
    target_desc, time_expr, parsed_start = details.get("target_event_description"), details.get("time_expression"), details.get("parsed_start_time")
    if not target_desc:
        prompt = "Which event to delete? Describe it:"; target_input = (va.listen(prompt=prompt) if USE_VOICE and va else input(prompt + " "))
        if not target_input or target_input.isspace(): speak_output("Delete cancelled: No event specified."); return "Delete cancelled."
        target_desc = target_input.strip()
    try: start_approx, end_approx = get_datetime_range_for_nlp(time_expr, parsed_start, default_range_days=APPROX_SEARCH_RANGE_DAYS); start_search, end_search = start_approx - timedelta(days=max(1, APPROX_SEARCH_RANGE_DAYS // 2)), end_approx + timedelta(days=max(1, APPROX_SEARCH_RANGE_DAYS // 2) + 1)
    except Exception as e: logger.error(f"Err det range: {e}", exc_info=True); speak_output("Error determining search range."); return "Error determining search range."
    speak_output(f"Looking for event '{target_desc}' around {start_approx.strftime('%B %d')}...")
    try: event_id, find_msg = assistant.find_event_id(target_desc, start_search, end_search)
    except Exception as e: logger.error(f"Err find_event_id: {e}", exc_info=True); speak_output("Error searching."); return "Internal error during search."
    speak_output(find_msg)
    if event_id:
         summary_confirm = target_desc;
         if "Found event: 📌" in find_msg:
             try: summary_confirm = find_msg.split('📌 ')[1].split(' at ')[0].split(' (All day')[0].strip()
             except IndexError: pass
         if confirm_action(f"Delete '{summary_confirm}'?"):
             speak_output("Deleting...");
             try: delete_msg = assistant.delete_event(event_id); speak_output(delete_msg); return delete_msg
             except Exception as e: logger.error(f"Err delete_event: {e}", exc_info=True); speak_output("Error deleting."); return "Internal error during deletion."
         else: speak_output("Okay, delete cancelled."); return "Delete cancelled by user."
    else: return find_msg

def handle_update_event(details):
    """Handles 'update_event' intent (Placeholder)."""
    logger.info("--- Handling 'update_event' Intent (Not Implemented) ---")
    speak_output("Sorry, updating events isn't implemented yet. Please delete and recreate.")
    return "Update functionality not implemented."

# =======================================
# --- MAIN COMMAND PROCESSING LOGIC ---
# =======================================
def process_command(user_input):
    """Processes user input: NLP -> Intent Routing -> Handler Execution."""
    # --- CORRECTED INPUT CHECK ---
    if not user_input or user_input.isspace():
        logger.warning("process_command received empty or whitespace input.")
        # Conditionally speak feedback ONLY if in voice mode
        if USE_VOICE:
            speak_output("No command received.")
        # ALWAYS return the status message if the input was empty
        return "Input received was empty."
    # --- END CORRECTION ---

    logger.info(f"Processing Input: '{user_input}'"); print(f"\n👤 User: {user_input}")
    if not extract_calendar_details: logger.critical("NLP unavailable."); speak_output("Language processing unavailable."); return "NLP unavailable."
    try: details = extract_calendar_details(user_input); logger.debug(f"NLP Result: {details}")
    except Exception as e: logger.error(f"NLP error: {e}", exc_info=True); speak_output("Error understanding request."); return "NLP error."
    intent = details.get("intent"); logger.info(f"Intent: {intent}"); print(f"🧠 Intent: {intent}")
    if not intent or intent == "unknown" or "error" in details:
         error_msg = details.get('error', 'Could not determine action.'); speak_output(f"Sorry, couldn't understand. {error_msg}"); logger.error(f"NLP Error/Unknown: {error_msg}. Details: {details}"); return f"NLP Error: {error_msg}"
    handler_map = {"create_event": handle_create_event, "list_events": handle_list_events, "check_availability": handle_check_availability, "delete_event": handle_delete_event, "update_event": handle_update_event}
    handler = handler_map.get(intent)
    if handler:
        logger.info(f"Executing handler: {handler.__name__}")
        try: return handler(details)
        except Exception as e: logger.error(f"Error in handler '{handler.__name__}': {e}", exc_info=True); speak_output(f"Error processing '{intent}'. Check logs."); return f"Handler error for {intent}."
    else: logger.error(f"No handler for valid intent '{intent}'"); speak_output(f"Action '{intent}' not implemented."); return f"Unhandled intent: '{intent}'."

# ==============================
# --- MAIN APPLICATION LOOP ---
# ==============================
def main_loop():
    """Runs the main interaction loop."""
    global USE_VOICE; logger.info("Application main_loop starting.")
    essentials = {"Calendar Assistant": assistant, "Calendar Service": getattr(assistant, 'service', None), "NLP Extract": extract_calendar_details, "NLP Parse Time": parse_natural_language_time, "Voice Class": VoiceAssistant, "Voice Instance": va}
    if not all(essentials.values()):
        print("\n❌ FATAL ERROR: Essential components failed:"); [print(f"   - {k}: {'OK' if v else 'FAILED'}") for k, v in essentials.items()]; print("   Application cannot start."); logger.critical("Essential components failed."); return
    stt_ready, tts_ready = bool(va and va.stt_ready), bool(va and va.tts_ready); voice_ready = stt_ready and tts_ready
    if not stt_ready: print("\n⚠️ WARNING: STT unavailable.")
    if not tts_ready: print("\n⚠️ WARNING: TTS unavailable.")
    speak_output("Hello! I'm your Calendar Assistant. How can I help?")
    while True:
        print("\n" + "="*40); can_use_voice = voice_ready; prompt = "[1] Text" + (" [2] Voice" if can_use_voice else "") + " [3] Exit: "; choice = input(prompt).strip()
        if choice == '1': USE_VOICE = False; speak_output("Using text."); user_text = input("You: ").strip(); (process_command(user_text) if user_text else speak_output("No command entered."))
        elif choice == '2' and can_use_voice: USE_VOICE = True; speak_output("Using voice."); user_speech = va.listen(); (process_command(user_speech) if user_speech else None)
        elif choice == '2' and not can_use_voice: print("Voice mode unavailable.")
        elif choice == '3': speak_output("Goodbye!"); logger.info("Exiting via user choice."); break
        else: print("Invalid choice (1, 2, or 3).")

# --- Script Entry Point ---
if __name__ == "__main__":
    logger.info("================ Application Starting ================")
    try:
        if all([assistant, va, extract_calendar_details, parse_natural_language_time, VoiceAssistant]): main_loop()
        else: logger.critical("Essential checks failed. Cannot start."); print("\nApp cannot start due to init errors.")
    except Exception as main_e: logger.critical(f"Uncaught exception: {main_e}", exc_info=True); print(f"\n🚨 CRITICAL ERROR: {main_e}\n   Check logs.")
    finally: logger.info("================ Application Finished ================")