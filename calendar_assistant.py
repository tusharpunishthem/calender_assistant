# calendar_assistant.py

# --- Standard Library Imports ---
from datetime import datetime, timedelta, date # Import specific classes needed
import os.path
import logging

# --- Third-Party Library Imports ---
import pytz
from dateutil import parser as dateutil_parser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# === CORRECTED Google API Imports ===
from googleapiclient.discovery import build
from googleapiclient import errors # Import errors from the correct location
# ====================================


# --- Local Application Imports ---
try:
    from gmail import GmailNotifier
except ImportError:
    GmailNotifier = None
    logging.warning("gmail_notifier.py not found or failed to import. Email notifications disabled.")
except Exception as e:
     GmailNotifier = None
     logging.error(f"Error importing GmailNotifier: {e}", exc_info=True)


# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_JSON_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

# --- CalendarAssistant Class Definition ---
class CalendarAssistant:
    """Manages interactions with the Google Calendar API."""
    def __init__(self):
        """Initializes connection to Google Calendar API and Gmail Notifier."""
        self.creds = self._authenticate()
        self.service = None
        self.user_timezone = 'UTC'
        self.notifier = None

        if self.creds:
            try:
                self.service = build('calendar', 'v3', credentials=self.creds)
                logger.info("Google Calendar service built successfully.")
                self.user_timezone = self._get_user_timezone()
            except Exception as e:
                logger.error(f"Failed to build Google Calendar service: {e}", exc_info=True)
                self.service = None
        else:
            logger.error("Authentication failed, credentials not obtained.")

        if GmailNotifier:
            logger.info("Initializing GmailNotifier...")
            try:
                self.notifier = GmailNotifier()
                if not self.notifier.service:
                    logger.warning("GmailNotifier failed to authenticate service.")
            except Exception as e:
                 logger.error(f"Error initializing GmailNotifier: {e}", exc_info=True)
                 self.notifier = None
        else:
             logger.warning("GmailNotifier class not available.")

        if not self.service:
            logger.error("Calendar service initialization failed.")

    # --- Authentication Method ---
    def _authenticate(self):
        """Handles Google OAuth 2.0 authentication flow."""
        creds = None
        if os.path.exists(TOKEN_JSON_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_JSON_FILE, SCOPES)
                logger.debug("Loaded credentials from token.json")
            except Exception as e:
                 logger.warning(f"Error loading {TOKEN_JSON_FILE}: {e}. Re-authenticating.")
                 creds = None

        if not creds or not creds.valid:
            needs_refresh = creds and creds.expired and creds.refresh_token
            if needs_refresh:
                logger.info("Refreshing Calendar API token...")
                try:
                    creds.refresh(Request())
                    logger.info("Token refreshed successfully.")
                    try: # Save refreshed token
                        with open(TOKEN_JSON_FILE, 'w') as token: token.write(creds.to_json())
                        logger.info(f"Refreshed token saved to {TOKEN_JSON_FILE}")
                    except Exception as save_e: logger.error(f"Error saving refreshed token: {save_e}")
                except Exception as e:
                    logger.error(f"Error refreshing token: {e}. Re-authenticating.", exc_info=True)
                    if os.path.exists(TOKEN_JSON_FILE):
                        try: os.remove(TOKEN_JSON_FILE)
                        except OSError as del_e: logger.error(f"Failed to remove token file: {del_e}")
                    creds = None

            if not creds or not creds.valid:
                logger.info("Starting OAuth flow...")
                if not os.path.exists(CREDENTIALS_FILE):
                     logger.critical(f"{CREDENTIALS_FILE} not found.")
                     raise FileNotFoundError(f"{CREDENTIALS_FILE} required.")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0, prompt='consent', authorization_prompt_message='Please authorize Calendar access:')
                    logger.info("OAuth flow completed.")
                    try: # Save new credentials
                        with open(TOKEN_JSON_FILE, 'w') as token: token.write(creds.to_json())
                        logger.info(f"New credentials saved to {TOKEN_JSON_FILE}")
                    except Exception as save_e: logger.error(f"Error saving new token: {save_e}")
                except Exception as e:
                     logger.error(f"OAuth flow failed: {e}", exc_info=True)
                     return None

        if not creds or not creds.valid:
             logger.error("Failed to obtain valid credentials.")
             return None
        return creds

    # --- Timezone Helper ---
    def _get_user_timezone(self):
        """Fetches and validates the primary calendar's timezone setting."""
        if not self.service: return 'UTC'
        try:
            logger.debug("Fetching calendar timezone setting...")
            settings = self.service.settings().get(setting='timezone').execute()
            tz = settings.get('value')
            if tz:
                try: # Validate
                    pytz.timezone(tz)
                    logger.info(f"Detected calendar timezone: {tz}")
                    return tz
                except pytz.UnknownTimeZoneError:
                    logger.warning(f"Unknown timezone '{tz}'. Defaulting to UTC.")
                    return 'UTC'
            else:
                 logger.warning("Could not retrieve timezone setting. Defaulting to UTC.")
                 return 'UTC'
        except errors.HttpError as e: logger.error(f"API Error fetching timezone: {e}"); return 'UTC'
        except Exception as e: logger.error(f"Error fetching timezone: {e}", exc_info=True); return 'UTC'

    # --- Datetime Formatting Helper ---
    def _format_datetime_for_api(self, dt_obj):
        """Converts aware/naive datetime to API-compatible ISO string."""
        if not isinstance(dt_obj, datetime): raise TypeError("Input must be datetime")
        try: local_tz = pytz.timezone(self.user_timezone)
        except pytz.UnknownTimeZoneError: local_tz = pytz.utc; logger.warning("Unknown timezone, using UTC.")

        if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None: dt_aware = local_tz.localize(dt_obj)
        else: dt_aware = dt_obj.astimezone(local_tz)

        iso_format_string = dt_aware.isoformat()
        logger.debug(f"Formatted datetime for API: {iso_format_string}")
        return iso_format_string

    # --- Event Time Parsing Helper ---
    def _parse_event_time(self, event_time_dict):
        """Parses Google API time dict to aware datetime or date."""
        dt_str = event_time_dict.get('dateTime')
        date_str = event_time_dict.get('date')
        if dt_str:
            try:
                dt = dateutil_parser.isoparse(dt_str)
                local_tz = pytz.timezone(self.user_timezone)
                return dt.astimezone(local_tz)
            except Exception as e: logger.error(f"Error parsing dateTime '{dt_str}': {e}"); return dt_str
        elif date_str:
             try: return date.fromisoformat(date_str)
             except ValueError: logger.error(f"Error parsing date '{date_str}'"); return date_str
        else: logger.warning("Event time dict missing dateTime/date."); return "N/A"

    # --- Event Display Formatting Helper ---
    def _format_event_display(self, event):
        """Formats event dict into readable string."""
        summary = event.get('summary', 'No Title')
        start = self._parse_event_time(event.get('start', {}))
        end = self._parse_event_time(event.get('end', {}))

        start_fmt = "N/A"
        if isinstance(start, datetime): start_fmt = start.strftime('%a, %b %d, %Y at %I:%M %p %Z')
        elif isinstance(start, date): start_fmt = start.strftime('%a, %b %d, %Y')
        elif isinstance(start, str): start_fmt = start

        end_fmt = ""
        if isinstance(end, datetime):
             if isinstance(start, datetime) and end.date() == start.date(): end_fmt = end.strftime('%I:%M %p %Z')
             else: end_fmt = end.strftime('%a, %b %d, %Y at %I:%M %p %Z')

        if isinstance(start, date): return f"📌 {summary} (All day: {start_fmt})"
        else: return f"📌 {summary} ({start_fmt}{f' until {end_fmt}' if end_fmt else ''})"

    # --- Core Calendar Operations ---
    def list_events(self, start_dt, end_dt):
        """Lists events in a datetime range."""
        if not self.service: return ["Error: Calendar service unavailable."]
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime): return ["Error: Invalid date range."]
        try: start_iso, end_iso = self._format_datetime_for_api(start_dt), self._format_datetime_for_api(end_dt)
        except Exception as e: return [f"Error preparing request: {e}"]
        logger.info(f"Fetching events from {start_iso} to {end_iso}")
        try:
            res = self.service.events().list(calendarId='primary', timeMin=start_iso, timeMax=end_iso, singleEvents=True, orderBy='startTime').execute()
            items = res.get('items', [])
            if not items:
                start_msg, end_msg = start_dt.strftime('%b %d'), end_dt.strftime('%b %d, %Y')
                return [f"📭 No events found ({start_msg} - {end_msg})."]
            return [self._format_event_display(e) for e in items]
        except errors.HttpError as e: logger.error(f"API Error listing: {e}"); return [f"API Error: {e}"]
        except Exception as e: logger.error(f"Error listing: {e}", exc_info=True); return [f"Unexpected error: {e}"]

    def check_overlap(self, start_dt, end_dt):
        """Checks for overlaps using free/busy."""
        if not self.service: return ["Error: Calendar service unavailable."]
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime): return ["Error: Invalid date range."]
        try: start_iso, end_iso = self._format_datetime_for_api(start_dt), self._format_datetime_for_api(end_dt)
        except Exception as e: return [f"Error preparing request: {e}"]
        logger.info(f"Checking overlaps: {start_iso} to {end_iso}")
        try:
            query = {"timeMin": start_iso, "timeMax": end_iso, "timeZone": self.user_timezone, "items": [{"id": "primary"}]}
            res = self.service.freebusy().query(body=query).execute()
            busy = res.get('calendars', {}).get('primary', {}).get('busy', [])
            if not busy: logger.debug("No overlap found."); return []
            logger.info(f"Overlap detected ({len(busy)} interval(s)). Fetching details...")
            details = self.list_events(start_dt, end_dt)
            return [e for e in details if not e.startswith(("API Error", "No events found"))] # Filter errors
        except errors.HttpError as e: logger.error(f"API Error checking overlap: {e}"); return [f"API Error checking overlap: {e}"]
        except Exception as e: logger.error(f"Error checking overlap: {e}", exc_info=True); return [f"Unexpected error checking overlap: {e}"]

    def create_event(self, summary, start_dt, end_dt, attendees=None, description=None, location=None):
        """Creates event, handles overlaps & notifications."""
        logger.info(f"Create request: '{summary}' {start_dt} -> {end_dt}")
        if not self.service: return "Service unavailable.", None
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime): return "Invalid time format.", None
        if start_dt >= end_dt: return "Start must be before end.", None
        attendees = attendees or []

        try: # Check overlap first
            overlaps = self.check_overlap(start_dt, end_dt)
            if overlaps and not overlaps[0].startswith("Error"):
                details = "\n".join(overlaps)
                logger.warning(f"Conflict detected for '{summary}':\n{details}")
                return f"CONFLICT: Time overlaps with:\n{details}", None
            elif overlaps and overlaps[0].startswith("Error"):
                logger.error(f"Overlap check failed: {overlaps[0]}. Proceeding.")
        except Exception as e: return f"Error checking conflicts: {e}", None

        try: # Prepare body
            start_iso, end_iso = self._format_datetime_for_api(start_dt), self._format_datetime_for_api(end_dt)
            body = {
                'summary': summary, 'location': location or "", 'description': description or "",
                'start': {'dateTime': start_iso, 'timeZone': self.user_timezone},
                'end': {'dateTime': end_iso, 'timeZone': self.user_timezone},
                'attendees': [{'email': e.strip()} for e in attendees if isinstance(e, str) and '@' in e],
                'reminders': {'useDefault': True},
            }
            logger.debug(f"Event body: {body}")
        except Exception as e: return f"Error formatting event data: {e}", None

        try: # Insert event
            logger.info(f"Sending insert request for '{summary}'...")
            created = self.service.events().insert(calendarId='primary', body=body, sendNotifications=True, sendUpdates='all').execute()
            link = created.get('htmlLink', 'N/A')
            eid = created.get('id')
            logger.info(f"Event '{summary}' created. ID: {eid}, Link: {link}")

            # Optional Email Notification
            if self.notifier and self.notifier.service:
                 logger.info("Sending additional email notification...")
                 subject = f"Calendar Event: {summary}"
                 start_str, end_str = start_dt.strftime('%c %Z'), end_dt.strftime('%I:%M %p %Z')
                 email_body = (f"Event scheduled:\n\nTitle: {summary}\nTime: {start_str} - {end_str}\n"
                               f"Desc: {body['description']}\nLocation: {body['location']}\n"
                               f"Attendees: {', '.join([a['email'] for a in body['attendees']]) or 'None'}\n\nLink: {link}")
                 recipients = list(set([a['email'] for a in body['attendees']]))
                 if recipients:
                     try:
                         sent = self.notifier.send_email_notification(recipients, subject, email_body)
                         logger.info(f"Additional email sent status: {sent}")
                     except Exception as email_e: logger.error(f"GmailNotifier error: {email_e}", exc_info=True)
                 else: logger.info("No attendees for additional email.")
            else: logger.info("GmailNotifier unavailable, skipping additional email.")

            return f"✅ Event '{summary}' created!", link
        except errors.HttpError as e: logger.error(f"API Error creating: {e}"); return f"API Error ({e.resp.status}): {e}", None
        except Exception as e: logger.error(f"Error creating: {e}", exc_info=True); return f"Unexpected error: {e}", None

    def find_event_id(self, search_term, start_dt, end_dt):
        """Finds event ID by search term and date range."""
        if not self.service: return None, "Service unavailable."
        if not search_term: return None, "Search term required."
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime): return None, "Invalid date range."
        try: start_iso, end_iso = self._format_datetime_for_api(start_dt), self._format_datetime_for_api(end_dt)
        except Exception as e: return None, f"Error preparing request: {e}"
        logger.info(f"Searching for '{search_term}' ({start_iso} - {end_iso})")
        try:
            res = self.service.events().list(calendarId='primary', timeMin=start_iso, timeMax=end_iso, q=search_term, singleEvents=True, maxResults=10).execute()
            items = res.get('items', [])
            if not items: return None, f"❓ No event found matching '{search_term}'."
            if len(items) > 1:
                logger.warning(f"Multiple ({len(items)}) matches for '{search_term}'.")
                list_str = "\n".join([f"  {i+1}. {self._format_event_display(e)}" for i, e in enumerate(items)])
                first_disp = self._format_event_display(items[0])
                return items[0].get('id'), f"⚠️ Found multiple matches. Using first:\n  1. {first_disp}\n\nOthers:\n{list_str}"
            event = items[0]; disp = self._format_event_display(event)
            logger.info(f"Found unique event: ID={event.get('id')}, Summary='{event.get('summary')}'")
            return event.get('id'), f"✅ Found event: {disp}"
        except errors.HttpError as e: logger.error(f"API Error finding: {e}"); return None, f"API Error: {e}"
        except Exception as e: logger.error(f"Error finding: {e}", exc_info=True); return None, f"Unexpected error: {e}"

    def delete_event(self, event_id):
        """Deletes event by ID."""
        if not self.service: return "Service unavailable."
        if not event_id: return "Event ID required."
        logger.info(f"Attempting delete: ID={event_id}")
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id, sendNotifications=True).execute()
            logger.info(f"Event {event_id} deleted via API.")
            return "✅ Event deleted."
        except errors.HttpError as e:
            if e.resp.status in [404, 410]: logger.warning(f"Event {event_id} not found/gone ({e.resp.status})."); return "Error: Event not found/already deleted."
            else: logger.error(f"API Error deleting {event_id}: {e}"); return f"API Error: {e}"
        except Exception as e: logger.error(f"Error deleting {event_id}: {e}", exc_info=True); return f"Unexpected error: {e}"

    def update_event(self, event_id, updates):
        """Updates event (Placeholder)."""
        if not self.service: return "Service unavailable.", None
        if not event_id: return "Event ID required.", None
        if not updates: return "Updates required.", None
        logger.warning(f"--- update_event called for ID {event_id} (Not Implemented) ---")
        logger.warning(f"Updates: {updates}")
        return "Update function not implemented.", None # Placeholder

    def find_free_slots(self, start_dt, end_dt, duration_minutes=30):
        """Finds available slots using free/busy."""
        if not self.service: return ["Error: Service unavailable."]
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime): return ["Error: Invalid date range."]
        if start_dt >= end_dt: return ["Error: Start >= End."]
        if duration_minutes <= 0: return ["Error: Duration must be > 0."]
        try: start_iso, end_iso = self._format_datetime_for_api(start_dt), self._format_datetime_for_api(end_dt)
        except Exception as e: return [f"Error preparing request: {e}"]
        logger.info(f"Finding {duration_minutes}-min slots ({start_iso} - {end_iso})")
        try:
            query = {"timeMin": start_iso, "timeMax": end_iso, "timeZone": self.user_timezone, "items": [{"id": "primary"}]}
            res = self.service.freebusy().query(body=query).execute()
            busy = res.get('calendars', {}).get('primary', {}).get('busy', [])
            logger.debug(f"Busy intervals: {busy}")

            free_slots = []
            try: local_tz = pytz.timezone(self.user_timezone)
            except pytz.UnknownTimeZoneError: local_tz = pytz.utc
            current_search = start_dt.astimezone(local_tz) if start_dt.tzinfo else local_tz.localize(start_dt)
            search_end = end_dt.astimezone(local_tz) if end_dt.tzinfo else local_tz.localize(end_dt)
            slot_delta = timedelta(minutes=duration_minutes)
            busy_times = []
            for interval in busy:
                try:
                    b_start = dateutil_parser.isoparse(interval['start']).astimezone(local_tz)
                    b_end = dateutil_parser.isoparse(interval['end']).astimezone(local_tz)
                    if b_end > b_start: busy_times.append((b_start, b_end))
                except Exception as pe: logger.warning(f"Parse busy interval error: {pe}")
            busy_times.sort()

            last_busy_end = current_search
            for b_start, b_end in busy_times:
                potential_start = last_busy_end
                while potential_start + slot_delta <= b_start:
                    if potential_start + slot_delta <= search_end:
                        start_s = potential_start.strftime('%I:%M %p')
                        end_s = (potential_start + slot_delta).strftime('%I:%M %p %Z')
                        free_slots.append(f"✅ Free {start_s} - {end_s}")
                    potential_start += slot_delta
                last_busy_end = max(last_busy_end, b_end)

            potential_start = last_busy_end
            while potential_start + slot_delta <= search_end:
                start_s = potential_start.strftime('%I:%M %p')
                end_s = (potential_start + slot_delta).strftime('%I:%M %p %Z')
                free_slots.append(f"✅ Free {start_s} - {end_s}")
                potential_start += slot_delta

            if not free_slots:
                date_str = start_dt.strftime('%A, %b %d')
                return [f"📭 No free {duration_minutes}-min slots found on {date_str}."]
            logger.info(f"Found {len(free_slots)} free slots.")
            return free_slots
        except errors.HttpError as e: logger.error(f"API Error free/busy: {e}"); return [f"API Error: {e}"]
        except Exception as e: logger.error(f"Error finding slots: {e}", exc_info=True); return [f"Unexpected error: {e}"]

# End of CalendarAssistant Class