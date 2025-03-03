from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import AppListing, ShareOwnership, AppComment  # Use existing AppComment
from ..forms import AppListingForm, AIAssessmentForm, AdvertisementForm, AppForSaleForm
from django.urls import reverse
from django.http import JsonResponse
import json
from django.utils import timezone
from django.views.generic import ListView
from django.db.models import Q, Sum, Count, F
from ..models import Blog, BlogCategory, Advertisement, CommunityVote
from django.contrib.admin.views.decorators import staff_member_required
from ..services.notifications import NotificationService
from django.conf import settings
from django.views.decorators.http import require_POST, require_GET
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..services.payments import PaymentService
import logging
from ..models import User, Investment
from ..models.payment_info import DeveloperPaymentInfo
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
import csv
from django.core.mail import send_mail, EmailMessage
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from ..models.base import AppTeamMember
from ..forms import AppTeamMemberForm
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from ..models import AppMessage
from django.contrib.contenttypes.models import ContentType
from ..models import Report

logger = logging.getLogger(__name__)

def format_naira(amount):
    """Format amount in Naira"""
    if amount is None:
        return '-'
    return f"₦{float(amount):,.2f}"

def app_list(request):
    """List all approved apps."""
    current_type = request.GET.get('type', 'LISTED')
    
    # Base query for apps
    if current_type == 'FUNDED':
        apps = AppListing.objects.filter(
            Q(status=AppListing.Status.FUNDED) |
            Q(status=AppListing.Status.COMPLETED)
        )
    else:
        apps = AppListing.objects.filter(status=AppListing.Status.ACTIVE)
        
        # Filter based on type
        if current_type == 'NOMINATED':
            # Include both nominated and community apps
            apps = apps.filter(
                Q(listing_type=AppListing.ListingType.NOMINATED) |
                Q(listing_type=AppListing.ListingType.COMMUNITY)
            )
        elif current_type == 'LISTED':
            # Only show listed apps
            apps = apps.filter(listing_type=AppListing.ListingType.LISTED)
    
    apps = apps.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(apps, 9)  # Show 9 apps per page
    page = request.GET.get('page')
    
    try:
        apps = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        apps = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        apps = paginator.page(paginator.num_pages)
    
    # Format amounts in Naira and sync remaining percentages
    for app in apps:
        # Sync remaining percentage with actual investments
        app.sync_remaining_percentage()
        app.formatted_price = format_naira(app.price_per_percentage)
        app.formatted_funding_goal = format_naira(app.funding_goal)
    
    return render(request, 'core/apps/list.html', {
        'apps': apps,
        'current_type': current_type
    })

@login_required
def app_create(request):
    # Allow both developers and admins to create apps
    if not (request.user.is_developer() or request.user.is_staff):
        messages.error(request, 'Only developers and administrators can create app listings.')
        return redirect('core:home')
    
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # Set listing_type based on user role
        if not request.user.is_staff:
            post_data['listing_type'] = AppListing.ListingType.LISTED
        elif 'listing_type' not in post_data or not post_data['listing_type']:
            # Set default listing_type for admin if not provided
            post_data['listing_type'] = AppListing.ListingType.NOMINATED
        
        form = AppListingForm(post_data)
        print("Form Data:", post_data)  # Debug print
        
        if form.is_valid():
            try:
                app = form.save(commit=False)
                app.developer = request.user
                app.status = AppListing.Status.PENDING
                app.remaining_percentage = app.available_percentage
                app.exchange_rate = app.get_current_exchange_rate()
                
                # Set nomination fields if it's a nominated app (admin only)
                if request.user.is_staff:
                    listing_type = form.cleaned_data.get('listing_type')
                    if listing_type == AppListing.ListingType.NOMINATED:
                        app.nominated_by = request.user
                        app.nomination_date = timezone.now()
                        app.development_stage = AppListing.DevelopmentStage.NOMINATED
                
                app.save()
                
                # Send notification to admins about new app submission
                NotificationService.notify_app_submission(app)
                
                messages.success(
                    request, 
                    'App listing created successfully! It will be reviewed shortly.'
                )
                return redirect('core:app_detail', pk=app.pk)
            except Exception as e:
                print(f"Error saving app: {str(e)}")  # Debug print
                messages.error(request, f'Error creating app listing: {str(e)}')
        else:
            print("Form Errors:", form.errors)  # Debug print
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AppListingForm()
        
        # Remove listing_type field for developers
        if not request.user.is_staff:
            if 'listing_type' in form.fields:
                del form.fields['listing_type']
        else:
            # Set default value for admin users
            form.initial['listing_type'] = AppListing.ListingType.NOMINATED
    
    return render(request, 'core/apps/create.html', {'form': form})

