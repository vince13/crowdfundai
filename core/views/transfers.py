from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from ..models import ShareTransfer, ShareOwnership, AppListing

@login_required
def share_transfer_list(request):
    """List percentages available for transfer and user's transfer history."""
    # Get app filter if provided
    app_id = request.GET.get('app')
    app = None
    if app_id:
        app = get_object_or_404(AppListing, pk=app_id)
    
    # Get user's share transfers (both as seller and buyer)
    transfers_selling = ShareTransfer.objects.filter(
        seller=request.user
    )
    if app:
        transfers_selling = transfers_selling.filter(app=app)
    transfers_selling = transfers_selling.select_related('app', 'buyer')
    
    transfers_buying = ShareTransfer.objects.filter(
        buyer=request.user
    )
    if app:
        transfers_buying = transfers_buying.filter(app=app)
    transfers_buying = transfers_buying.select_related('app', 'seller')
    
    # Get available transfers for purchase
    available_transfers = ShareTransfer.objects.filter(
        status=ShareTransfer.Status.PENDING,
        buyer__isnull=True
    ).exclude(seller=request.user)
    if app:
        available_transfers = available_transfers.filter(app=app)
    available_transfers = available_transfers.select_related('app', 'seller')
    
    # Get user's share ownerships that are eligible for transfer
    ownerships = ShareOwnership.objects.filter(
        user=request.user,
        percentage_owned__gt=0
    )
    if app:
        ownerships = ownerships.filter(app=app)
    ownerships = ownerships.select_related('app')
    
    # Check lock-in period for each ownership
    transferable_percentages = []
    for ownership in ownerships:
        investment = ownership.app.investment_set.filter(
            investor=request.user
        ).order_by('created_at').first()
        
        if investment:
            lock_in_end_date = investment.created_at + timezone.timedelta(
                days=ownership.app.lock_in_period
            )
            can_transfer = timezone.now() >= lock_in_end_date
            
            transferable_percentages.append({
                'ownership': ownership,
                'can_transfer': can_transfer,
                'lock_in_end_date': lock_in_end_date if not can_transfer else None
            })
    
    return render(request, 'core/transfers/list.html', {
        'app': app,
        'transfers_selling': transfers_selling,
        'transfers_buying': transfers_buying,
        'available_transfers': available_transfers,
        'transferable_percentages': transferable_percentages,
        'user_currency': 'NGN'
    })

@login_required
def create_transfer(request, app_id):
    """Create a new percentage transfer listing."""
    app = get_object_or_404(AppListing, pk=app_id)
    ownership = get_object_or_404(ShareOwnership, user=request.user, app=app)

    # Check if shares are still in lock-in period
    investment = app.investment_set.filter(
        investor=request.user
    ).order_by('created_at').first()

    if investment:
        lock_in_end_date = investment.created_at + timezone.timedelta(
            days=app.lock_in_period
        )
        can_transfer = timezone.now() >= lock_in_end_date

        if not can_transfer:
            days_remaining = (lock_in_end_date - timezone.now()).days
            messages.error(
                request, 
                f'Your investment is still in lock-in period. {days_remaining} days remaining until you can transfer.'
            )
            return redirect('core:share_transfer_list')
    
    if request.method == 'POST':
        try:
            # Get and validate percentage amount
            percentage_amount = request.POST.get('percentage_amount', '')
            if not percentage_amount:
                messages.error(request, 'Please enter the percentage amount to transfer.')
                return render(request, 'core/transfers/create.html', {
                    'app': app,
                    'ownership': ownership,
                    'can_transfer': True
                })
            
            percentage_amount = float(percentage_amount)
            if percentage_amount <= 0 or percentage_amount > ownership.percentage_owned:
                messages.error(request, 'Invalid percentage amount.')
                return render(request, 'core/transfers/create.html', {
                    'app': app,
                    'ownership': ownership,
                    'can_transfer': True
                })

            # Get and validate price per percentage
            price_per_percentage = request.POST.get('price_per_percentage', '')
            if not price_per_percentage:
                messages.error(request, 'Please enter the price per percentage.')
                return render(request, 'core/transfers/create.html', {
                    'app': app,
                    'ownership': ownership,
                    'can_transfer': True
                })
            
            price_per_percentage = float(price_per_percentage)
            if price_per_percentage < float(app.price_per_percentage):
                messages.error(request, f'Price per percentage cannot be less than ₦{app.price_per_percentage:,.2f}')
                return render(request, 'core/transfers/create.html', {
                    'app': app,
                    'ownership': ownership,
                    'can_transfer': True
                })

            # Create the transfer
            transfer = ShareTransfer.objects.create(
                app=app,
                seller=request.user,
                percentage_amount=percentage_amount,
                price_per_percentage=price_per_percentage,
                total_amount=percentage_amount * price_per_percentage,
                status=ShareTransfer.Status.PENDING
            )

            messages.success(request, 'Share transfer created successfully.')
            return redirect('core:share_transfer_list')

        except ValueError:
            messages.error(request, 'Please enter valid numbers for percentage and price.')
            return render(request, 'core/transfers/create.html', {
                'app': app,
                'ownership': ownership,
                'can_transfer': True
            })
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'core/transfers/create.html', {
                'app': app,
                'ownership': ownership,
                'can_transfer': True
            })
    
    return render(request, 'core/transfers/create.html', {
        'app': app,
        'ownership': ownership,
        'can_transfer': True
    })

@login_required
def purchase_transfer(request, transfer_id):
    """Purchase percentage ownership from a transfer listing."""
    transfer = get_object_or_404(ShareTransfer, id=transfer_id)
    
    # Check if transfer is still available
    if transfer.status != ShareTransfer.Status.PENDING:
        messages.error(request, 'This percentage transfer is no longer available.')
        return redirect('core:share_transfer_list')
    
    # Check if user is not the seller
    if request.user == transfer.seller:
        messages.error(request, 'You cannot purchase your own percentage ownership.')
        return redirect('core:share_transfer_list')
    
    # Check if user has enough funds (this would be implemented based on your user balance system)
    # For now, we'll just proceed with the payment
    
    return render(request, 'core/transfers/purchase.html', {
        'transfer': transfer,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
        'payment_gateway_mode': settings.PAYMENT_GATEWAY_MODE
    })

@login_required
def cancel_transfer(request, transfer_id):
    """Cancel a pending percentage transfer."""
    transfer = get_object_or_404(ShareTransfer, pk=transfer_id, seller=request.user)
    
    if transfer.status != ShareTransfer.Status.PENDING:
        messages.error(request, 'Only pending transfers can be cancelled.')
        return redirect('core:share_transfer_list')
    
    transfer.status = ShareTransfer.Status.CANCELLED
    transfer.save()
    
    messages.success(request, 'Transfer cancelled successfully.')
    return redirect('core:share_transfer_list') 