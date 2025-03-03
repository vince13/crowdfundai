from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.forms import PitchDeckForm
from core.models import AppListing, PitchDeck, Subscription
import logging

logger = logging.getLogger(__name__)

def check_developer_subscription(user):
    """Check if the developer has an active paid subscription."""
    try:
        subscription = Subscription.objects.get(user=user, is_active=True)
        return subscription.tier in ['PRO', 'ENTERPRISE']  # Adjust tiers as needed
    except Subscription.DoesNotExist:
        return False

@login_required
def pitch_deck_create(request, app_id):
    app = get_object_or_404(AppListing, id=app_id, developer=request.user)
    pitch_deck = PitchDeck.objects.filter(app=app).first()
    
    if request.method == 'POST':
        form = PitchDeckForm(request.POST, request.FILES, instance=pitch_deck)
        if form.is_valid():
            try:
                pitch_deck = form.save(commit=False)
                pitch_deck.app = app
                pitch_deck.save()
                
                messages.success(request, 'Pitch deck uploaded successfully!')
                
                # Check if user has paid subscription for AI analysis
                if check_developer_subscription(request.user):
                    messages.info(request, 'You can now trigger AI analysis from the pitch deck view page.')
                else:
                    messages.info(request, 'Upgrade to a paid plan to access AI analysis features.')
                
                return redirect('core:app_detail', pk=app_id)
            except Exception as e:
                logger.error(f"Error saving pitch deck: {str(e)}")
                messages.error(request, 'An error occurred while saving your pitch deck. Please try again.')
    else:
        form = PitchDeckForm(instance=pitch_deck)
    
    return render(request, 'core/pitch_deck/create.html', {
        'form': form,
        'app': app,
        'is_update': pitch_deck is not None
    })

@login_required
def pitch_deck_view(request, app_id):
    app = get_object_or_404(AppListing, id=app_id)
    pitch_deck = get_object_or_404(PitchDeck, app=app)
    has_paid_subscription = check_developer_subscription(app.developer)
    
    return render(request, 'core/pitch_deck/view.html', {
        'app': app,
        'pitch_deck': pitch_deck,
        'has_paid_subscription': has_paid_subscription,
        'can_trigger_analysis': has_paid_subscription and pitch_deck.ai_analysis_status not in ['IN_PROGRESS', 'PENDING']
    })

@login_required
def pitch_deck_edit(request, app_id):
    app = get_object_or_404(AppListing, id=app_id, developer=request.user)
    pitch_deck = get_object_or_404(PitchDeck, app=app)
    
    if request.method == 'POST':
        form = PitchDeckForm(request.POST, request.FILES, instance=pitch_deck)
        if form.is_valid():
            pitch_deck = form.save()
            messages.success(request, 'Pitch deck updated successfully!')
            return redirect('core:app_detail', pk=app_id)
    else:
        form = PitchDeckForm(instance=pitch_deck)
    
    return render(request, 'core/pitch_deck/create.html', {
        'form': form,
        'app': app,
        'is_update': True
    }) 

@login_required
@require_POST
def trigger_ai_analysis(request, app_id):
    """Manually trigger AI analysis for a pitch deck."""
    app = get_object_or_404(AppListing, id=app_id, developer=request.user)
    pitch_deck = get_object_or_404(PitchDeck, app=app)
    
    if not check_developer_subscription(request.user):
        return JsonResponse({
            'status': 'error',
            'message': 'AI analysis requires a paid subscription. Please upgrade your plan.'
        }, status=403)
    
    if pitch_deck.ai_analysis_status in ['IN_PROGRESS', 'PENDING']:
        return JsonResponse({
            'status': 'error',
            'message': 'Analysis is already in progress.'
        }, status=400)
    
    try:
        pitch_deck.generate_ai_assessment()
        return JsonResponse({
            'status': 'success',
            'message': 'AI analysis completed successfully.'
        })
    except Exception as e:
        logger.error(f"Error in AI analysis: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500) 