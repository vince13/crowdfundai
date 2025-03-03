# Payment System Monitoring

## Key Metrics

### Transaction Metrics

#### Success Rate
- **Metric**: `payment.success_rate`
- **Type**: Gauge (0-100%)
- **Description**: Percentage of successful payments vs total attempts
- **Alert Threshold**: 
  - Warning: < 95%
  - Critical: < 90%
- **Calculation**: `(successful_payments / total_payments) * 100`

#### Processing Time
- **Metric**: `payment.processing_time`
- **Type**: Histogram
- **Description**: Time taken to process payments
- **Alert Threshold**:
  - Warning: > 5s
  - Critical: > 10s
- **Percentiles Tracked**: p50, p90, p95, p99

#### Volume
- **Metric**: `payment.volume`
- **Type**: Counter
- **Description**: Number of payment transactions
- **Dimensions**:
  - By status (success/failed)
  - By payment method
  - By currency

### Webhook Metrics

#### Webhook Success Rate
- **Metric**: `webhook.success_rate`
- **Type**: Gauge (0-100%)
- **Description**: Percentage of successfully processed webhooks
- **Alert Threshold**:
  - Warning: < 98%
  - Critical: < 95%

#### Webhook Processing Time
- **Metric**: `webhook.processing_time`
- **Type**: Histogram
- **Description**: Time taken to process webhooks
- **Alert Threshold**:
  - Warning: > 2s
  - Critical: > 5s

#### Webhook Volume
- **Metric**: `webhook.volume`
- **Type**: Counter
- **Description**: Number of webhook events
- **Dimensions**:
  - By event type
  - By status

### Escrow Metrics

#### Escrow Balance
- **Metric**: `escrow.balance`
- **Type**: Gauge
- **Description**: Current total funds in escrow
- **Dimensions**:
  - By app
  - By currency

#### Release Success Rate
- **Metric**: `escrow.release.success_rate`
- **Type**: Gauge (0-100%)
- **Description**: Success rate of fund releases
- **Alert Threshold**:
  - Warning: < 98%
  - Critical: < 95%

#### Release Processing Time
- **Metric**: `escrow.release.processing_time`
- **Type**: Histogram
- **Description**: Time taken to process releases
- **Alert Threshold**:
  - Warning: > 5s
  - Critical: > 10s

## Health Checks

### Payment Gateway
```python
def check_payment_gateway():
    try:
        # Test API connectivity
        response = requests.get(
            'https://api.paystack.co/ping',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'}
        )
        return response.status_code == 200
    except Exception:
        return False
```

### Webhook Endpoint
```python
def check_webhook_endpoint():
    try:
        # Test webhook endpoint
        response = requests.post(
            settings.WEBHOOK_URL,
            headers={'X-Test': 'true'},
            json={'event': 'test'}
        )
        return response.status_code == 200
    except Exception:
        return False
```

### Database Transactions
```python
def check_db_transactions():
    try:
        # Test transaction creation
        with transaction.atomic():
            test_tx = Transaction.objects.create(
                amount=0,
                status='TEST'
            )
            test_tx.delete()
        return True
    except Exception:
        return False
```

## Alerting

### Critical Alerts

1. **Payment Gateway Down**
   - Condition: Payment gateway health check fails
   - Action: Notify DevOps and Engineering leads
   - Escalation: If not resolved in 5 minutes

2. **High Payment Failure Rate**
   - Condition: Success rate < 90% in 5-minute window
   - Action: Notify Engineering team
   - Escalation: If not improved in 15 minutes

3. **Webhook Processing Issues**
   - Condition: Webhook success rate < 95% or processing time > 5s
   - Action: Notify Backend team
   - Escalation: If not resolved in 10 minutes

### Warning Alerts

1. **Degraded Payment Performance**
   - Condition: Processing time > 5s
   - Action: Notify Engineering team

2. **Increased Error Rate**
   - Condition: Error rate > 5% in 15-minute window
   - Action: Notify Backend team

3. **Low Escrow Balance**
   - Condition: Balance < minimum threshold
   - Action: Notify Finance team

## Dashboards

### Transaction Overview
- Success rate over time
- Transaction volume by status
- Processing time distribution
- Error rate by type

### Webhook Performance
- Webhook success rate
- Processing time trends
- Event volume by type
- Failed webhook analysis

### Escrow Management
- Total funds in escrow
- Release success rate
- Processing time trends
- Balance by app/currency

## Logging

### Payment Logs
```python
logger.info('Payment initiated', extra={
    'reference': payment_ref,
    'amount': amount,
    'currency': currency,
    'payment_method': method
})

logger.error('Payment failed', extra={
    'reference': payment_ref,
    'error_code': error.code,
    'error_message': str(error)
})
```

### Webhook Logs
```python
logger.info('Webhook received', extra={
    'event_type': event.type,
    'payload_size': len(payload)
})

logger.error('Webhook processing failed', extra={
    'event_type': event.type,
    'error': str(error)
})
```

## Reporting

### Daily Reports
- Transaction success rate
- Payment volume and value
- Error distribution
- Processing time averages

### Weekly Reports
- Trend analysis
- Performance comparison
- Error patterns
- System health summary

### Monthly Reports
- Business metrics
- System performance
- Resource utilization
- Improvement recommendations 