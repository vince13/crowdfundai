# Payment API Endpoints

## Investment Payments

### Create Investment Payment
```http
POST /api/v1/payments/investment/create/
```

Creates a new investment payment intent.

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "app_id": "integer",
    "percentage_amount": "decimal",
    "payment_method": "string (PAYSTACK)",
    "currency": "string (NGN, USD, EUR, GBP)"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "payment_url": "string",
    "reference": "string",
    "amount": "decimal",
    "currency": "string"
}
```

**Error Responses:**
- 400 Bad Request: Invalid input data
- 401 Unauthorized: Invalid or missing token
- 403 Forbidden: User not authorized to invest
- 404 Not Found: App not found
- 422 Unprocessable Entity: Invalid percentage amount

### Verify Investment Payment
```http
GET /api/v1/payments/verify/{reference}/
```

Verifies a payment using its reference.

**Parameters:**
- `reference` (string, required): Payment reference from payment creation

**Response (200 OK):**
```json
{
    "success": true,
    "status": "string",
    "amount": "decimal",
    "currency": "string",
    "metadata": {
        "payment_type": "string",
        "app_id": "string",
        "user_id": "string"
    }
}
```

## Escrow Operations

### Process Milestone Release
```http
POST /api/v1/payments/milestone/release/{milestone_id}/
```

Processes a milestone-based fund release.

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "release_percentage": "decimal",
    "notes": "string"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "transaction_id": "string",
    "amount_released": "decimal",
    "remaining_balance": "decimal"
}
```

### Process Refund
```http
POST /api/v1/payments/refund/
```

Processes a refund for an investment.

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "transaction_id": "string",
    "refund_percentage": "decimal",
    "reason": "string"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "refund_id": "string",
    "amount_refunded": "decimal",
    "remaining_balance": "decimal"
}
```

## Webhook Endpoints

### Paystack Webhook
```http
POST /api/v1/payments/webhook/paystack/
```

Handles Paystack payment webhooks.

**Request Headers:**
```
X-Paystack-Signature: string
Content-Type: application/json
```

**Request Body Example:**
```json
{
    "event": "charge.success",
    "data": {
        "reference": "string",
        "amount": "integer",
        "currency": "string",
        "status": "string",
        "metadata": {
            "payment_type": "string",
            "app_id": "string",
            "user_id": "string"
        }
    }
}
```

**Response (200 OK):**
```json
{
    "status": "success"
}
```

## Developer Payment Settings

### Update Payment Settings
```http
PUT /api/v1/payments/settings/
```

Updates developer payment settings.

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "payment_method": "string (BANK_TRANSFER, PAYSTACK)",
    "account_details": {
        "bank_name": "string",
        "account_number": "string",
        "account_name": "string"
    }
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "settings_id": "string",
    "verification_required": "boolean"
}
```

## Rate Limits

- Unauthenticated requests: 60 requests per hour
- Authenticated requests: 1000 requests per hour
- Webhook endpoints: 10,000 requests per hour

## Error Codes

| Code | Description |
|------|-------------|
| PAYMENT_001 | Invalid payment amount |
| PAYMENT_002 | Payment verification failed |
| PAYMENT_003 | Invalid webhook signature |
| PAYMENT_004 | Insufficient escrow funds |
| PAYMENT_005 | Invalid release percentage |
| PAYMENT_006 | Milestone not completed |
| PAYMENT_007 | Unauthorized payment action |

## Testing

Test credentials are provided for the sandbox environment:

```
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
PAYSTACK_SECRET_KEY=sk_test_xxxxx
```

Test card:
- Number: 4084 0840 8408 4081
- CVV: 408
- Expiry: 04/24
- PIN: 0000
- OTP: 123456 