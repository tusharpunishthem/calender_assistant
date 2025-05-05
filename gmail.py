# gmail_notifier.py
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import pickle
import os
import logging
from googleapiclient import errors # Import errors for handling API exceptions
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_PICKLE_FILE = 'gmail_token.pickle'
CREDENTIALS_FILE = 'credentials.json'

class GmailNotifier:
    def __init__(self):
        self.service = self._authenticate()
        if not self.service:
            logger.error("Gmail Notifier failed to authenticate. Email sending disabled.")

    def _authenticate(self):
        creds = None
        if os.path.exists(TOKEN_PICKLE_FILE):
            try:
                with open(TOKEN_PICKLE_FILE, 'rb') as token:
                    creds = pickle.load(token)
                logger.debug("Loaded Gmail credentials from pickle.")
            except Exception as e:
                logger.error(f"Error loading {TOKEN_PICKLE_FILE}: {e}. Re-authenticating.", exc_info=True)
                creds = None

        if not creds or not creds.valid:
            needs_refresh = creds and creds.expired and creds.refresh_token
            if needs_refresh:
                logger.info("Refreshing Gmail API token...")
                try:
                    creds.refresh(Request())
                    logger.info("Gmail token refreshed.")
                    # Save refreshed token
                    try:
                         with open(TOKEN_PICKLE_FILE, 'wb') as token: pickle.dump(creds, token)
                         logger.info(f"Refreshed Gmail token saved to {TOKEN_PICKLE_FILE}")
                    except Exception as save_e: logger.error(f"Error saving refreshed Gmail token: {save_e}")
                except Exception as e:
                    logger.error(f"Error refreshing Gmail token: {e}. Re-authenticating.", exc_info=True)
                    if os.path.exists(TOKEN_PICKLE_FILE):
                        try: os.remove(TOKEN_PICKLE_FILE)
                        except OSError as del_e: logger.error(f"Failed to remove corrupt Gmail token: {del_e}")
                    creds = None

            if not creds or not creds.valid:
                logger.info("Starting OAuth flow for Gmail API access...")
                if not os.path.exists(CREDENTIALS_FILE):
                     logger.critical(f"{CREDENTIALS_FILE} not found. Cannot authenticate Gmail.")
                     return None
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0, prompt='consent', authorization_prompt_message='Please authorize Gmail access:')
                    logger.info("Gmail OAuth flow completed.")
                    # Save new credentials
                    try:
                        with open(TOKEN_PICKLE_FILE, 'wb') as token: pickle.dump(creds, token)
                        logger.info(f"New Gmail token saved to {TOKEN_PICKLE_FILE}")
                    except Exception as save_e: logger.error(f"Error saving new Gmail token: {save_e}")
                except Exception as e:
                    logger.error(f"Gmail OAuth flow failed: {e}", exc_info=True)
                    return None

        if not creds or not creds.valid:
             logger.error("Failed to obtain valid Gmail credentials.")
             return None

        try:
            service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail service built successfully.")
            return service
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}", exc_info=True)
            return None

    def send_email_notification(self, to_emails, subject, body):
        """Sends an email notification to a list of recipients."""
        if not self.service:
             logger.error("Gmail service unavailable. Cannot send email.")
             return False # Indicate failure

        if isinstance(to_emails, str): # Allow single string recipient
            to_emails = [to_emails]
        if not isinstance(to_emails, list) or not to_emails:
            logger.warning("No valid recipient emails provided for notification.")
            return False

        success_count = 0
        total_recipients = len(to_emails)
        logger.info(f"Attempting to send email '{subject}' to {total_recipients} recipient(s)...")

        for to_email in to_emails:
            if not isinstance(to_email, str) or '@' not in to_email:
                logger.warning(f"Skipping invalid email address: {to_email}")
                total_recipients -= 1 # Adjust total for success rate calculation
                continue
            try:
                # Create MIME message
                message = MIMEText(body)
                message['to'] = to_email
                message['subject'] = subject
                message['from'] = 'me' # Sends from the authenticated user's address

                # Encode message in base64
                raw_message_bytes = message.as_bytes()
                raw_message_b64 = base64.urlsafe_b64encode(raw_message_bytes).decode()
                api_body = {'raw': raw_message_b64}

                # Send message using Gmail API
                send_result = self.service.users().messages().send(
                    userId='me',
                    body=api_body
                ).execute()
                logger.debug(f"Email sent to {to_email}. Message ID: {send_result.get('id')}")
                success_count += 1
            except errors.HttpError as error:
                logger.error(f"API error sending email to {to_email}: {error}", exc_info=True)
            except Exception as e:
                logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)

        if success_count > 0:
            logger.info(f"Successfully sent email notification to {success_count}/{total_recipients} valid recipients.")
        else:
             logger.error(f"Failed to send email notification to any of the {total_recipients} valid recipients.")

        # Return True only if all intended valid emails were sent successfully
        return success_count == total_recipients and total_recipients > 0

# End of GmailNotifier Class