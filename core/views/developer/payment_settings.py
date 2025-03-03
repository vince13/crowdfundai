from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.utils import timezone
from ...models.payment_info import DeveloperPaymentInfo, VerificationDocument
from ...services.payments import PaymentService
import logging
import os

logger = logging.getLogger(__name__)

@login_required
def payment_info_setup(request):
    """View for developers to set up their payment information."""
    try:
        payment_info = request.user.payment_info
    except DeveloperPaymentInfo.DoesNotExist:
        payment_info = None

    if request.method == 'POST':
        # Log all POST data for debugging
        logger.info(f"POST data received: {request.POST}")
        
        payment_method = request.POST.get('payment_method')
        logger.info(f"Payment method selected: {payment_method}")
        
        account_details = {}

        if payment_method == 'bank_transfer':
            # Validate required fields for bank transfer
            bank_name = request.POST.get('bank_name', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            account_name = request.POST.get('account_name', '').strip()
            
            # Log the received data for debugging
            logger.info(f"Bank transfer data: bank_name='{bank_name}', account_number='{account_number}', account_name='{account_name}'")
            
            if not bank_name:
                logger.warning("Bank name is missing")
                messages.error(request, 'Please enter bank name')
                return redirect('core:payment_setup')
                
            if not account_number:
                logger.warning("Account number is missing")
                messages.error(request, 'Please enter account number')
                return redirect('core:payment_setup')
                
            if not account_name:
                logger.warning("Account name is missing")
                messages.error(request, 'Please enter account name')
                return redirect('core:payment_setup')
            
            account_details = {
                'bank_name': bank_name,
                'account_number': account_number,
                'account_name': account_name
            }
            
            # Log the account details being saved
            logger.info(f"Saving bank transfer details: {account_details}")
            
        elif payment_method == 'paystack':
            # Get bank name from the bank list
            bank_code = request.POST.get('bank_code')
            email = request.POST.get('email', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            
            if not bank_code:
                messages.error(request, 'Please select a bank')
                return redirect('core:payment_setup')
                
            if not email:
                messages.error(request, 'Please enter email address')
                return redirect('core:payment_setup')
                
            if not account_number:
                messages.error(request, 'Please enter account number')
                return redirect('core:payment_setup')
            
            # Create Paystack recipient
            recipient = PaymentService.create_transfer_recipient(
                name=request.user.get_full_name() or request.user.username,
                email=email,
                account_number=account_number,
                bank_code=bank_code
            )
            
            if not recipient.get('status'):
                error_message = recipient.get('message', 'Failed to verify account details')
                messages.error(request, error_message)
                return redirect('core:payment_setup')
                
            # Get bank name from bank list
            bank_name = None
            banks = PaymentService.get_bank_list()
            for bank in banks:
                if bank['code'] == bank_code:
                    bank_name = bank['name']
                    break
                
            account_details = {
                'recipient_code': recipient['data']['recipient_code'],
                'email': email,
                'account_number': account_number,
                'bank_code': bank_code,
                'bank_name': bank_name,
                'account_name': recipient['data'].get('account_name', '')
            }
        
        else:
            messages.error(request, 'Invalid payment method selected')
            return redirect('core:payment_setup')
            
        # Save the payment information
        try:
            if payment_info:
                payment_info.payment_method = payment_method
                payment_info.account_details = account_details
                payment_info.verified = False
                payment_info.verification_status = 'pending'
                payment_info.save()
            else:
                DeveloperPaymentInfo.objects.create(
                    developer=request.user,
                    payment_method=payment_method,
                    account_details=account_details,
                    verification_status='pending'
                )
            messages.success(request, 'Payment information updated successfully')
            return redirect('core:verify_payment_account')
        except ValidationError as e:
            logger.error(f"Validation error saving payment info: {str(e)}")
            messages.error(request, str(e))
            return redirect('core:payment_setup')

    # Always get the bank list for Paystack
    banks = PaymentService.get_bank_list()
    
    return render(request, 'core/developer/payment_setup.html', {
        'payment_info': payment_info,
        'banks': banks
    })

@login_required
def verify_payment_account(request):
    """View for verifying developer's payment account."""
    payment_info = get_object_or_404(DeveloperPaymentInfo, developer=request.user)
    
    if request.method == 'POST':
        if payment_info.payment_method == 'bank_transfer':
            # For bank transfer, handle document upload
            verification_document = request.FILES.get('verification_document')
            document_type = request.POST.get('document_type')
            
            # Log request data for debugging
            logger.info(f"POST data: {request.POST}")
            logger.info(f"FILES data: {request.FILES}")
            
            if not verification_document:
                logger.warning("No verification document found in request")
                messages.error(request, 'Please upload a verification document')
                return redirect('core:verify_payment_account')
                
            if not document_type:
                logger.warning("No document type selected")
                messages.error(request, 'Please select document type')
                return redirect('core:verify_payment_account')
            
            # Validate file type
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            file_ext = os.path.splitext(verification_document.name)[1].lower()
            
            logger.info(f"File extension: {file_ext}")
            
            if file_ext not in allowed_extensions:
                logger.warning(f"Invalid file type: {file_ext}")
                messages.error(request, 'Invalid file type. Please upload PDF, JPG, or PNG files only.')
                return redirect('core:verify_payment_account')

            # Validate file size
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            if verification_document.size > max_size:
                logger.warning(f"File too large: {verification_document.size} bytes")
                messages.error(request, 'File size must be less than 5MB.')
                return redirect('core:verify_payment_account')
            
            # Create verification document
            try:
                doc = VerificationDocument.objects.create(
                    payment_info=payment_info,
                    document_type=document_type,
                    file=verification_document
                )
                logger.info(f"Created verification document: {doc.id}")
                
                # Update payment info status
                payment_info.verification_status = 'under_review'
                payment_info.save()
                logger.info(f"Updated payment info status to under_review")
                
                messages.success(request, 'Verification document submitted for review')
                return redirect('core:developer_dashboard')
                
            except Exception as e:
                logger.error(f"Error saving verification document: {str(e)}", exc_info=True)
                messages.error(request, 'Failed to upload verification document')
                return redirect('core:verify_payment_account')
        
        elif payment_info.payment_method == 'paystack':
            # Verify Paystack recipient
            recipient_code = payment_info.account_details.get('recipient_code')
            if recipient_code:
                verification = PaymentService.verify_transfer_recipient(recipient_code)
                if verification.get('status'):
                    payment_info.verified = True
                    payment_info.verification_status = 'verified'
                    payment_info.verified_at = timezone.now()
                    payment_info.save()
                    messages.success(request, 'Payment account verified successfully')
                    return redirect('core:developer_dashboard')
                else:
                    messages.error(request, 'Failed to verify payment account')
    
    return render(request, 'core/developer/payment_verification.html', {
        'payment_info': payment_info
    })

@login_required
@require_POST
def update_payment_info(request):
    """AJAX view for updating payment information."""
    try:
        payment_info = request.user.payment_info
    except DeveloperPaymentInfo.DoesNotExist:
        return JsonResponse({'error': 'Payment info not found'}, status=404)
    
    payment_method = request.POST.get('payment_method')
    if not payment_method:
        return JsonResponse({'error': 'Payment method required'}, status=400)
    
    try:
        account_details = {}
        if payment_method == 'bank_transfer':
            account_details = {
                'bank_name': request.POST.get('bank_name'),
                'account_number': request.POST.get('account_number'),
                'account_name': request.POST.get('account_name')
            }
        elif payment_method == 'paystack':
            # Get bank name from the bank list
            bank_code = request.POST.get('bank_code')
            bank_name = None
            banks = PaymentService.get_bank_list()
            for bank in banks:
                if bank['code'] == bank_code:
                    bank_name = bank['name']
                    break
            
            account_details = {
                'recipient_code': request.POST.get('recipient_code'),
                'email': request.POST.get('email'),
                'account_number': request.POST.get('account_number'),
                'bank_code': bank_code,
                'bank_name': bank_name
            }
        
        payment_info.payment_method = payment_method
        payment_info.account_details = account_details
        payment_info.verified = False
        payment_info.verification_status = 'pending'
        payment_info.save()
        
        return JsonResponse({'status': 'success'})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400) 