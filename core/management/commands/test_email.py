from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import smtplib
import sys
import ssl
from contextlib import contextmanager
import io
import certifi
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

class Command(BaseCommand):
    help = 'Test email configuration by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str, help='Email address to send test email to')

    @contextmanager
    def suppress_stdout(self):
        stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            yield
        finally:
            sys.stdout = stdout

    def handle(self, *args, **options):
        recipient = options['recipient']
        self.stdout.write(self.style.SUCCESS(f"\nEmail Configuration:"))
        self.stdout.write(f"SMTP Server: {settings.EMAIL_HOST}")
        self.stdout.write(f"Port: {settings.EMAIL_PORT}")
        self.stdout.write(f"TLS Enabled: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"SSL Enabled: {settings.EMAIL_USE_SSL}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"To: {recipient}")
        
        try:
            # Test SMTP connection with detailed error handling
            self.stdout.write("\nTesting SMTP connection...")
            
            # Create SSL context with system certificates
            context = ssl.create_default_context(cafile=certifi.where())
            
            # Connect to SMTP server
            self.stdout.write("1. Connecting to SMTP server...")
            smtp = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=30)
            smtp.set_debuglevel(1)  # Enable debug output
            
            # Perform initial EHLO
            self.stdout.write("2. Performing initial EHLO...")
            smtp.ehlo()
            
            if settings.EMAIL_USE_TLS:
                self.stdout.write("3. Starting TLS...")
                smtp.starttls(context=context)
                smtp.ehlo()  # Perform second EHLO after TLS
            
            # Attempt login
            self.stdout.write("4. Attempting login...")
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            self.stdout.write(self.style.SUCCESS("✓ SMTP connection and authentication successful"))

            # Create message
            self.stdout.write("\nSending test email...")
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'FundAfrica - Test Email'
            msg['From'] = settings.DEFAULT_FROM_EMAIL
            msg['To'] = recipient
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain='fundafrica.net')
            msg.add_header('X-Priority', '1')  # High priority
            msg.add_header('X-MSMail-Priority', 'High')
            msg.add_header('Importance', 'High')
            
            # Plain text version
            text = "This is a test email from FundAfrica platform."
            msg.attach(MIMEText(text, 'plain'))
            
            # HTML version
            html = """
            <html>
                <head>
                    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                </head>
                <body>
                    <h1>FundAfrica Test Email</h1>
                    <p>This is a test email from FundAfrica platform.</p>
                    <p>If you're seeing this, the email was delivered successfully!</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(html, 'html'))
            
            # Send the email
            smtp.send_message(msg)
            smtp.quit()
            
            self.stdout.write(self.style.SUCCESS("✓ Test email sent successfully"))
            self.stdout.write("\nPlease check your inbox at " + recipient)
            
        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f'Authentication failed: {str(e)}'))
            self.stdout.write(self.style.WARNING('Please verify your EMAIL_HOST_USER and EMAIL_HOST_PASSWORD'))
        except smtplib.SMTPException as e:
            self.stdout.write(self.style.ERROR(f'SMTP Error: {str(e)}'))
            self.stdout.write(self.style.WARNING('This might be due to incorrect server settings or network issues'))
        except ssl.SSLError as e:
            self.stdout.write(self.style.ERROR(f'SSL Error: {str(e)}'))
            self.stdout.write(self.style.WARNING('This might be due to SSL/TLS configuration issues'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            import traceback
            self.stdout.write(self.style.WARNING(traceback.format_exc())) 