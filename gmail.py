import smtplib

class GmailAssistant:
    def __init__(self, email, password):
        self.email = email
        self.password = password

    def send_email(self, recipient, subject, body):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.email, self.password)
                message = f"Subject: {subject}\n\n{body}"
                server.sendmail(self.email, recipient, message)
            print("Email sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")
