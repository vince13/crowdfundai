import os
from dotenv import load_dotenv
from pathlib import Path

def test_environment_variables():
    # Load environment variables
    load_dotenv()
    
    # Required variables to check
    required_vars = {
        'Django Settings': [
            'DJANGO_DEBUG',
            'DJANGO_SECRET_KEY',
            'ALLOWED_HOSTS',
        ],
        'OpenAI Settings': [
            'OPENAI_API_KEY',
        ],
        'Firebase Settings': [
            'FIREBASE_PROJECT_ID',
            'FIREBASE_PRIVATE_KEY_ID',
            'FIREBASE_PRIVATE_KEY',
            'FIREBASE_CLIENT_EMAIL',
            'FIREBASE_CLIENT_ID',
            'FIREBASE_CLIENT_CERT_URL',
        ],
        'Email Settings': [
            'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD',
            'DEFAULT_FROM_EMAIL',
        ],
        'Paystack Settings': [
            'PAYSTACK_SECRET_KEY',
            'PAYSTACK_PUBLIC_KEY',
        ],
        'Google Auth Settings': [
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
        ],
        'Redis Settings': [
            'REDIS_URL',
        ],
    }
    
    print("\nEnvironment Variables Test Results:")
    print("="*50)
    
    all_valid = True
    for category, variables in required_vars.items():
        print(f"\n{category}:")
        print("-"*30)
        for var in variables:
            value = os.getenv(var)
            if value:
                # For sensitive data, only show first/last few characters
                if any(sensitive in var.lower() for sensitive in ['key', 'secret', 'password', 'private']):
                    display_value = f"{value[:4]}...{value[-4:]}"
                else:
                    display_value = value
                print(f"✅ {var}: {display_value}")
            else:
                print(f"❌ {var}: Not set")
                all_valid = False
    
    print("\n" + "="*50)
    if all_valid:
        print("✅ All required environment variables are set!")
    else:
        print("❌ Some required environment variables are missing!")

if __name__ == "__main__":
    test_environment_variables() 