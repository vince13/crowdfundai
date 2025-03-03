from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
from datetime import datetime, timedelta
from ...models import User
from ...forms import UserRegistrationForm
from ...services.auth import AuthService
import pyotp
from django.contrib.sessions.models import Session
from importlib import import_module

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """API endpoint for user registration"""
    form = UserRegistrationForm(request.data)
    if form.is_valid():
        user = form.save()
        user.is_active = False  # User needs to verify email
        user.save()
        
        # Send verification email
        AuthService.send_verification_email(user)
        
        return Response({
            'message': 'Registration successful. Please check your email to verify your account.',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        }, status=status.HTTP_201_CREATED)
    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    """Verify user's email address"""
    user_id = AuthService.verify_email_token(token)
    if not user_id:
        return Response({
            'error': 'Invalid or expired verification link'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        if user.is_active:
            return Response({
                'message': 'Email already verified'
            })
        
        user.is_active = True
        user.save()
        
        # Generate JWT token for automatic login
        token = generate_jwt_token(user)
        return Response({
            'message': 'Email verified successfully',
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Request password reset email"""
    email = request.data.get('email')
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        AuthService.send_password_reset_email(user)
        return Response({
            'message': 'Password reset instructions sent to your email'
        })
    except User.DoesNotExist:
        return Response({
            'message': 'Password reset instructions sent to your email'
        })  # Same response for security

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request, token):
    """Reset user's password"""
    user_id = AuthService.verify_password_reset_token(token)
    if not user_id:
        return Response({
            'error': 'Invalid or expired reset link'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    password = request.data.get('password')
    if not password:
        return Response({
            'error': 'Password is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(id=user_id)
        user.set_password(password)
        user.save()
        return Response({
            'message': 'Password reset successful'
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user's password"""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({
            'error': 'Both old and new passwords are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not request.user.check_password(old_password):
        return Response({
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    request.user.set_password(new_password)
    request.user.save()
    return Response({
        'message': 'Password changed successfully'
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """API endpoint for user login"""
    email = request.data.get('email')
    password = request.data.get('password')
    two_factor_code = request.data.get('two_factor_code')
    
    try:
        user = User.objects.get(email=email)
        
        # Check if account is locked
        if user.is_account_locked():
            return Response({
                'error': 'Account is temporarily locked due to too many failed attempts.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Authenticate user
        auth_user = authenticate(email=email, password=password)
        if not auth_user:
            user.record_login_attempt(
                success=False,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check email verification
        if not user.is_email_verified:
            return Response({
                'error': 'Please verify your email address first'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check 2FA if enabled
        if user.two_factor_enabled:
            if not two_factor_code:
                return Response({
                    'error': '2FA code required',
                    'requires_2fa': True
                }, status=status.HTTP_403_FORBIDDEN)
            
            if not AuthService.verify_2fa(user, two_factor_code):
                return Response({
                    'error': 'Invalid 2FA code'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Record successful login
        user.record_login_attempt(
            success=True,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        # Generate token
        token = generate_jwt_token(user)
        
        return Response({
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'two_factor_enabled': user.two_factor_enabled
            }
        })
        
    except User.DoesNotExist:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_2fa(request):
    """Set up 2FA for user"""
    user = request.user
    
    if user.two_factor_enabled:
        return Response({
            'error': '2FA is already enabled'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    setup_data = AuthService.setup_2fa(user)
    
    # Store the secret temporarily
    request.session['temp_2fa_secret'] = setup_data['secret']
    
    return Response({
        'qr_code': setup_data['qr_code'],
        'secret': setup_data['secret']
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_2fa_setup(request):
    """Verify and enable 2FA"""
    user = request.user
    code = request.data.get('code')
    secret = request.session.get('temp_2fa_secret')
    
    if not secret:
        return Response({
            'error': '2FA setup not initiated'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not code:
        return Response({
            'error': 'Verification code required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify the code
    totp = pyotp.TOTP(secret)
    if totp.verify(code):
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        user.save()
        
        # Clean up session
        del request.session['temp_2fa_secret']
        
        return Response({
            'message': '2FA enabled successfully'
        })
    
    return Response({
        'error': 'Invalid verification code'
    }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_2fa(request):
    """Disable 2FA for user"""
    user = request.user
    password = request.data.get('password')
    
    if not user.two_factor_enabled:
        return Response({
            'error': '2FA is not enabled'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verify password
    if not authenticate(username=user.username, password=password):
        return Response({
            'error': 'Invalid password'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    user.two_factor_enabled = False
    user.two_factor_secret = None
    user.save()
    
    return Response({
        'message': '2FA disabled successfully'
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """Delete user account"""
    user = request.user
    password = request.data.get('password')
    reason = request.data.get('reason')
    
    # Verify password
    if not authenticate(username=user.username, password=password):
        return Response({
            'error': 'Invalid password'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    user.soft_delete(reason=reason)
    
    return Response({
        'message': 'Account deleted successfully'
    })

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def signout_all_devices(request):
    """Sign out from all devices by invalidating all sessions"""
    user = request.user
    
    # Get all sessions for the user
    for session in Session.objects.all():
        try:
            if session.get_decoded().get('_auth_user_id') == str(user.id):
                session.delete()
        except (Session.DoesNotExist, KeyError):
            continue
    
    return Response({
        'message': 'Successfully signed out from all devices'
    })

def generate_jwt_token(user):
    """Generate JWT token for authenticated user"""
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256') 