def app_detail(request, pk):
    """Display app details."""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Increment view count
    app.view_count += 1
    app.save()
    
    # Get user's share ownership if any
    user_ownership = None
    if request.user.is_authenticated:
        user_ownership = ShareOwnership.objects.filter(
            user=request.user,
            app=app
        ).first()
    
    # Get message-related context
    user_has_messages = False
    unread_message_count = 0
    if request.user.is_authenticated:
        user_has_messages = AppMessage.objects.filter(
            app=app
        ).filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).exists()
        
        if request.user == app.developer:
            unread_message_count = AppMessage.objects.filter(
                app=app,
                recipient=request.user,
                is_read=False
            ).count()
    
    context = {
        'app': app,
        'user_ownership': user_ownership,
        'user_has_messages': user_has_messages,
        'unread_message_count': unread_message_count,
    }
    
    return render(request, 'core/apps/detail.html', context)

@login_required
def app_edit(request, pk):
    app = get_object_or_404(AppListing, pk=pk)
    
    # Check if user is the app's developer
    if request.user != app.developer:
        messages.error(request, 'You can only edit your own apps.')
        return redirect('core:app_detail', pk=pk)
    
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # Set listing_type based on user role
        if not request.user.is_staff:
            post_data['listing_type'] = AppListing.ListingType.LISTED
        elif 'listing_type' not in post_data or not post_data['listing_type']:
            # Set default listing_type for admin if not provided
            post_data['listing_type'] = AppListing.ListingType.NOMINATED
        
        form = AppListingForm(post_data, instance=app)
        if form.is_valid():
            form.save()
            messages.success(request, 'App listing updated successfully.')
            return redirect('core:app_detail', pk=pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AppListingForm(instance=app)
        
        # Remove listing_type field for developers
        if not request.user.is_staff:
            if 'listing_type' in form.fields:
                del form.fields['listing_type']
    
    return render(request, 'core/apps/create.html', {
        'form': form,
        'app': app,
        'is_edit': True  # Flag to indicate this is an edit operation
    })

@login_required
def app_insights_view(request, pk):
    """View for displaying AI insights for an app"""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Check if AI assessment exists
    if not hasattr(app, 'ai_assessment'):
        if request.user == app.developer:
            messages.warning(request, 'Please complete the AI assessment first.')
            return redirect('core:app_detail', pk=pk)
        else:
            messages.warning(request, 'AI insights not available for this app yet.')
            return redirect('core:app_detail', pk=pk)
    
    # Now we can safely access app.ai_assessment
    assessment = app.ai_assessment
    
    # Get insights data
    insights_data = {
        'technical_score': calculate_technical_score(assessment),
        'market_score': calculate_market_score(assessment),
        'team_score': calculate_team_score(assessment),
        'overall_score': calculate_overall_score(assessment),
        'recommendations': generate_recommendations(assessment),
        'risk_analysis': analyze_risks(assessment)
    }
    
    return render(request, 'core/apps/insights.html', {
        'app': app,
        'assessment': assessment,
        'insights': insights_data,
        'page_title': f'AI Insights - {app.name}'
    })

def calculate_technical_score(assessment):
    """Calculate technical assessment score"""
    return assessment.innovation_score if assessment.innovation_score is not None else 0

def calculate_market_score(assessment):
    """Calculate market assessment score"""
    return assessment.market_potential_score if assessment.market_potential_score is not None else 0

def calculate_team_score(assessment):
    """Calculate team assessment score"""
    return assessment.execution_capability_score if assessment.execution_capability_score is not None else 0

def calculate_overall_score(assessment):
    """Calculate overall assessment score"""
    return assessment.overall_score if assessment.overall_score is not None else 0

def generate_recommendations(assessment):
    """Generate recommendations based on assessment"""
    recommendations = []
    
    # Technical recommendations
    if assessment.technical_analysis:
        tech_analysis = assessment.technical_analysis
        if isinstance(tech_analysis, str):
            tech_analysis = json.loads(tech_analysis)
        
        # Add recommendations based on tech stack
        if 'stack' in tech_analysis:
            stack = tech_analysis['stack']
            if isinstance(stack, dict) and 'ai_framework' in stack:
                recommendations.append({
                    'category': 'Technical',
                    'title': 'AI Framework Optimization',
                    'description': f'Consider optimizing your use of {stack["ai_framework"]}'
                })
    
    # Market recommendations
    if assessment.market_analysis:
        market_analysis = assessment.market_analysis
        if isinstance(market_analysis, str):
            market_analysis = json.loads(market_analysis)
        
        if 'market_size' in market_analysis and 'local' in market_analysis['market_size'].lower():
            recommendations.append({
                'category': 'Market',
                'title': 'Market Expansion',
                'description': 'Consider expanding to regional markets'
            })
    
    return recommendations

def analyze_risks(assessment):
    """Analyze risks based on assessment"""
    risks = []
    
    # Parse risk factors from risk analysis
    if assessment.risk_analysis:
        risk_analysis = assessment.risk_analysis
        if isinstance(risk_analysis, str):
            risk_analysis = json.loads(risk_analysis)
        
        # Add technical risks
        if 'technical_risks' in risk_analysis:
            for risk in risk_analysis['technical_risks']:
                risks.append({
                    'category': 'Technical',
                    'risk': risk,
                    'severity': 'Medium',  # You can add severity calculation logic
                    'mitigation': 'Implement proper technical controls and monitoring'
                })
        
        # Add market risks
        if 'market_risks' in risk_analysis:
            for risk in risk_analysis['market_risks']:
                risks.append({
                    'category': 'Market',
                    'risk': risk,
                    'severity': 'Medium',
                    'mitigation': 'Develop market adaptation strategies'
                })
        
        # Add operational risks
        if 'operational_risks' in risk_analysis:
            for risk in risk_analysis['operational_risks']:
                risks.append({
                    'category': 'Operational',
                    'risk': risk,
                    'severity': 'Medium',
                    'mitigation': 'Establish operational procedures and contingency plans'
                })
    
    return risks

@login_required
def ai_assessment(request, pk):
    app = get_object_or_404(AppListing, pk=pk, developer=request.user)
    
    if request.method == 'POST':
        form = AIAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.app = app
            assessment.save()
            messages.success(request, 'AI Assessment completed! You can now view AI insights.')
            return JsonResponse({
                'status': 'success',
                'redirect': reverse('core:app_insights', args=[pk])
            })
        return JsonResponse({'status': 'error', 'errors': form.errors})
    
    form = AIAssessmentForm()
    return render(request, 'core/apps/ai_assessment_form.html', {
        'form': form,
        'app': app
    })

class BlogListView(ListView):
    model = Blog
    template_name = 'core/blog/list.html'
    context_object_name = 'posts'
    paginate_by = 10

    def get_queryset(self):
        queryset = Blog.objects.filter(status=Blog.Status.PUBLISHED)
        
        # Handle search
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(content__icontains=q) |
                Q(excerpt__icontains=q)
            )
        
        # Handle category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = BlogCategory.objects.all()
        
        # Add current advertisements
        today = timezone.now().date()
        context['main_ad'] = Advertisement.objects.filter(
            position='main',
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
        
        context['sidebar_ad'] = Advertisement.objects.filter(
            position='sidebar',
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        ).first()
        
        return context 

@login_required
def ad_list(request):
    """View for listing advertisements"""
    if request.user.is_staff:
        # Staff sees all ads with filters
        status = request.GET.get('status', '')
        if status:
            ads = Advertisement.objects.filter(status=status)
        else:
            ads = Advertisement.objects.all()
    else:
        # Users see only their own ads
        ads = Advertisement.objects.filter(advertiser=request.user)
    
    ads = ads.order_by('-created_at')
    return render(request, 'core/ads/list.html', {'ads': ads})

@login_required
def ad_create(request, position=None):
    """View for creating a new advertisement"""
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, user=request.user)
        if form.is_valid():
            ad = form.save(commit=False)
            ad.advertiser = request.user
            ad.price = ad.calculate_price()
            ad.save()
            
            # Redirect to payment
            return redirect('core:ad_payment', pk=ad.pk)
    else:
        initial = {}
        if position:
            initial['position'] = position
        form = AdvertisementForm(user=request.user, initial=initial)
    
    return render(request, 'core/ads/form.html', {
        'form': form,
        'is_new': True
    })

