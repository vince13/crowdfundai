# AI-APP Marketplace Revenue Management System

## Overview
The AI-APP Marketplace Revenue Management System is a comprehensive solution for tracking, distributing, and managing revenue from AI applications. It supports multiple currencies with Naira (NGN) as the primary currency, handles automatic revenue distribution to shareholders, and provides detailed analytics.
AI predicts campaign success with 85% accuracy and scalable backend handles over 10k users

## Features
- Multi-currency revenue tracking (NGN, USD, EUR, GBP, JPY)
- Automated revenue distribution to shareholders
- Real-time exchange rate management
- Detailed revenue analytics and reporting
- Distribution status tracking and retry mechanisms
- Currency formatting and validation

## Setup Instructions

### Prerequisites
- Python 3.8+
- Django 4.0+
- PostgreSQL (recommended) or SQLite

### Installation
1. Clone the repository:
```bash
git clone [repository-url]
cd crowdfund_ai
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start the development server:
```bash
python manage.py runserver
```

## Testing
Run the test suite:
```bash
pytest
```

For specific revenue tests:
```bash
pytest core/tests/test_revenue_currency_cases.py -v
```

## Documentation
- [API Documentation](docs/api.md)
- [Technical Documentation](docs/technical.md)
- [User Guide](docs/user_guide.md)

## License
[License Type] - See LICENSE file for details

# Environment Setup

This project requires several environment variables to be set. Follow these steps to set up your environment:

1. Copy `.env.example` to create your `.env` file:
```bash
cp .env.example .env
```

2. Update the `.env` file with your actual values:
- Add your OpenAI API key
- Configure Firebase credentials
- Set up email settings
- Configure Paystack settings
- Add Google Auth credentials
- Set database credentials
- Configure Redis URL

3. For PythonAnywhere deployment:
- Create `.env` file in your PythonAnywhere project directory
- Set proper permissions: `chmod 600 .env`
- Never commit the `.env` file to version control
- Make sure DEBUG=False in production

## Required Environment Variables

The following environment variables must be set:

- `DJANGO_DEBUG`: Set to False in production
- `DJANGO_SECRET_KEY`: Your Django secret key
- `OPENAI_API_KEY`: Your OpenAI API key
- `FIREBASE_*`: Firebase service account credentials
- `EMAIL_*`: Email configuration
- `PAYSTACK_*`: Paystack payment gateway credentials
- `GOOGLE_*`: Google authentication credentials
- `REDIS_URL`: Redis connection URL

See `.env.example` for all required variables. 
