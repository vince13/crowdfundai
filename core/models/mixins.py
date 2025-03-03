from django.utils import timezone
import pyotp
import qrcode
import base64
from io import BytesIO

class UserSecurityMixin:
    def record_login_attempt(self, success, ip_address=None, user_agent=None):
        """Record login attempt and handle account locking"""
        if success:
            self.failed_login_attempts = 0
            self.last_login_ip = ip_address
            self.last_login_user_agent = user_agent
        else:
            self.failed_login_attempts += 1
            self.last_failed_login = timezone.now()
            
            # Lock account after 5 failed attempts
            if self.failed_login_attempts >= 5:
                self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        
        self.save()
    
    def is_account_locked(self):
        """Check if account is temporarily locked"""
        if self.account_locked_until and self.account_locked_until > timezone.now():
            return True
        return False

    def soft_delete(self, reason=None):
        """Soft delete the user account"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deletion_reason = reason
        self.email = f"deleted_{self.id}_{self.email}"  # Preserve email uniqueness
        self.username = f"deleted_{self.id}_{self.username}"  # Preserve username uniqueness
        self.is_active = False
        self.save()

class TwoFactorMixin:
    def setup_2fa(self):
        """Set up 2FA for the user"""
        if self.two_factor_enabled:
            return None
            
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Generate QR code
        provisioning_uri = totp.provisioning_uri(
            name=self.email,
            issuer_name="AI Crowdfunding"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Save the secret
        self.two_factor_secret = secret
        self.two_factor_enabled = True
        self.save()
        
        return {
            'secret': secret,
            'qr_code': qr_code_base64
        }
    
    def verify_2fa_code(self, code):
        """Verify a 2FA code"""
        if not self.two_factor_enabled or not self.two_factor_secret:
            return False
            
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(code)
    
    def disable_2fa(self):
        """Disable 2FA for the user"""
        if not self.two_factor_enabled:
            return False
            
        self.two_factor_enabled = False
        self.two_factor_secret = None
        self.save()
        return True 