@login_required
def ad_edit(request, pk):
    """View for editing an advertisement"""
    ad = get_object_or_404(Advertisement, pk=pk)
    
    # Only owner or staff can edit
    if not (request.user == ad.advertiser or request.user.is_staff):
        messages.error(request, 'You do not have permission to edit this advertisement.')
        return redirect('core:ad_list')
    
    # Can't edit if already paid
    if ad.payment_status == 'PAID':
        messages.error(request, 'Paid advertisements cannot be edited.')
        return redirect('core:ad_list')
    
    if request.method == 'POST':
        form = AdvertisementForm(request.POST, instance=ad, user=request.user)
        if form.is_valid():
            ad = form.save(commit=False)
            # Recalculate price if dates changed
            new_price = ad.calculate_price()
            if new_price != ad.price:
                ad.price = new_price
                ad.payment_status = 'UNPAID'
            ad.save()
            messages.success(request, 'Advertisement updated successfully.')
            return redirect('core:ad_list')
    else:
        form = AdvertisementForm(instance=ad, user=request.user)
    
    return render(request, 'core/ads/form.html', {
        'form': form,
        'ad': ad,
        'is_new': False
    })

@login_required
def ad_delete(request, pk):
    """View for deleting an advertisement"""
    ad = get_object_or_404(Advertisement, pk=pk)
    
    # Only owner or staff can delete
    if not (request.user == ad.advertiser or request.user.is_staff):
        messages.error(request, 'You do not have permission to delete this advertisement.')
        return redirect('core:ad_list')
    
    # Can't delete if already paid and active
    if ad.payment_status == 'PAID' and ad.is_current():
        messages.error(request, 'Active paid advertisements cannot be deleted.')
        return redirect('core:ad_list')
    
    ad.delete()
    messages.success(request, 'Advertisement deleted successfully.')
    return redirect('core:ad_list')

