from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..forms import UserRegistrationForm, UserProfileForm
from django.contrib.auth import authenticate, login
from ..security.security_service import SecurityService
from ..services.auth import AuthService
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetView
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import traceback
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

logger = logging.getLogger(__name__)

@csrf_exempt
def register(request):
    if request.method == 'GET':
        form = UserRegistrationForm()
        return render(request, 'core/auth/register.html', {'form': form})
    
    elif request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # User needs to verify email
            user.save()
            
            try:
                # Attempt to send verification email
                email_sent = AuthService.send_verification_email(user)
                
                if request.headers.get('Accept') == 'application/json':
                    # API response
                    if email_sent or settings.DEBUG:
                        return JsonResponse({
                            'message': 'Registration successful. Please check your email to verify your account.',
                            'user': {
                                'id': user.id,
                                'username': user.username,
                                'email': user.email
                            }
                        }, status=201)
                    else:
                        return JsonResponse({
                            'message': 'Registration successful but we could not send the verification email. Please try requesting a new verification email later.',
                            'user': {
                                'id': user.id,
                                'username': user.username,
                                'email': user.email
                            }
                        }, status=201)
                else:
                    # Browser response
                    messages.success(request, 'Registration successful. Please check your email to verify your account.')
                    return redirect('core:login')
                    
            except Exception as e:
                # Log the error but don't expose details to the user
                logger.error(f"Error during registration for {user.email}: {str(e)}")
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse({
                        'error': 'An error occurred during registration. Please try again later.'
                    }, status=500)
                else:
                    messages.error(request, 'An error occurred during registration. Please try again later.')
                    return render(request, 'core/auth/register.html', {'form': form})
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'error': 'Invalid form data',
                    'errors': form.errors
                }, status=400)
            else:
                return render(request, 'core/auth/register.html', {'form': form})
    
    return JsonResponse({'error': 'Only GET and POST methods are allowed'}, status=405)

@login_required
def profile(request, user_id=None):
    if user_id:
        # Viewing another user's profile
        profile_user = get_object_or_404(get_user_model(), id=user_id)
        return render(request, 'core/auth/profile.html', {
            'profile_user': profile_user,
            'viewing_other': True
        })
    else:
        # Viewing/editing own profile
        if request.method == 'POST':
            form = UserProfileForm(request.POST, request.FILES, instance=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('core:profile')
        else:
            form = UserProfileForm(instance=request.user)
        
        return render(request, 'core/auth/profile.html', {
            'form': form,
            'profile_user': request.user,
            'viewing_other': False
        })

def login_view(request):
    # For GET requests, ensure CSRF token is set
    if request.method == 'GET':
        response = render(request, 'core/auth/login.html')
        if 'csrftoken' not in request.COOKIES:
            get_token(request)  # Force CSRF token generation
        return response

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Debug logging
        logger.info(f"Login attempt for user: {username}")
        logger.info(f"CSRF Token present: {'csrfmiddlewaretoken' in request.POST}")
        logger.info(f"CSRF Cookie present: {'csrftoken' in request.COOKIES}")
        
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Please verify your email address before logging in.")
                return redirect('core:login')
                
            if SecurityService.prevent_brute_force(user):
                messages.error(request, "Your account has been locked due to too many failed login attempts.")
                return redirect('core:login')

            # Log the user in and set session settings
            login(request, user)
            
            # Set session expiry and security flags
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)  # Use the settings value
            request.session['is_secure'] = request.is_secure()
            request.session['user_id'] = user.id
            request.session['is_staff'] = user.is_staff
            
            # Debug: Log session info
            logger.info(f"Session info after login - user: {user.username}, is_staff: {user.is_staff}, session_id: {request.session.session_key}")
            
            # If this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('core:dashboard')
                })
                
            return redirect('core:dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            # Optionally log suspicious activity
            SecurityService.detect_suspicious_activity(None, "Failed login attempt", f"Username: {username}")
            
            # If this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': "Invalid username or password."
                }, status=401)

    return render(request, 'core/auth/login.html')

def check_session(request):
    """Debug endpoint to check session state"""
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
            'is_staff': request.user.is_staff,
            'session_id': request.session.session_key,
            'session_data': {
                'is_secure': request.session.get('is_secure'),
                'user_id': request.session.get('user_id'),
                'is_staff': request.session.get('is_staff')
            }
        })
    return JsonResponse({
        'authenticated': False,
        'session_id': request.session.session_key
    }) 

@csrf_exempt
def verify_email(request, token):
    """Verify user's email address"""
    User = get_user_model()
    logger.info(f"Attempting to verify email with token: {token[:10]}...")
    
    try:
        # Verify the token and get user_id
        user_id = AuthService.verify_email_token(token)
        if not user_id:
            logger.warning(f"Invalid or expired token: {token[:10]}...")
            messages.error(request, 'Invalid or expired verification link. Please request a new verification email.')
            return redirect('core:login')
        
        # Get the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"User not found for token: {token[:10]}...")
            messages.error(request, 'User not found. Please register again.')
            return redirect('core:register')
        
        # Check if already verified
        if user.is_active and user.is_email_verified:
            logger.info(f"User {user.email} already verified")
            messages.info(request, 'Your email is already verified. Please log in.')
            return redirect('core:login')
        
        # Verify the email
        logger.info(f"Verifying email for user {user.email}")
        User.objects.filter(id=user_id).update(
            is_active=True,
            is_email_verified=True
        )
        
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('core:login')
        
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        messages.error(request, 'An error occurred during email verification. Please try again.')
        return redirect('core:login') 

class CustomPasswordResetView(PasswordResetView):
    template_name = 'core/auth/password_reset.html'
    email_template_name = 'core/emails/password_reset.html'
    subject_template_name = 'core/emails/password_reset_subject.txt'
    success_url = reverse_lazy('core:password_reset_done')
    
    def form_valid(self, form):
        """Override form_valid to use our custom email sending."""
        email = form.cleaned_data["email"]
        logger.info("Password reset form submitted")
        logger.info(f"Attempting password reset for email: {email}")
        
        try:
            # Find active users for this email
            active_users = get_user_model().objects.filter(email=email, is_active=True)
            logger.info(f"Found {active_users.count()} active users for email {email}")
            
            if active_users.exists():
                user = active_users.first()
                # Get the context for email template
                context = {
                    'email': email,
                    'domain': self.request.get_host(),
                    'site_name': settings.SITE_NAME,
                    'protocol': 'https' if self.request.is_secure() else 'http',
                    'user': user,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                }
                
                # Render email templates
                subject = render_to_string(self.subject_template_name, context)
                subject = ''.join(subject.splitlines())  # Remove newlines
                html_message = render_to_string(self.email_template_name, context)
                plain_message = strip_tags(html_message)
                
                # Use our custom email sending method
                email_sent = AuthService.send_email(
                    subject=subject,
                    message=plain_message,
                    html_message=html_message,
                    recipient_list=[user.email]
                )
                
                if email_sent:
                    logger.info(f"Password reset email sent successfully to {email}")
                    return super().form_valid(form)
                else:
                    logger.error(f"Failed to send password reset email to {email}")
                    messages.error(self.request, "Failed to send password reset email. Please try again.")
                    return self.form_invalid(form)
            
            # Even if no user is found, return success to prevent user enumeration
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(self.request, "There was an error sending the password reset email. Please try again.")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = settings.SITE_NAME
        return context 