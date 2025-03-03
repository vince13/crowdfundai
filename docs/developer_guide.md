# Developer Guide - Crowdfund AI Platform

## Table of Contents
1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Setup](#development-setup)
4. [Key Components](#key-components)
5. [API Integration](#api-integration)
6. [Testing](#testing)
7. [Best Practices](#best-practices)

## Getting Started

### Prerequisites
- Python 3.13+
- PostgreSQL
- Redis (for caching and WebSocket support)
- Node.js and npm (for frontend assets)

### Installation
```bash
# Clone the repository
git clone [repository-url]
cd crowdfund_ai

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install frontend dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## Project Structure

```
crowdfund_ai/
├── core/                   # Main application
│   ├── api/               # API endpoints
│   ├── models/            # Database models
│   ├── services/          # Business logic
│   ├── templates/         # HTML templates
│   ├── static/            # Static files
│   └── views/             # View controllers
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## Development Setup

### Environment Variables
Required environment variables:
- `DJANGO_SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `PAYSTACK_SECRET_KEY`: Paystack API key
- `AWS_ACCESS_KEY_ID`: AWS credentials (for S3)
- `AWS_SECRET_ACCESS_KEY`: AWS credentials
- `EMAIL_HOST`: SMTP server settings

### Database Setup
```bash
# Create database
createdb crowdfund_ai

# Run migrations
python manage.py migrate

# Load initial data
python manage.py loaddata initial_data.json
```

## Key Components

### 1. Investment System
- `core.models.Investment`: Handles investment records
- `core.services.investment`: Investment business logic
- `core.views.investments`: Investment-related views

### 2. Payment Integration
- `core.services.payments`: Payment processing service
- Supported providers: Paystack
- Webhook handling for payment notifications

### 3. Certificate System
- `core.services.certificate_generator`: Certificate generation
- PDF generation and verification
- Blockchain integration for verification

### 4. Escrow System
- `core.services.escrow`: Escrow management
- Automated release based on milestones
- Dispute resolution system

## API Integration

### Authentication
```python
# Example API authentication
import requests

headers = {
    'Authorization': f'Bearer {api_token}',
    'Content-Type': 'application/json'
}

response = requests.get('api/v1/investments/', headers=headers)
```

### Key Endpoints
- `/api/v1/apps/`: App listing management
- `/api/v1/investments/`: Investment operations
- `/api/v1/payments/`: Payment processing
- `/api/v1/certificates/`: Certificate management

## Testing

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific test module
python manage.py test core.tests.test_investments

# Run with coverage
coverage run manage.py test
coverage report
```

### Test Structure
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- API tests: `tests/api/`

## Best Practices

### Code Style
- Follow PEP 8 guidelines
- Use type hints for better code clarity
- Document all public methods and classes

### Security
- Never commit sensitive data
- Use environment variables for secrets
- Implement rate limiting for API endpoints
- Validate all user inputs

### Performance
- Use caching where appropriate
- Optimize database queries
- Profile slow operations
- Use async views for long-running operations

### Version Control
- Use feature branches
- Write meaningful commit messages
- Follow conventional commits format
- Review code before merging

### Error Handling
- Use appropriate HTTP status codes
- Log errors with proper context
- Implement global exception handling
- Return user-friendly error messages

### Deployment
- Use CI/CD pipelines
- Implement blue-green deployment
- Monitor application metrics
- Set up automated backups 