@login_required
def ad_payment(request, pk):
    """View for handling advertisement payment"""
    ad = get_object_or_404(Advertisement, pk=pk, advertiser=request.user)
    
    if ad.payment_status == 'PAID':
        messages.info(request, 'This advertisement has already been paid for.')
        return redirect('core:ad_list')
    
    if request.method == 'POST':
        # Initialize payment with Paystack
        try:
            paystack = utils.PaystackAPI()
            response = paystack.transaction.initialize(
                email=request.user.email,
                amount=int(ad.price * 100),  # Convert to kobo
                callback_url=request.build_absolute_uri(
                    reverse('core:ad_payment_verify', kwargs={'pk': ad.pk})
                ),
                metadata={
                    'ad_id': ad.pk,
                    'type': 'advertisement'
                }
            )
            
            # Update ad with payment info
            ad.payment_status = 'PROCESSING'
            ad.payment_id = response['data']['reference']
            ad.save()
            
            # Redirect to Paystack payment page
            return redirect(response['data']['authorization_url'])
            
        except Exception as e:
            messages.error(request, 'Error initializing payment. Please try again.')
            return redirect('core:ad_list')
    
    return render(request, 'core/ads/payment.html', {'ad': ad})

@login_required
def ad_payment_verify(request, pk):
    """View for verifying advertisement payment"""
    ad = get_object_or_404(Advertisement, pk=pk, advertiser=request.user)
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, 'No payment reference found.')
        return redirect('core:ad_list')
    
    try:
        paystack = utils.PaystackAPI()
        response = paystack.transaction.verify(reference)
        
        if response['data']['status'] == 'success':
            # Update ad status
            ad.payment_status = 'PAID'
            ad.status = 'PENDING'  # Pending admin approval
            ad.save()
            
            messages.success(request, 'Payment successful! Your ad will be reviewed shortly.')
        else:
            ad.payment_status = 'FAILED'
            ad.save()
            messages.error(request, 'Payment failed. Please try again.')
            
    except Exception as e:
        messages.error(request, 'Error verifying payment. Please contact support.')
    
    return redirect('core:ad_list')

