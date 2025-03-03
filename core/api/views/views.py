from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from core.models.base import AppListing, CommunityVote

@login_required
@require_POST
def app_like_api(request, pk):
    app = get_object_or_404(AppListing, pk=pk)
    
    # Check if user already liked
    vote, created = CommunityVote.objects.get_or_create(
        user=request.user,
        app=app,
        vote_type='LIKE'
    )
    
    if not created:
        # User already liked, so unlike
        vote.delete()
        is_liked = False
    else:
        is_liked = True
    
    # Get updated counts
    likes_count = CommunityVote.objects.filter(
        app=app,
        vote_type='LIKE'
    ).count()
    
    return JsonResponse({
        'is_liked': is_liked,
        'likes_count': likes_count
    })

@login_required
@require_POST
def app_upvote_api(request, pk):
    app = get_object_or_404(AppListing, pk=pk)
    
    # Check if user already upvoted
    vote, created = CommunityVote.objects.get_or_create(
        user=request.user,
        app=app,
        vote_type='UPVOTE'
    )
    
    if not created:
        # User already upvoted, so remove upvote
        vote.delete()
        is_upvoted = False
    else:
        is_upvoted = True
    
    # Get updated counts
    upvotes_count = CommunityVote.objects.filter(
        app=app,
        vote_type='UPVOTE'
    ).count()
    
    return JsonResponse({
        'is_upvoted': is_upvoted,
        'upvotes_count': upvotes_count
    }) 