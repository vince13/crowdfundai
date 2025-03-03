# Subscription Recovery API Documentation

## Overview
The Subscription Recovery API provides endpoints for managing failed payments, grace periods, and subscription reactivation processes.

## Authentication
All API endpoints require admin authentication. Include the authentication token in the request header:
```http
Authorization: Bearer <your_admin_token>
```

## Endpoints

### 1. Failed Payment Management

#### Retry Payment
```http
POST /administration/subscriptions/retry-payment/{paymentId}/
```

Attempts to retry a failed payment.

**Parameters:**
- `paymentId` (path) - ID of the failed payment to retry

**Response:**
```json
{
    "success": true,
    "payment": {
        "id": "string",
        "status": "string",
        "retry_count": "number",
        "last_retry": "datetime",
        "amount": "decimal",
        "currency": "string"
    },
    "message": "string"
}
```

**Error Responses:**
- `404 Not Found` - Payment not found
- `400 Bad Request` - Invalid payment state
- `403 Forbidden` - Insufficient permissions

### 2. Grace Period Management

#### Extend Grace Period
```http
POST /administration/subscriptions/extend-grace/{graceId}/
```

Extends an active grace period.

**Parameters:**
- `graceId` (path) - ID of the grace period
- Request Body:
  ```json
  {
      "days": "number",
      "reason": "string"
  }
  ```

**Response:**
```json
{
    "success": true,
    "grace_period": {
        "id": "string",
        "subscription_id": "string",
        "start_date": "datetime",
        "end_date": "datetime",
        "status": "string"
    }
}
```

**Error Responses:**
- `404 Not Found` - Grace period not found
- `400 Bad Request` - Invalid extension duration
- `403 Forbidden` - Insufficient permissions

#### End Grace Period
```http
POST /administration/subscriptions/end-grace/{graceId}/
```

Terminates a grace period early.

**Parameters:**
- `graceId` (path) - ID of the grace period
- Request Body:
  ```json
  {
      "reason": "string",
      "notify_user": "boolean"
  }
  ```

**Response:**
```json
{
    "success": true,
    "subscription_status": "string",
    "end_date": "datetime"
}
```

### 3. Recovery Analytics

#### Get Recovery Statistics
```http
GET /administration/subscriptions/recovery-stats/
```

Retrieves recovery-related statistics.

**Query Parameters:**
- `start_date` (optional) - Start date for statistics
- `end_date` (optional) - End date for statistics

**Response:**
```json
{
    "failed_payments_count": "number",
    "active_grace_periods": "number",
    "recovery_rate": "number",
    "average_recovery_time": "number",
    "total_recovered_amount": "decimal",
    "period_stats": {
        "start_date": "datetime",
        "end_date": "datetime"
    }
}
```

#### Get Detailed Recovery Report
```http
GET /administration/subscriptions/recovery-report/
```

Generates a detailed recovery report.

**Query Parameters:**
- `period` (optional) - Report period (daily, weekly, monthly)
- `format` (optional) - Response format (json, csv)

**Response:**
```json
{
    "report_data": [{
        "date": "datetime",
        "failed_count": "number",
        "recovered_count": "number",
        "recovery_rate": "number",
        "total_amount": "decimal"
    }],
    "summary": {
        "total_failed": "number",
        "total_recovered": "number",
        "overall_rate": "number"
    }
}
```

## Webhook Events

### Payment Recovery Events
The API sends webhook notifications for the following events:

```json
{
    "event": "payment.recovery.succeeded",
    "data": {
        "payment_id": "string",
        "subscription_id": "string",
        "amount": "decimal",
        "recovered_at": "datetime"
    }
}
```

```json
{
    "event": "payment.recovery.failed",
    "data": {
        "payment_id": "string",
        "subscription_id": "string",
        "error": "string",
        "retry_count": "number"
    }
}
```

```json
{
    "event": "grace_period.started",
    "data": {
        "grace_period_id": "string",
        "subscription_id": "string",
        "start_date": "datetime",
        "end_date": "datetime"
    }
}
```

## Error Handling

### Error Response Format
```json
{
    "success": false,
    "error": {
        "code": "string",
        "message": "string",
        "details": {}
    }
}
```

### Common Error Codes
- `FP001` - Payment retry failed - Invalid payment method
- `FP002` - Payment retry failed - Insufficient funds
- `GP001` - Grace period extension failed
- `GP002` - Invalid grace period duration

## Rate Limiting

- Rate limit: 100 requests per minute
- Rate limit header: `X-RateLimit-Limit`
- Remaining requests: `X-RateLimit-Remaining`
- Reset time: `X-RateLimit-Reset`

## Testing

### Test Endpoints
```http
POST /administration/subscriptions/test/retry-payment/
```
Test payment retry functionality with mock data.

```http
POST /administration/subscriptions/test/grace-period/
```
Test grace period management with mock data.

### Test Credentials
```json
{
    "test_admin_token": "test_admin_xyz",
    "test_payment_id": "test_payment_123",
    "test_grace_id": "test_grace_456"
}
```

## SDK Examples

### Python Example
```python
import requests

def retry_payment(payment_id, token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        f'/administration/subscriptions/retry-payment/{payment_id}/',
        headers=headers
    )
    return response.json()
```

### JavaScript Example
```javascript
async function extendGracePeriod(graceId, days, token) {
    const response = await fetch(
        `/administration/subscriptions/extend-grace/${graceId}/`,
        {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ days })
        }
    );
    return response.json();
}
```

## Best Practices

1. **Error Handling**
   - Always check for error responses
   - Implement exponential backoff for retries
   - Log all failed recovery attempts

2. **Security**
   - Use HTTPS for all API calls
   - Rotate admin tokens regularly
   - Validate all input parameters

3. **Performance**
   - Cache recovery statistics
   - Batch recovery operations
   - Monitor API response times 