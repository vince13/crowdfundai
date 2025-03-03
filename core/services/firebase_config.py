import os
import json
import firebase_admin
from firebase_admin import credentials
from pathlib import Path

def initialize_firebase():
    try:
        # Check if already initialized
        if firebase_admin._apps:
            return

        # Try to get credentials from environment variables first
        cred_dict = {
            "type": "service_account",
            "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
            "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get('FIREBASE_CLIENT_CERT_URL')
        }

        # Check if all required fields are present
        required_fields = ['project_id', 'private_key_id', 'private_key', 'client_email']
        if all(cred_dict.get(field) for field in required_fields):
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully from environment variables")
            return

        # If environment variables are not complete, try the JSON file
        base_dir = Path(__file__).resolve().parent.parent.parent
        cred_path = base_dir / 'firebase-credentials.json'
        
        if cred_path.exists():
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully from credentials file")
            return
        
        print("Warning: Firebase credentials not found. Firebase features will be disabled.")
    except Exception as e:
        print(f"Warning: Firebase initialization failed: {str(e)}")
        print("Firebase features will be disabled.") 