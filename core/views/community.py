from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from ..models import AppListing, CommunityVote, AppComment
from ..forms import AppListingForm
from ..services.notifications import NotificationService
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def suggest_app(request):
    """Handle community app suggestions."""
    if request.method == 'POST':
        # Create a mutable copy of POST data
        post_data = request.POST.copy()
        
        # Set default values for all required fields
        post_data['funding_goal'] = 1000  # Minimum valid funding goal
        post_data['equity_percentage'] = 1  # Minimum valid percentage
        post_data['available_percentage'] = 1  # Minimum valid percentage
        post_data['min_investment_percentage'] = 1  # Minimum valid percentage
        post_data['price_per_percentage'] = 0.01  # Minimum valid price
        post_data['listing_type'] = AppListing.ListingType.COMMUNITY
        post_data['currency'] = 'NGN'  # Default currency
        post_data['funding_round'] = 'PRESEED'  # Default funding round
        post_data['round_number'] = 1  # Default round number
        post_data['lock_in_period'] = 30  # Minimum lock-in period
        post_data['funding_end_date'] = (timezone.now() + timezone.timedelta(days=30)).strftime('%Y-%m-%d')  # 30 days from now
        post_data['use_of_funds'] = '{"development": 100}'  # Simple use of funds
        
        form = AppListingForm(post_data)
        if form.is_valid():
            app = form.save(commit=False)
            app.developer = request.user
            app.suggested_by = request.user
            app.listing_type = AppListing.ListingType.COMMUNITY
            app.status = AppListing.Status.PENDING
            app.exchange_rate = 1.0  # Set exchange rate to 1.0 since we're using only Naira
            app.remaining_percentage = app.available_percentage 
            app.save()
            
            # Notify admins about the new suggestion
            NotificationService.notify_community_suggestion(app)
            
            messages.success(request, 'Your app suggestion has been submitted successfully! It will be reviewed by our team.')
            return redirect('core:app_detail', pk=app.pk)
        else:
            print("Form Errors:", form.errors)  # Debug print
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AppListingForm()
        
        # Remove fields not relevant for community suggestions
        exclude_fields = ['funding_goal', 'equity_percentage', 'price_per_percentage', 
                         'min_investment_percentage', 'available_percentage', 'listing_type',
                         'currency', 'funding_round', 'round_number', 'lock_in_period',
                         'funding_end_date', 'use_of_funds']
        for field in exclude_fields:
            if field in form.fields:
                del form.fields[field]
    
    return render(request, 'core/apps/suggest.html', {'form': form})

@require_POST
@login_required
def vote_app(request, pk):
    """Handle voting for community-suggested apps."""
    app = get_object_or_404(AppListing, pk=pk)
    
    if app.listing_type != AppListing.ListingType.COMMUNITY:
        return JsonResponse({
            'success': False,
            'message': 'Voting is only allowed for community-suggested apps'
        }, status=400)
    
    try:
        data = json.loads(request.body)
        vote_type = data.get('vote_type')
    except json.JSONDecodeError:
        vote_type = request.POST.get('vote_type')
    
    if vote_type not in ['UPVOTE', 'LIKE']:
        return JsonResponse({
            'success': False,
            'message': 'Invalid vote type'
        }, status=400)
    
    # Check for existing vote of the same type
    existing_vote = CommunityVote.objects.filter(
        user=request.user,
        app=app,
        vote_type=vote_type
    ).first()
    
    if existing_vote:
        # Remove vote if it exists (toggle off)
        existing_vote.delete()
        action = 'removed'
        message = f'Your {vote_type.lower()} has been removed'
    else:
        # Add new vote (toggle on) using get_or_create to prevent duplicates
        CommunityVote.objects.get_or_create(
            user=request.user,
            app=app,
            vote_type=vote_type
        )
        action = 'added'
        message = f'Your {vote_type.lower()} has been added'
    
    # Get user's current votes
    user_votes = CommunityVote.objects.filter(
        user=request.user,
        app=app
    ).values_list('vote_type', flat=True)
    
    # Update vote counts
    upvote_count = CommunityVote.objects.filter(app=app, vote_type='UPVOTE').count()
    like_count = CommunityVote.objects.filter(app=app, vote_type='LIKE').count()
    
    # Check if app has become trending
    vote_threshold = getattr(settings, 'TRENDING_VOTE_THRESHOLD', 30)
    is_trending = upvote_count >= vote_threshold
    
    if is_trending and not app.is_trending:
        app.is_trending = True
        app.save()
        NotificationService.notify_suggestion_trending(app)
    elif not is_trending and app.is_trending:
        app.is_trending = False
        app.save()
    
    return JsonResponse({
        'success': True,
        'message': message,
        'action': action,
        'upvote_count': upvote_count,
        'like_count': like_count,
        'is_trending': is_trending,
        'user_votes': list(user_votes)
    })

