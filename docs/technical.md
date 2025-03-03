# Technical Documentation

## System Architecture

### Core Components

#### 1. Revenue Model
The `Revenue` model is the central component for tracking revenue entries:
```python
class Revenue(models.Model):
    app = models.ForeignKey(AppListing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)  # NGN, USD, EUR, etc.
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    is_distributed = models.BooleanField(default=False)
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    metadata = models.JSONField(default=dict)
```

#### 2. Distribution Model
The `Distribution` model handles revenue distribution records:
```python
class Distribution(models.Model):
    revenue = models.ForeignKey(Revenue, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    share_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20)
    distributed_at = models.DateTimeField(null=True)
```

### Currency Handling

#### 1. Currency Validation
- Supported currencies: NGN (primary), USD, EUR, GBP, JPY
- Exchange rates are validated for freshness (must be < 24 hours old)
- Negative exchange rates are not allowed
- Zero-decimal currencies (like JPY) must have whole number amounts

#### 2. Exchange Rate Management
- Exchange rates are fetched from external API
- Rates are cached for 1 hour to minimize API calls
- Base currency is NGN (Nigerian Naira)
- Fallback mechanism for API failures

#### 3. Currency Formatting
- Each currency has specific formatting rules:
  - NGN: ₦ symbol, 2 decimal places
  - USD: $ symbol, 2 decimal places
  - EUR: € symbol, 2 decimal places
  - GBP: £ symbol, 2 decimal places
  - JPY: ¥ symbol, 0 decimal places

### Revenue Distribution Process

#### 1. Distribution Calculation
```python
def calculate_share_distribution(app, revenue_amount):
    # Get all shareholders and their share counts
    share_ownerships = ShareOwnership.objects.filter(app=app)
    total_shares = sum(ownership.shares_owned for ownership in share_ownerships)
    
    distributions = []
    for ownership in share_ownerships:
        if ownership.shares_owned > 0:
            share_percentage = (ownership.shares_owned / total_shares) * 100
            amount = (share_percentage / 100) * revenue_amount
            distributions.append({
                'recipient': ownership.user,
                'amount': amount,
                'share_percentage': share_percentage
            })
    return distributions
```

#### 2. Distribution Processing
- Atomic transactions ensure data consistency
- Retry mechanism for failed distributions
- Notifications sent to recipients
- Transaction records created for audit trail

### Error Handling

#### 1. Validation Errors
- Currency code validation
- Exchange rate validation
- Amount format validation
- Period overlap validation

#### 2. Distribution Errors
- Insufficient shares error
- Invalid distribution amount
- Failed transaction handling
- Retry mechanism

### Testing

#### 1. Test Categories
- Basic revenue tests
- Currency validation tests
- Distribution calculation tests
- Edge case tests

#### 2. Test Coverage
- Model validation
- Service methods
- API endpoints
- Currency formatting
- Distribution processing

## Performance Considerations

### 1. Database Optimization
- Indexed fields:
  - revenue.period_start
  - revenue.period_end
  - revenue.currency
  - distribution.status

### 2. Caching Strategy
- Exchange rates cached for 1 hour
- Distribution calculations cached
- API response caching

### 3. Batch Processing
- Bulk distribution processing
- Async notification sending
- Background task processing

## Security Measures

### 1. Data Validation
- Input sanitization
- Currency code validation
- Amount range validation

### 2. Access Control
- Role-based permissions
- API authentication
- Rate limiting

### 3. Audit Trail
- Transaction logging
- Distribution history
- Exchange rate tracking 