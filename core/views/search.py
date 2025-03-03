from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..services.search import SearchService
from ..models import AppListing

def search_apps(request):
    """Main search view"""
    query = request.GET.get('q', '')
    category = request.GET.get('category')
    sort_by = request.GET.get('sort')
    page = int(request.GET.get('page', 1))
    
    filters = {}
    if category:
        filters['category'] = category
    
    # Get price range filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price and max_price:
        filters['price_range'] = (float(min_price), float(max_price))
    
    # Get status filter
    status = request.GET.get('status')
    if status:
        filters['status'] = status
    
    search_results = SearchService.search_apps(
        query=query,
        filters=filters,
        sort_by=sort_by,
        page=page
    )
    
    context = {
        'query': query,
        'results': search_results['results'],
        'total_results': search_results['total_results'],
        'total_pages': search_results['total_pages'],
        'current_page': search_results['current_page'],
        'has_next': search_results['has_next'],
        'has_previous': search_results['has_previous'],
        'filters': filters,
        'sort_by': sort_by,
        'categories': AppListing.Category.choices,
        'app_statuses': AppListing.Status.choices
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'core/search/results_partial.html', context)
    return render(request, 'core/search/results.html', context)

def search_suggestions(request):
    """AJAX endpoint for search suggestions"""
    query = request.GET.get('q', '')
    suggestions = SearchService.get_search_suggestions(query)
    trending = SearchService.get_trending_searches()
    
    return JsonResponse({
        'suggestions': suggestions,
        'trending': trending
    }) 