def community_leaderboard(request):
    """Display trending and top-voted community apps."""
    vote_threshold = getattr(settings, 'TRENDING_VOTE_THRESHOLD', 30)
    week_ago = timezone.now() - timezone.timedelta(days=7)

    # Get trending apps (both manual and automatic)
    trending_apps = AppListing.objects.filter(
        # Only include community and nominated apps
        listing_type__in=[AppListing.ListingType.COMMUNITY, AppListing.ListingType.NOMINATED],
        status=AppListing.Status.ACTIVE
    ).filter(
        # Either manually trending OR has sufficient recent votes
        Q(manual_trending=True) |
        Q(
            community_votes__created_at__gte=week_ago,
            community_votes__vote_type__in=['LIKE', 'UPVOTE']
        )
    ).annotate(
        recent_votes=Count(
            'community_votes',
            filter=Q(
                community_votes__created_at__gte=week_ago,
                community_votes__vote_type__in=['LIKE', 'UPVOTE']
            )
        )
    ).filter(
        # Ensure either manual trending OR meets vote threshold
        Q(manual_trending=True) | Q(recent_votes__gte=vote_threshold)
    ).order_by('-manual_trending', '-recent_votes').distinct()[:6]
    
    # Get all-time most voted apps (only community and nominated)
    top_voted_apps = AppListing.objects.filter(
        listing_type__in=[AppListing.ListingType.COMMUNITY, AppListing.ListingType.NOMINATED],
        status=AppListing.Status.ACTIVE
    ).annotate(
        vote_count=Count('community_votes', filter=Q(community_votes__vote_type='UPVOTE'))
    ).order_by('-vote_count')[:9]
    
    return render(request, 'core/apps/leaderboard.html', {
        'trending_apps': trending_apps,
        'top_voted_apps': top_voted_apps
    })

@login_required
def add_comment(request, pk):
    """Add a comment to an app."""
    app = get_object_or_404(AppListing, pk=pk)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            content = data.get('content')
            parent_id = data.get('parent_id')
        except json.JSONDecodeError:
            content = request.POST.get('content')
            parent_id = request.POST.get('parent_id')
        
        if not content:
            return JsonResponse({
                'success': False,
                'message': 'Comment content is required'
            }, status=400)
        
        # Determine if comment should be private based on app type
        is_private = app.listing_type == AppListing.ListingType.LISTED
        
        comment = AppComment.objects.create(
            app=app,
            user=request.user,
            content=content,
            is_private=is_private,
            parent_id=parent_id if parent_id else None
        )
        
        # Notify relevant users about the new comment
        if is_private:
            NotificationService.notify_private_comment(app, comment)
        else:
            NotificationService.notify_community_comment(app, comment)
        
        default_avatar = '/static/core/images/default-avatar.png'
        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'author_name': comment.user.username,
                'author_avatar': comment.user.profile_picture.url if hasattr(comment.user, 'profile_picture') and comment.user.profile_picture else default_avatar,
                'created_at': comment.created_at.isoformat(),
                'is_private': comment.is_private,
                'is_author': True,  # User is always the author of their own comment
                'parent_id': comment.parent_id,
                'replies': []
            }
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def get_comments(request, pk):
    try:
        app = AppListing.objects.get(pk=pk)
        comments = AppComment.objects.filter(app=app, parent=None).order_by('-created_at')
        
        default_avatar = '/static/core/images/default-avatar.png'
        
        comments_data = []
        for comment in comments:
            # Skip invalid comments
            if not comment or not comment.content:
                continue
                
            # Check if user can see private comments
            if comment.is_private and not comment.is_visible_to(request.user):
                continue
                
            comment_data = {
                'id': comment.id,
                'content': comment.content.strip(),  # Ensure content is stripped of whitespace
                'author_name': comment.user.username if comment.user else 'Anonymous',
                'author_avatar': comment.user.profile_picture.url if hasattr(comment.user, 'profile_picture') and comment.user.profile_picture else default_avatar,
                'created_at': comment.created_at.isoformat(),
                'is_private': comment.is_private,
                'is_author': request.user.is_authenticated and (comment.user == request.user or request.user == app.developer),
                'replies': []
            }
            
            # Get replies
            replies = AppComment.objects.filter(parent=comment).order_by('created_at')
            for reply in replies:
                # Skip invalid replies
                if not reply or not reply.content:
                    continue
                    
                if reply.is_private and not reply.is_visible_to(request.user):
                    continue
                    
                reply_data = {
                    'id': reply.id,
                    'content': reply.content.strip(),  # Ensure content is stripped of whitespace
                    'author_name': reply.user.username if reply.user else 'Anonymous',
                    'author_avatar': reply.user.profile_picture.url if hasattr(reply.user, 'profile_picture') and reply.user.profile_picture else default_avatar,
                    'created_at': reply.created_at.isoformat(),
                    'is_private': reply.is_private,
                    'is_author': request.user.is_authenticated and (reply.user == request.user or request.user == app.developer),
                    'parent_id': comment.id
                }
                comment_data['replies'].append(reply_data)
            
            comments_data.append(comment_data)
        
        return JsonResponse({
            'success': True,
            'comments': comments_data
        })
        
    except AppListing.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'App not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_comments: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while loading comments'
        }, status=500)

@login_required
def delete_comment(request, pk, comment_id):
    """Delete a comment from an app."""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=405)
        
    app = get_object_or_404(AppListing, pk=pk)
    comment = get_object_or_404(AppComment, id=comment_id, app=app)
    
    # Check if user is authorized to delete the comment
    if comment.user != request.user and request.user != app.developer:
        return JsonResponse({
            'success': False,
            'message': 'You are not authorized to delete this comment'
        }, status=403)
    
    comment.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Comment deleted successfully'
    })

@require_GET
def get_comment_count(request, pk):
    """Get the total comment count for an app."""
    app = get_object_or_404(AppListing, pk=pk)
    count = app.get_total_comments()
    return JsonResponse({'count': count})