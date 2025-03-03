# API Documentation - Crowdfund AI Platform

## Overview
The Crowdfund AI Platform API provides programmatic access to investment management, app listings, payment processing, and certificate verification features.

## Base URL
```
Production: https://api.crowdfundai.com/v1
Development: http://localhost:8000/api/v1
```

## Authentication
All API requests require authentication using Bearer tokens.

```bash
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     https://api.crowdfundai.com/v1/investments/
```

## Rate Limiting
- 1000 requests per hour for authenticated users
- 60 requests per hour for unauthenticated users
- Rate limit headers included in responses

## Endpoints

### Authentication
#### Login
```http
POST /auth/login/
```
Request:
```json
{
    "email": "user@example.com",
    "password": "secure_password"
}
```
Response:
```json
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": {
        "id": 1,
        "email": "user@example.com",
        "role": "INVESTOR"
    }
}
```

#### Register
```http
POST /auth/register/
```
Request:
```json
{
    "email": "user@example.com",
    "password": "secure_password",
    "full_name": "John Doe",
    "role": "INVESTOR"
}
```

### App Listings

#### List Apps
```http
GET /apps/
```
Parameters:
- `category` (string): Filter by category
- `status` (string): Filter by status
- `search` (string): Search term
- `page` (int): Page number
- `per_page` (int): Items per page

Response:
```json
{
    "count": 100,
    "next": "https://api.crowdfundai.com/v1/apps/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "App Name",
            "description": "App description",
            "funding_goal": "1000000.00",
            "current_funding": "500000.00",
            "status": "ACTIVE"
        }
    ]
}
```

#### Create App
```http
POST /apps/
```
Request:
```json
{
    "name": "App Name",
    "description": "Detailed description",
    "funding_goal": "1000000.00",
    "category": "FINTECH",
    "pitch_deck": "base64_encoded_file"
}
```

### Investments

#### Create Investment
```http
POST /investments/
```
Request:
```json
{
    "app_id": 1,
    "amount": "10000.00",
    "payment_method": "PAYSTACK"
}
```
Response:
```json
{
    "id": 1,
    "status": "PENDING",
    "payment_url": "https://paystack.com/pay/123xyz",
    "reference": "INV-123-456"
}
```

#### List Investments
```http
GET /investments/
```
Parameters:
- `status` (string): Filter by status
- `app_id` (int): Filter by app
- `page` (int): Page number

### Certificates

#### Generate Certificate
```http
POST /certificates/generate/
```
Request:
```json
{
    "investment_id": 1
}
```
Response:
```json
{
    "certificate_id": "CERT-123-456",
    "download_url": "https://api.crowdfundai.com/v1/certificates/CERT-123-456/download",
    "verification_url": "https://api.crowdfundai.com/v1/certificates/verify/CERT-123-456"
}
```

#### Verify Certificate
```http
GET /certificates/verify/{certificate_id}/
```
Response:
```json
{
    "valid": true,
    "details": {
        "investor": "John Doe",
        "app": "App Name",
        "percentage": "5.00",
        "date_issued": "2025-01-18T09:00:00Z"
    }
}
```

### Payment Webhooks

#### Paystack Webhook
```http
POST /payments/paystack-webhook/
```
Headers:
```
X-Paystack-Signature: hash_signature
```
Request:
```json
{
    "event": "charge.success",
    "data": {
        "reference": "INV-123-456",
        "amount": 1000000,
        "status": "success"
    }
}
```

### Analytics

#### App Analytics
```http
GET /analytics/apps/{app_id}/
```
Response:
```json
{
    "total_investments": "1000000.00",
    "investor_count": 50,
    "funding_progress": 75.5,
    "recent_activities": [
        {
            "type": "INVESTMENT",
            "amount": "10000.00",
            "timestamp": "2025-01-18T09:00:00Z"
        }
    ]
}
```

## Error Handling

### Error Codes
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Too Many Requests
- 500: Internal Server Error

### Error Response Format
```json
{
    "error": {
        "code": "INVALID_INPUT",
        "message": "Detailed error message",
        "details": {
            "field": ["Error details"]
        }
    }
}
```

## Pagination
All list endpoints support pagination:
```json
{
    "count": 100,
    "next": "https://api.crowdfundai.com/v1/resource/?page=2",
    "previous": null,
    "results": []
}
```

## Versioning
- Current version: v1
- Version specified in URL
- Deprecation notices sent via email
- 6 months support for deprecated versions

## Best Practices
1. Use HTTPS for all requests
2. Include appropriate headers
3. Handle rate limiting
4. Implement proper error handling
5. Cache responses when appropriate
6. Use pagination for large datasets

## SDKs and Libraries
- Python: `pip install crowdfundai-python`
- JavaScript: `npm install crowdfundai-js`
- PHP: `composer require crowdfundai/php-sdk`

## Support
- Email: api-support@crowdfundai.com
- Documentation: https://docs.crowdfundai.com
- Status page: https://status.crowdfundai.com 