@staff_member_required
def ad_review(request, pk):
    """View for staff to review advertisements"""
    ad = get_object_or_404(Advertisement, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            ad.status = 'ACTIVE'
            ad.is_active = True
            ad.admin_notes = notes
            messages.success(request, 'Advertisement approved successfully.')
        elif action == 'reject':
            ad.status = 'REJECTED'
            ad.is_active = False
            ad.rejection_reason = notes
            messages.success(request, 'Advertisement rejected.')
        
        ad.save()
        return redirect('core:ad_list')
    
    return render(request, 'core/ads/review.html', {'ad': ad})

def ad_click(request, pk):
    """View for handling advertisement clicks"""
    ad = get_object_or_404(Advertisement, pk=pk)
    
    if not ad.is_current():
        messages.error(request, 'This advertisement is no longer active.')
        return redirect('core:home')
    
    # Track the click
    ad.track_click(request.user if request.user.is_authenticated else None)
    
    # Redirect to the advertisement URL
    return redirect(ad.url)

@login_required
def test_notifications(request):
    """Test endpoint to trigger different types of notifications"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can access this endpoint")
        return redirect('core:home')
        
    # Create a test app
    app = AppListing.objects.first()
    if not app:
        messages.error(request, "No apps found to test with")
        return redirect('core:home')
    
    # Test submission notification
    NotificationService.notify_app_submission(app)
    messages.success(request, "Sent app submission notification to admins")
    
    # Test approval notification
    NotificationService.notify_app_approval(app)
    messages.success(request, "Sent app approval notification to developer and investors")
    
    # Test rejection notification
    NotificationService.notify_app_rejection(app, "Test rejection reason")
    messages.success(request, "Sent app rejection notification to developer")
    
    return redirect('core:home')

@receiver(post_save, sender=Investment)
def check_funding_completion(sender, instance, **kwargs):
    """Check if app has reached funding goal and process fees"""
    app = instance.app
    if app.is_fully_funded() and app.status != AppListing.Status.COMPLETED:
        try:
            PaymentService.handle_funding_completion(app)
        except Exception as e:
            logger.error(f"Error handling funding completion: {str(e)}") 

@staff_member_required
def test_fee_collection(request, app_id):
    """Test view for platform fee collection (staff only)"""
    app = get_object_or_404(AppListing, pk=app_id)
    
    if request.method == 'POST':
        try:
            # Check if developer has verified payment info
            try:
                payment_info = app.developer.payment_info
                if not payment_info or not payment_info.verified:
                    messages.error(request, 
                        "Developer must have verified payment information before collecting fees. "
                        "Please ask the developer to set up their payment information."
                    )
                    return redirect('core:app_detail', pk=app_id)
            except DeveloperPaymentInfo.DoesNotExist:
                messages.error(request, 
                    "Developer must set up payment information before collecting fees. "
                    "Please ask the developer to set up their payment information."
                )
                return redirect('core:app_detail', pk=app_id)
            
            # Check if platform fee transaction already exists
            existing_fee = PlatformFeeTransaction.objects.filter(
                app=app,
                status__in=['PENDING', 'COMPLETED']
            ).first()
            
            if existing_fee:
                messages.error(request, "Platform fee transaction already exists for this app.")
                return redirect('core:app_detail', pk=app_id)
            
            # Create test investment to reach funding goal
            test_amount = app.funding_goal
            platform_fee = app.calculate_platform_fee()
            developer_amount = test_amount - platform_fee
            
            # Create test investor if needed
            investor, created = User.objects.get_or_create(
                email='test_investor@example.com',
                defaults={
                    'username': 'test_investor',
                    'role': User.Role.INVESTOR
                }
            )
            
            # Create investment
            investment = Investment.objects.create(
                investor=investor,
                app=app,
                amount_paid=test_amount,
                transaction_id=f'TEST-{timezone.now().strftime("%Y%m%d%H%M%S")}'
            )
            
            # Update app status
            app.status = AppListing.Status.FUNDED
            app.save()
            
            # Process fee collection
            PaymentService.handle_funding_completion(app)
            
            messages.success(request, 
                f"Successfully tested fee collection!\n"
                f"Platform Fee (5%): ₦{platform_fee:,.2f}\n"
                f"Developer Amount: ₦{developer_amount:,.2f}"
            )
            
            # Create notification for developer
            Notification.objects.create(
                user=app.developer,
                type=Notification.Type.FUNDING_COMPLETE,
                title=f"Funding Complete - {app.name}",
                message=(
                    f"Your app has reached its funding goal!\n"
                    f"Total Raised: ₦{test_amount:,.2f}\n"
                    f"Platform Fee (5%): ₦{platform_fee:,.2f}\n"
                    f"Net Amount: ₦{developer_amount:,.2f}"
                )
            )
            
        except Exception as e:
            logger.error(f"Error testing fee collection: {str(e)}")
            messages.error(request, f"Error testing fee collection: {str(e)}")
        
        return redirect('core:app_detail', pk=app_id)
    
    return render(request, 'core/apps/test_fee.html', {
        'app': app,
        'developer_amount': app.funding_goal - app.calculate_platform_fee()
    })

@csrf_exempt
def get_available_percentage(request, app_id):
    """Public API endpoint to get current available percentage for an app."""
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
        
    try:
        app = get_object_or_404(AppListing, id=app_id)
        app.sync_remaining_percentage()  # Ensure we have the latest value
        
        return JsonResponse({
            'success': True,
            'available_percentage': str(app.remaining_percentage)
        })
    except AppListing.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'App not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting available percentage: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def app_shareholders(request, pk):
    """View for displaying all shareholders of an app"""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Only allow developer and admin access
    if not (request.user == app.developer or request.user.is_staff):
        raise PermissionDenied
    
    # Get all shareholders with their investments
    shareholders = []
    share_ownerships = ShareOwnership.objects.filter(app=app).select_related('user')
    
    for ownership in share_ownerships:
        # Get the corresponding investment
        investment = Investment.objects.filter(
            app=app,
            investor=ownership.user
        ).first()
        
        if investment:
            ownership.amount_paid = investment.amount_paid
            ownership.investment_date = investment.created_at
            # Consider investment active if it has a valid certificate or was created in the last 180 days
            ownership.is_active = investment.created_at >= timezone.now() - timezone.timedelta(days=180)
        else:
            ownership.amount_paid = 0
            ownership.investment_date = None
            ownership.is_active = False
            
        shareholders.append(ownership)
    
    # Sort by percentage owned
    shareholders.sort(key=lambda x: x.percentage_owned, reverse=True)
    
    # Calculate total shares distributed
    total_shares_distributed = sum(
        shareholder.percentage_owned for shareholder in shareholders
    )
    
    return render(request, 'core/apps/shareholders.html', {
        'app': app,
        'shareholders': shareholders,
        'total_shares_distributed': total_shares_distributed
    })

@login_required
def export_shareholders(request, pk):
    """Export shareholders data to CSV"""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Only allow developer and admin access
    if not (request.user == app.developer or request.user.is_staff):
        raise PermissionDenied
    
    # Get all shareholders with their investments
    shareholders = []
    share_ownerships = ShareOwnership.objects.filter(app=app).select_related('user')
    
    for ownership in share_ownerships:
        # Get the corresponding investment
        investment = Investment.objects.filter(
            app=app,
            investor=ownership.user
        ).first()
        
        if investment:
            ownership.amount_paid = investment.amount_paid
            ownership.investment_date = investment.created_at
            # Consider investment active if it has a valid certificate or was created in the last 180 days
            ownership.is_active = investment.created_at >= timezone.now() - timezone.timedelta(days=180)
        else:
            ownership.amount_paid = 0
            ownership.investment_date = None
            ownership.is_active = False
            
        shareholders.append(ownership)
    
    # Sort by percentage owned
    shareholders.sort(key=lambda x: x.percentage_owned, reverse=True)
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{app.name}_shareholders_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name',
        'Email',
        'Shares Owned (%)',
        'Investment Amount (₦)',
        'Current Value (₦)',
        'Investment Date',
        'Status'
    ])
    
    for shareholder in shareholders:
        writer.writerow([
            shareholder.user.get_full_name() or shareholder.user.username,
            shareholder.user.email,
            f"{shareholder.percentage_owned:.2f}%",
            f"{shareholder.amount_paid:.2f}",
            f"{shareholder.current_value:.2f}",
            shareholder.investment_date.strftime('%Y-%m-%d') if shareholder.investment_date else "N/A",
            'Active' if shareholder.is_active else 'Inactive'
        ])
    
    return response 

@require_POST
def hire_us(request):
    """Handle hire us form submission"""
    try:
        # Get form data
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        project_type = request.POST.get('project_type')
        message = request.POST.get('message')
        
        # Send email notification to admin
        subject = f'New Project Request from {name}'
        email_body = f"""
        New project request details:
        
        Name: {name}
        Email: {email}
        Phone: {phone}
        Project Type: {project_type}
        
        Message:
        {message}
        """
        
        send_mail(
            subject,
            email_body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        # Send confirmation email to user
        user_subject = 'Thank you for your project request'
        user_message = f"""
        Dear {name},
        
        Thank you for reaching out to us. We have received your project request and our team will review it shortly.
        We aim to respond to all requests within 24-48 hours.
        
        Your project details:
        - Project Type: {project_type}
        - Message: {message}
        
        Best regards,
        The Team
        """
        
        send_mail(
            user_subject,
            user_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        messages.success(request, 'Your request has been submitted successfully! We will contact you shortly.')
        
    except Exception as e:
        logger.error(f"Error processing hire us form: {str(e)}")
        messages.error(request, 'There was an error processing your request. Please try again later.')
    
    return redirect('core:home')

class AppTeamMemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = AppTeamMember
    form_class = AppTeamMemberForm
    template_name = 'core/apps/team_member_form.html'
    
    def test_func(self):
        app = get_object_or_404(AppListing, pk=self.kwargs['pk'])
        return self.request.user == app.developer
    
    def form_valid(self, form):
        app = get_object_or_404(AppListing, pk=self.kwargs['pk'])
        form.instance.app = app
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('core:app_detail', kwargs={'pk': self.kwargs['pk']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = get_object_or_404(AppListing, pk=self.kwargs['pk'])
        context['app'] = app
        context['is_edit'] = False
        return context

class AppTeamMemberUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AppTeamMember
    form_class = AppTeamMemberForm
    template_name = 'core/apps/team_member_form.html'
    pk_url_kwarg = 'member_pk'
    
    def test_func(self):
        team_member = self.get_object()
        return self.request.user == team_member.app.developer
    
    def get_success_url(self):
        return reverse('core:app_detail', kwargs={'pk': self.kwargs['pk']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = get_object_or_404(AppListing, pk=self.kwargs['pk'])
        context['app'] = app
        context['is_edit'] = True
        return context

class AppTeamMemberDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = AppTeamMember
    template_name = 'core/apps/team_member_confirm_delete.html'
    pk_url_kwarg = 'member_pk'
    
    def test_func(self):
        team_member = self.get_object()
        return self.request.user == team_member.app.developer
    
    def get_success_url(self):
        return reverse('core:app_detail', kwargs={'pk': self.kwargs['pk']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = get_object_or_404(AppListing, pk=self.kwargs['pk'])
        context['app'] = app
        return context

@login_required
def pitch_deck_template(request, pk):
    """Display the pitch deck template with examples."""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Only allow the app developer to access the template
    if app.developer != request.user:
        messages.error(request, 'You do not have permission to access this template.')
        return redirect('core:app_detail', pk=pk)
    
    return render(request, 'core/apps/pitch_deck_template.html', {
        'app': app
    })

def apps_for_sale(request):
    """List all apps that are for sale."""
    apps = AppListing.objects.filter(
        status=AppListing.Status.ACTIVE,
        listing_type=AppListing.ListingType.FOR_SALE
    ).order_by('-created_at')
    
    # Format amounts in Naira
    for app in apps:
        app.formatted_sale_price = format_naira(app.sale_price)
        app.formatted_monthly_revenue = format_naira(app.monthly_revenue)
    
    return render(request, 'core/apps/for_sale_list.html', {
        'apps': apps,
    })

@login_required
def app_for_sale_create(request):
    """Create a new app for sale listing."""
    # Allow both developers and admins to create apps for sale
    if not (request.user.is_developer() or request.user.is_staff):
        messages.error(request, 'Only developers and administrators can create app listings.')
        return redirect('core:home')
    
    if request.method == 'POST':
        form = AppForSaleForm(request.POST)
        
        if form.is_valid():
            try:
                app = form.save(commit=False)
                app.developer = request.user
                app.status = AppListing.Status.PENDING
                app.listing_type = AppListing.ListingType.FOR_SALE
                app.exchange_rate = app.get_current_exchange_rate()
                
                app.save()
                
                # Send notification to admins about new app submission
                NotificationService.notify_app_submission(app)
                
                messages.success(
                    request, 
                    'App for sale listing created successfully! It will be reviewed shortly.'
                )
                return redirect('core:app_detail', pk=app.pk)
            except Exception as e:
                messages.error(request, f'Error creating app listing: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AppForSaleForm()
    
    return render(request, 'core/apps/for_sale_create.html', {'form': form})

@login_required
@require_POST
def contact_seller(request, pk):
    """Handle contact seller form submission."""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Ensure the app is for sale
    if app.listing_type != AppListing.ListingType.FOR_SALE:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'This app is not for sale.'})
        messages.error(request, 'This app is not for sale.')
        return redirect('core:app_detail', pk=pk)
    
    # Get the message from the form
    message = request.POST.get('message', '').strip()
    if not message:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Please provide a message for the seller.'})
        messages.error(request, 'Please provide a message for the seller.')
        return redirect('core:app_detail', pk=pk)
    
    try:
        # Create message in database
        AppMessage.objects.create(
            app=app,
            sender=request.user,
            recipient=app.developer,
            message=message
        )
        
        # Send email to the seller
        subject = f'Interest in {app.name} - New Message from {request.user.username}'
        email_body = f"""
Hello {app.developer.username},

You have received a new message regarding your app "{app.name}" that is listed for sale.

From: {request.user.username} ({request.user.email})
Message:
{message}

You can reply directly to this email to contact the potential buyer.

Best regards,
The FundAfrica Team
        """
        
        # Use EmailMessage for more control over headers
        email = EmailMessage(
            subject=subject,
            body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[app.developer.email],
            headers={'Reply-To': request.user.email}
        )
        email.send(fail_silently=False)
        
        # Create a notification for the seller
        NotificationService.notify_seller_contact(
            app=app,
            sender=request.user,
            message=message
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Your message has been sent to the seller. They will contact you soon.'})
        messages.success(request, 'Your message has been sent to the seller. They will contact you soon.')
    except Exception as e:
        logger.error(f'Error sending contact seller email: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'There was an error sending your message. Please try again later.'})
        messages.error(request, 'There was an error sending your message. Please try again later.')
    
    return redirect('core:app_detail', pk=pk)

@login_required
def app_messages(request, pk):
    """View messages for an app."""
    app = get_object_or_404(AppListing, pk=pk)
    
    # Only allow app developer and message senders/recipients to view messages
    if not (request.user == app.developer or 
            AppMessage.objects.filter(
                app=app,
                sender=request.user
            ).exists() or
            AppMessage.objects.filter(
                app=app,
                recipient=request.user
            ).exists()):
        messages.error(request, 'You do not have permission to view these messages.')
        return redirect('core:app_detail', pk=pk)
    
    messages_list = AppMessage.objects.filter(
        app=app
    ).filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')
    
    paginator = Paginator(messages_list, 20)  # Show 20 messages per page
    page = request.GET.get('page')
    messages_list = paginator.get_page(page)
    
    return render(request, 'core/apps/messages.html', {
        'app': app,
        'messages_list': messages_list,
        'is_paginated': messages_list.has_other_pages()
    })

@login_required
@require_POST
def mark_message_read(request, message_id):
    """Mark a message as read."""
    message = get_object_or_404(AppMessage, pk=message_id)
    
    # Only recipient can mark message as read
    if request.user != message.recipient:
        messages.error(request, 'You do not have permission to mark this message as read.')
        return redirect('core:app_detail', pk=message.app.pk)
    
    message.is_read = True
    message.save()
    
    return redirect('core:app_messages', pk=message.app.pk)

@login_required
@require_POST
def reply_message(request, message_id):
    """Reply to a message."""
    original_message = get_object_or_404(AppMessage, pk=message_id)
    app = original_message.app
    
    # Determine the recipient (if you're replying to a message you sent, reply goes to recipient, otherwise to sender)
    recipient = original_message.sender if original_message.recipient == request.user else original_message.recipient
    
    message = request.POST.get('message', '').strip()
    if not message:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Message cannot be empty.'})
        messages.error(request, 'Message cannot be empty.')
        return redirect('core:app_messages', pk=app.pk)
    
    try:
        # Create the reply message
        AppMessage.objects.create(
            app=app,
            sender=request.user,
            recipient=recipient,
            message=message
        )
        
        # Send email notification
        subject = f'New Reply - {app.name}'
        email_body = f"""
Hello {recipient.username},

You have received a new reply to your message regarding the app "{app.name}".

From: {request.user.username}
Message:
{message}

You can reply directly to this email to continue the conversation.

Best regards,
The FundAfrica Team
        """
        
        email = EmailMessage(
            subject=subject,
            body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
            headers={'Reply-To': request.user.email}
        )
        email.send(fail_silently=False)
        
        # Create a notification
        NotificationService.notify_message_reply(
            app=app,
            sender=request.user,
            recipient=recipient,
            message=message
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Reply sent successfully.'})
        messages.success(request, 'Reply sent successfully.')
        
    except Exception as e:
        logger.error(f'Error sending reply message: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'There was an error sending your reply. Please try again later.'})
        messages.error(request, 'There was an error sending your reply. Please try again later.')
    
    return redirect('core:app_messages', pk=app.pk)

@login_required
@require_POST
def archive_message(request, message_id):
    """Archive or unarchive a message."""
    message = get_object_or_404(AppMessage, pk=message_id)
    
    # Only sender or recipient can archive/unarchive
    if request.user not in [message.sender, message.recipient]:
        messages.error(request, 'You do not have permission to archive this message.')
        return redirect('core:app_messages', pk=message.app.pk)
    
    message.is_archived = not message.is_archived
    message.save()
    
    action = 'unarchived' if not message.is_archived else 'archived'
    messages.success(request, f'Message {action} successfully.')
    return redirect('core:app_messages', pk=message.app.pk)

@login_required
@require_POST
def delete_message(request, message_id):
    """Delete a message."""
    message = get_object_or_404(AppMessage, pk=message_id)
    
    # Only sender or recipient can delete
    if request.user not in [message.sender, message.recipient]:
        messages.error(request, 'You do not have permission to delete this message.')
        return redirect('core:app_messages', pk=message.app.pk)
    
    app_pk = message.app.pk
    message.delete()
    
    messages.success(request, 'Message deleted successfully.')
    return redirect('core:app_messages', pk=app_pk)

@login_required
def report_comment(request, app_id, comment_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    try:
        app = get_object_or_404(AppListing, id=app_id)
        comment = get_object_or_404(AppComment, id=comment_id, app=app)
        
        # Check if report already exists
        existing_report = Report.objects.filter(
            content_type=ContentType.objects.get_for_model(AppComment),
            object_id=comment.id,
            reporter=request.user
        ).exists()
        
        if existing_report:
            return JsonResponse({
                'success': False, 
                'message': 'You have already reported this comment'
            }, status=400)
        
        # Get reason from request
        data = json.loads(request.body)
        reason = data.get('reason', 'inappropriate content')
        
        # Create new report
        Report.objects.create(
            content_type=ContentType.objects.get_for_model(AppComment),
            object_id=comment.id,
            reporter=request.user,
            reason=reason,
            status='PENDING'
        )
        
        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid request data'}, status=400)
    except Exception as e:
        logger.error(f"Error reporting comment: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'message': 'An error occurred while reporting the comment'
        }, status=500)

@login_required
def get_comments(request, app_id):
    try:
        app = get_object_or_404(AppListing, id=app_id)
        comments = AppComment.objects.filter(app=app, parent=None)
        
        comments_data = [{
            'id': comment.id,
            'content': comment.content,
            'author_name': comment.user.username,
            'author_avatar': comment.user.profile_picture.url if comment.user.profile_picture else None,
            'created_at': comment.created_at.isoformat(),
            'can_delete': comment.user == request.user or request.user.is_staff,
            'app_id': app_id,
            'is_author': comment.user == request.user,
            'replies': [{
                'id': reply.id,
                'content': reply.content,
                'author_name': reply.user.username,
                'author_avatar': reply.user.profile_picture.url if reply.user.profile_picture else None,
                'created_at': reply.created_at.isoformat(),
                'can_delete': reply.user == request.user or request.user.is_staff,
                'app_id': app_id,
                'is_author': reply.user == request.user
            } for reply in comment.replies.all()]
        } for comment in comments]
        
        return JsonResponse({
            'success': True,
            'comments': comments_data
        })
    except Exception as e:
        logger.error(f"Error in get_comments: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def add_comment(request, app_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        content = data.get('content')
        parent_id = data.get('parent_id')
        
        if not content:
            return JsonResponse({'success': False, 'message': 'Content is required'}, status=400)
        
        app = get_object_or_404(AppListing, id=app_id)
        comment = AppComment.objects.create(
            app=app,
            user=request.user,
            content=content,
            parent_id=parent_id
        )
        
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'author_name': comment.user.username,
                'author_avatar': comment.user.profile_picture.url if comment.user.profile_picture else None,
                'created_at': comment.created_at.isoformat(),
                'can_delete': True,
                'app_id': app_id,
                'is_author': True
            }
        })
    except Exception as e:
        logger.error(f"Error in add_comment: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
def delete_comment(request, app_id, comment_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    try:
        app = get_object_or_404(AppListing, id=app_id)
        comment = get_object_or_404(AppComment, id=comment_id, app=app)
        
        # Check if user can delete
        if not (comment.user == request.user or request.user.is_staff):
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to delete this comment'
            }, status=403)
        
        comment.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error deleting comment: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while deleting the comment'
        }, status=500)
