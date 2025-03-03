# Payment System Documentation

## Overview
The payment system handles all financial transactions in the platform, including investments, share transfers, and revenue distributions. It uses Paystack as the primary payment gateway and implements a secure escrow system.

## Components

### 1. Payment Gateway (Paystack)
- **Initialization**: Creates payment intents for transactions
- **Verification**: Validates payment completions
- **Webhook Handling**: Processes asynchronous payment notifications
- **Supported Payment Methods**: Card, Bank Transfer, USSD, QR, Mobile Money

### 2. Escrow System
- **Transaction Types**:
  - Deposits: Initial investment funds
  - Releases: Milestone-based fund releases
  - Refunds: Full or partial refund processing
- **Features**:
  - Multi-signature approval
  - Milestone tracking
  - Dispute resolution
  - Transaction reporting

### 3. Revenue Distribution
- Automated calculation of share distributions
- Support for multiple recipients
- Transaction history tracking
- Monthly revenue reporting

## Security Features

### Payment Security
- Payment signature verification
- Secure webhook handling
- Rate limiting
- Transaction validation
- Atomic database operations

### Data Protection
- Encrypted payment information
- Secure API key handling
- Environment-based configuration

## Integration Guide

### 1. Creating a Payment

```python
from services.payments import PaymentService

# Initialize payment
payment = PaymentService.create_payment(
    amount=1000.00,
    currency='NGN',
    metadata={
        'payment_type': 'investment',
        'app_id': app.id,
        'user_id': user.id
    }
)

# Get payment URL
payment_url = payment['payment_url']
```

### 2. Handling Webhooks

```python
@csrf_exempt
@require_POST
def paystack_webhook(request):
    # Verify signature
    is_valid = PaymentService.verify_signature(
        request.body,
        request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    )
    
    if not is_valid:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
        
    # Process webhook
    event = json.loads(request.body)
    if event.get('event') == 'charge.success':
        handle_successful_payment(event['data'])
```

### 3. Processing Escrow Transactions

```python
from services.escrow import EscrowService

# Create escrow transaction
transaction = EscrowService.process_deposit(
    app=app,
    investor=user,
    amount=Decimal('1000.00'),
    currency='NGN',
    payment_gateway='PAYSTACK',
    gateway_reference='ref_123'
)

# Process milestone release
EscrowService.process_release(
    transaction,
    milestone=milestone,
    release_percentage=Decimal('25.00')
)
```

## Error Handling

### Common Error Codes
- `PAYMENT_FAILED`: Payment processing failed
- `INVALID_SIGNATURE`: Invalid webhook signature
- `INSUFFICIENT_FUNDS`: Insufficient funds in escrow
- `INVALID_AMOUNT`: Invalid payment amount
- `UNAUTHORIZED`: Unauthorized payment action

### Error Response Format
```json
{
    "error": {
        "code": "PAYMENT_FAILED",
        "message": "Payment processing failed",
        "details": {
            "reason": "Insufficient funds",
            "transaction_ref": "ref_123"
        }
    }
}
```

## Testing

### Unit Tests
- Payment initialization
- Webhook signature verification
- Escrow transaction processing
- Revenue distribution calculation

### Integration Tests
- End-to-end payment flow
- Webhook handling
- Escrow system operations
- Multi-currency support

## Monitoring

### Health Checks
- Payment gateway connectivity
- Webhook endpoint availability
- Database transaction integrity
- Redis connection for WebSocket

### Metrics
- Transaction success rate
- Payment processing time
- Webhook processing time
- Error rate by type

## Configuration

### Environment Variables
```bash
PAYSTACK_SECRET_KEY=sk_test_xxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
PAYMENT_GATEWAY_MODE=test
ESCROW_RELEASE_THRESHOLD=1000000
```

### Feature Flags
```python
FEATURES = {
    'ENABLE_AUTOMATIC_RELEASES': False,
    'ENABLE_MULTI_CURRENCY': True,
    'ENABLE_DISPUTE_RESOLUTION': True
}
``` 