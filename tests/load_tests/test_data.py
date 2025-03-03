"""
Test Data Management for Load Tests
"""
import requests
import json
from typing import Dict, List
from pathlib import Path
from datetime import datetime
import re
import time

class TestDataManager:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.created_users: Dict[str, Dict] = {}
        self.created_apps: List[Dict] = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def _make_request(self, method: str, endpoint: str, data: Dict = None, headers: Dict = None) -> Dict:
        """Make HTTP request and handle response"""
        url = f"{self.base_url}{endpoint}"
        try:
            request_kwargs = {
                'headers': headers or {},
                'timeout': 10
            }
            if data:
                request_kwargs['json'] = data
                
            response = self.session.request(method, url, **request_kwargs)
            
            # Print response details for debugging
            print(f"\nRequest details:")
            print(f"URL: {url}")
            print(f"Method: {method}")
            print(f"Headers: {request_kwargs['headers']}")
            print(f"Data: {data}")
            print(f"\nResponse details:")
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            try:
                print(f"Body: {response.json()}")
            except:
                print(f"Text: {response.text}")
                
            if response.status_code >= 400:
                print(f"\nError response details:")
                try:
                    error_data = response.json()
                    for field, errors in error_data.items():
                        print(f"{field}: {errors}")
                except:
                    print(f"Raw error text: {response.text}")
                return {}
                
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            print(f"\nRequest error:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                try:
                    print(f"Response body: {e.response.json()}")
                except:
                    print(f"Response text: {e.response.text}")
            return {}
            
    def _extract_verification_token(self, user_email: str) -> str:
        """Extract verification token from console output in development mode"""
        try:
            # In development mode, the verification URL will be logged to console
            # Look for the verification URL in the console output
            # The URL will be in the format: http://127.0.0.1:8000/api/v1/auth/verify-email/{token}
            # We need to extract the token from the URL
            
            # Wait a moment for the email to be logged
            time.sleep(1)
            
            # Read the logs
            with open('/Users/vince/Documents/PYTHON/AI-APP Marketplace/V1/crowdfund_ai/logs/general.log', 'r') as f:
                logs = f.readlines()
            
            # Look for the verification URL in recent logs
            for line in reversed(logs[-50:]):  # Check last 50 lines
                if 'verification_url' in line and user_email in line:
                    url_match = re.search(r'http://[^/]+/api/v1/auth/verify-email/([^/\s]+)', line)
                    if url_match:
                        return url_match.group(1)
            
            print(f"Could not find verification URL for {user_email} in logs")
            return ""
            
        except Exception as e:
            print(f"Error extracting verification token: {e}")
            return ""
            
    def create_user(self, user_type: str, user_data: Dict) -> bool:
        """Create a test user"""
        try:
            # Generate unique username and email
            base_email = user_data["email"].split("@")
            unique_email = f"{base_email[0]}_{self.timestamp}@{base_email[1]}"
            unique_username = f"{base_email[0]}_{self.timestamp}"
            
            # Register user
            register_data = {
                "username": unique_username,
                "email": unique_email,
                "password1": user_data["password"],
                "password2": user_data["password"],
                "role": user_data["role"]
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            response = self._make_request("POST", "/api/v1/auth/register/", register_data, headers)
            
            if not response:
                print(f"Failed to register user {unique_email}")
                return False
                
            # Store user data
            self.created_users[user_type] = {
                "email": unique_email,
                "username": unique_username,
                "password": user_data["password"],
                "role": user_data["role"]
            }
            
            # Get verification token and verify email
            verification_token = self._extract_verification_token(unique_email)
            if verification_token:
                verify_response = self._make_request("GET", f"/api/v1/auth/verify-email/{verification_token}/")
                if verify_response:
                    print(f"Verified email for user: {unique_email}")
                    
                    # Login to get auth token
                    login_data = {
                        "email": unique_email,
                        "password": user_data["password"]
                    }
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }
                    login_response = self._make_request("POST", "/api/v1/auth/login/", login_data, headers)
                    
                    if login_response and "token" in login_response:
                        self.session.headers.update({
                            "Authorization": f"Bearer {login_response['token']}"
                        })
                        print(f"Successfully logged in as {unique_email}")
                        return True
                        
            print(f"Failed to verify/login user {unique_email}")
            return False
            
        except Exception as e:
            print(f"Error creating user {user_data['email']}: {e}")
            return False
            
    def create_app(self, app_data: Dict) -> bool:
        """Create a test app"""
        try:
            # Login as developer
            login_data = {
                "email": self.created_users["developer"]["email"],
                "password": self.created_users["developer"]["password"]
            }
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            login_response = self._make_request("POST", "/api/v1/auth/login/", login_data, headers)
            
            if not login_response or "token" not in login_response:
                print("Failed to login as developer")
                return False
                
            # Set authorization header
            self.session.headers.update({
                "Authorization": f"Bearer {login_response['token']}"
            })
            
            # Create app with unique name
            unique_app_data = app_data.copy()
            unique_app_data["name"] = f"{app_data['name']}_{self.timestamp}"
            
            # Create app
            response = self._make_request("POST", "/api/v1/apps/", unique_app_data)
            
            if response:
                self.created_apps.append(response)
                print(f"Created test app: {unique_app_data['name']}")
                return True
                
            return False
            
        except Exception as e:
            print(f"Error creating app {app_data['name']}: {e}")
            return False
            
    def setup_test_data(self, users: Dict[str, Dict], apps: List[Dict]) -> bool:
        """Set up all test data"""
        success = True
        
        # Create users
        for user_type, user_data in users.items():
            if not self.create_user(user_type, user_data):
                success = False
                
        # Create apps
        for app_data in apps:
            if not self.create_app(app_data):
                success = False
                
        return success
        
    def cleanup_test_data(self) -> bool:
        """Clean up test data"""
        try:
            # Delete apps (developer can delete their own apps)
            if "developer" in self.created_users:
                # Login as developer
                login_data = {
                    "email": self.created_users["developer"]["email"],
                    "password": self.created_users["developer"]["password"]
                }
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                login_response = self._make_request("POST", "/api/v1/auth/login/", login_data, headers)
                
                if login_response and "token" in login_response:
                    self.session.headers.update({
                        "Authorization": f"Bearer {login_response['token']}"
                    })
                    
                    # Delete apps
                    for app in self.created_apps:
                        self._make_request("DELETE", f"/api/v1/apps/{app['id']}/")
                        print(f"Deleted app: {app['name']}")
            
            # Delete users (each user can delete their own account)
            for user_type, user_data in self.created_users.items():
                # Login as the user
                login_data = {
                    "email": user_data["email"],
                    "password": user_data["password"]
                }
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                login_response = self._make_request("POST", "/api/v1/auth/login/", login_data, headers)
                
                if login_response and "token" in login_response:
                    self.session.headers.update({
                        "Authorization": f"Bearer {login_response['token']}"
                    })
                    # Delete account
                    self._make_request("POST", "/api/v1/auth/delete-account/", {
                        "password": user_data["password"],
                        "reason": "Test cleanup"
                    })
                    print(f"Deleted {user_type} user: {user_data['email']}")
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up test data: {e}")
            return False 