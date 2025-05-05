import datetime
import pytz
import os
import pickle
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.send'
]

class CalendarAssistant:
    def __init__(self):
        self.creds = None
        self.service = None
        self.gmail_service = None
        self.authenticate()

    def authenticate(self):
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)

        self.service = build('calendar', 'v3', credentials=self.creds)
        self.gmail_service = build('gmail', 'v1', credentials=self.creds)

    def get_events_for_day(self, day_offset=0):
        now = datetime.datetime.utcnow().date() + datetime.timedelta(days=day_offset)
        start = datetime.datetime.combine(now, datetime.time.min).isoformat() + 'Z'
        end = datetime.datetime.combine(now, datetime.time.max).isoformat() + 'Z'

        events_result = self.service.events().list(
            calendarId='primary', timeMin=start, timeMax=end,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        return events

    def list_today_events(self):
        events = self.get_events_for_day()
        print("Today's Events:")
        if not events:
            print("No events found.")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"{start} - {event.get('summary', 'No Title')}")

    def list_tomorrow_events(self):
        events = self.get_events_for_day(day_offset=1)
        print("Tomorrow's Events:")
        if not events:
            print("No events found.")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"{start} - {event.get('summary', 'No Title')}")

    def list_all_upcoming_events(self):
        print("Upcoming events:")
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = self.service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=10, singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            print("No upcoming events found.")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"{start} - {event.get('summary', 'No Title')}")

    def create_event(self, summary, start_time_str, end_time_str, email=None):
        start_time = datetime.datetime.fromisoformat(start_time_str)
        end_time = datetime.datetime.fromisoformat(end_time_str)
        event = {
            'summary': summary,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }

        created_event = self.service.events().insert(calendarId='primary', body=event).execute()
        print(f"✅ Event created: {created_event.get('htmlLink')}")

        if email:
            self.send_email_notification(email, summary, start_time_str, end_time_str)

    def send_email_notification(self, to_email, summary, start, end):
        message_text = f"You have a new event: {summary}\nStart: {start}\nEnd: {end}"
        message = MIMEText(message_text)
        message['to'] = to_email
        message['subject'] = 'New Calendar Event Notification'
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {'raw': raw}
        try:
            message = self.gmail_service.users().messages().send(userId="me", body=body).execute()
            print(f"📧 Email notification sent to {to_email}")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")

    def find_free_slots(self):
        print("Checking free 30-minute slots...")
        now = datetime.datetime.utcnow()
        start = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=pytz.UTC)
        end = start + datetime.timedelta(days=1)

        events_result = self.service.events().list(
            calendarId='primary', timeMin=start.isoformat(),
            timeMax=end.isoformat(), singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        busy = []
        for event in events:
            start_time = event['start'].get('dateTime')
            end_time = event['end'].get('dateTime')
            if start_time and end_time:
                busy.append((
                    datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00')),
                    datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                ))

        busy.sort()
        free_slots = []
        current = start
        for start_time, end_time in busy:
            if (start_time - current).total_seconds() >= 1800:
                free_slots.append((current, start_time))
            current = max(current, end_time)
        if (end - current).total_seconds() >= 1800:
            free_slots.append((current, end))

        if not free_slots:
            print("No 30-minute free slots found today.")
        else:
            for s, e in free_slots:
                print(f"🕒 Free from {s.time()} to {e.time()}")

    def show_week_events(self):
        print("Fetching this week's events...")
        now = datetime.datetime.utcnow()
        start = datetime.datetime(now.year, now.month, now.day, tzinfo=pytz.UTC)
        end = start + datetime.timedelta(days=7)

        events_result = self.service.events().list(
            calendarId='primary', timeMin=start.isoformat(),
            timeMax=end.isoformat(), singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            print("No events found for this week.")
        for event in events:
            start_time = event['start'].get('dateTime', event['start'].get('date'))
            print(f"{start_time} {event.get('summary', 'No Title')}")
