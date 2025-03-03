from django.conf import settings
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
import jwt
from datetime import datetime, timedelta
import pyotp
import qrcode
import base64
from io import BytesIO
import logging
from django.urls import reverse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
import smtplib
import ssl
import certifi

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def generate_token(user_id, type='email_verification', expiry_hours=24):
        """Generate a JWT token for email verification or password reset"""
        payload = {
            'user_id': user_id,
            'type': type,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def verify_token(token, type):
        """Verify a JWT token and return the user_id if valid"""
        try:
            logger.info(f"Verifying {type} token: {token[:10]}...")
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            
            if payload['type'] != type:
                logger.warning(f"Token type mismatch. Expected {type}, got {payload['type']}")
                return None
                
            logger.info(f"Token verified successfully for user_id: {payload['user_id']}")
            return payload['user_id']
            
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token expired: {token[:10]}...")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {token[:10]}... Error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {str(e)}")
            return None

    @staticmethod
    def send_email(subject, message, html_message, recipient_list, max_retries=2):
        """Send email with retry logic"""
        for attempt in range(max_retries):
            try:
                # Create SSL context with system certificates
                context = ssl.create_default_context(cafile=certifi.where())
                
                # Create message
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = settings.DEFAULT_FROM_EMAIL
                msg['To'] = ', '.join(recipient_list)
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid(domain='fundafrica.net')
                msg.add_header('X-Priority', '1')  # High priority
                msg.add_header('X-MSMail-Priority', 'High')
                msg.add_header('Importance', 'High')
                
                # Attach plain text and HTML versions
                msg.attach(MIMEText(message, 'plain'))
                if html_message:
                    msg.attach(MIMEText(html_message, 'html'))
                
                # Connect to SMTP server
                smtp = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=30)
                if settings.DEBUG:
                    smtp.set_debuglevel(1)
                
                # Start TLS if required
                if settings.EMAIL_USE_TLS:
                    smtp.starttls(context=context)
                
                # Login and send
                smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                smtp.send_message(msg)
                smtp.quit()
                
                logger.info(f"Email sent successfully to {', '.join(recipient_list)}")
                return True
                
            except Exception as e:
                logger.error(f"Email sending failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    if settings.DEBUG:
                        # In development, log the email content to console
                        logger.info(f"Email would have been sent in production:")
                        logger.info(f"Subject: {subject}")
                        logger.info(f"To: {recipient_list}")
                        logger.info(f"Message: {message}")
                    else:
                        raise  # Re-raise the exception in production
        return False

    @staticmethod
    def send_verification_email(user):
        """Send email verification link to user"""
        try:
            token = AuthService.generate_token(user.id, 'email_verification')
            verification_url = f"{settings.SITE_URL}{reverse('core:verify_email', kwargs={'token': token})}"
            
            logger.info(f"Sending verification email to {user.email} with URL: {verification_url}")
            
            context = {
                'user': user,
                'verification_url': verification_url,
                'site_name': 'AI Crowdfunding'
            }
            
            html_message = render_to_string('core/emails/verify_email.html', context)
            plain_message = strip_tags(html_message)
            
            success = AuthService.send_email(
                subject='Verify your email address',
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.email]
            )
            
            if success:
                logger.info(f"Verification email sent successfully to {user.email}")
                return True
            else:
                logger.error(f"Failed to send verification email to {user.email}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending verification email to {user.email}: {str(e)}")
            if settings.DEBUG:
                raise
            return False

    @staticmethod
    def send_password_reset_email(user):
        """Send password reset link to user"""
        try:
            token = AuthService.generate_token(user.id, 'password_reset')
            reset_url = f"{settings.SITE_URL}{reverse('core:password_reset_confirm', kwargs={'token': token})}"
            
            logger.info(f"Sending password reset email to {user.email} with URL: {reset_url}")
            
            context = {
                'user': user,
                'reset_url': reset_url,
                'site_name': 'AI Crowdfunding'
            }
            
            html_message = render_to_string('core/emails/password_reset.html', context)
            plain_message = strip_tags(html_message)
            
            success = AuthService.send_email(
                subject='Reset your password',
                message=plain_message,
                html_message=html_message,
                recipient_list=[user.email]
            )
            
            if success:
                logger.info(f"Password reset email sent successfully to {user.email}")
                return True
            else:
                logger.error(f"Failed to send password reset email to {user.email}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending password reset email to {user.email}: {str(e)}")
            if settings.DEBUG:
                raise
            return False

    @staticmethod
    def setup_2fa(user):
        """Set up 2FA for a user"""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate QR code
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="AI Crowdfunding"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            'secret': secret,
            'qr_code': qr_code_base64
        }

    @staticmethod
    def verify_2fa(user, code):
        """Verify 2FA code"""
        if not user.two_factor_secret:
            return False
            
        totp = pyotp.TOTP(user.two_factor_secret)
        return totp.verify(code)

    @staticmethod
    def verify_email_token(token):
        """Verify email verification token"""
        return AuthService.verify_token(token, 'email_verification')

    @staticmethod
    def verify_password_reset_token(token):
        """Verify password reset token"""
        return AuthService.verify_token(token, 'password_reset')

    @staticmethod
    def test_email_configuration():
        """Test email configuration by sending a test email"""
        try:
            logger.info("Testing email configuration...")
            html_message = """
            <html>
                <body>
                    <h1>Test Email</h1>
                    <p>This is a test email to verify the email configuration.</p>
                    <p>If you receive this, your email settings are working correctly.</p>
                </body>
            </html>
            """
            plain_message = "This is a test email to verify the email configuration."
            
            success = AuthService.send_email(
                subject='Test Email Configuration',
                message=plain_message,
                html_message=html_message,
                recipient_list=[settings.EMAIL_HOST_USER]  # Send to the configured email
            )
            
            if success:
                logger.info("Test email sent successfully!")
                return True, "Test email sent successfully!"
            else:
                error_msg = "Failed to send test email"
                logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Error testing email configuration: {str(e)}"
            logger.error(error_msg)
            return False, error_msg 