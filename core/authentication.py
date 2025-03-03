from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings
import jwt
from datetime import datetime
from .models import User

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            # Get the token
            auth_type, token = auth_header.split(' ')
            if auth_type.lower() != 'bearer':
                return None

            # Decode token
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=['HS256']
            )

            # Check token expiration
            exp_timestamp = payload.get('exp')
            if not exp_timestamp or datetime.fromtimestamp(exp_timestamp) < datetime.now():
                raise exceptions.AuthenticationFailed('Token has expired')

            # Get user
            user_id = payload.get('user_id')
            if not user_id:
                raise exceptions.AuthenticationFailed('Invalid token payload')

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise exceptions.AuthenticationFailed('User not found')

            return (user, token)

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except ValueError:
            return None

    def authenticate_header(self, request):
        return 'Bearer' 