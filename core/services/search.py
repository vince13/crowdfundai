from django.db.models import Q, Count, Value, F
from django.db.models.functions import Lower
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.conf import settings
from ..models import AppListing, User

class SearchService:
    @staticmethod
    def search_apps(query=None, filters=None, sort_by=None, page=1, per_page=10):
        """
        Advanced search with filters and ranking
        
        Parameters:
        - query: Search text
        - filters: Dict of filters (category, price_range, status, etc.)
        - sort_by: Sorting criteria
        - page: Page number
        - per_page: Items per page
        """
        # Start with approved and active apps
        queryset = AppListing.objects.filter(Q(status='APPROVED') | Q(status='ACTIVE'))
        
        if query:
            # Check if using PostgreSQL
            if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
                # PostgreSQL full-text search
                search_vector = SearchVector('name', weight='A') + \
                              SearchVector('description', weight='B') + \
                              SearchVector('ai_features', weight='B') + \
                              SearchVector('category', weight='C')
                
                search_query = SearchQuery(query)
                
                # Apply full-text search with ranking
                queryset = queryset.annotate(
                    rank=SearchRank(search_vector, search_query)
                ).filter(rank__gt=0.1)
            else:
                # SQLite fallback using basic text search
                q_objects = Q()
                search_fields = ['name', 'description', 'ai_features', 'category']
                
                for term in query.split():
                    for field in search_fields:
                        q_objects |= Q(**{f"{field}__icontains": term})
                
                queryset = queryset.filter(q_objects).annotate(
                    # Simple relevance score based on exact matches
                    rank=Count('id')
                )
        
        # Apply filters
        if filters:
            if 'category' in filters:
                queryset = queryset.filter(category=filters['category'])
            
            if 'price_range' in filters:
                min_price, max_price = filters['price_range']
                queryset = queryset.filter(price_per_percentage__range=(min_price, max_price))
            
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'min_funding' in filters:
                queryset = queryset.annotate(
                    total_investment=Count('investment')
                ).filter(total_investment__gte=filters['min_funding'])
        
        # Apply sorting
        if sort_by:
            if sort_by == 'newest':
                queryset = queryset.order_by('-created_at')
            elif sort_by == 'popular':
                queryset = queryset.annotate(
                    investor_count=Count('investment__investor', distinct=True)
                ).order_by('-investor_count')
            elif sort_by == 'funding':
                queryset = queryset.annotate(
                    total_investment=Count('investment')
                ).order_by('-total_investment')
            elif sort_by == 'relevance' and query:
                if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
                    queryset = queryset.order_by('-rank')
                else:
                    # For SQLite, order by multiple fields for better relevance
                    queryset = queryset.order_by('-rank', '-created_at')
        else:
            # Default sorting
            queryset = queryset.order_by('-created_at')
        
        # Calculate total results and pages
        total_results = queryset.count()
        total_pages = (total_results + per_page - 1) // per_page
        
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        results = queryset[start:end]
        
        return {
            'results': results,
            'total_results': total_results,
            'total_pages': total_pages,
            'current_page': page,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }
    
    @staticmethod
    def get_search_suggestions(partial_query, limit=5):
        """
        Get autocomplete suggestions based on partial query
        
        Parameters:
        - partial_query: Partial search text
        - limit: Maximum number of suggestions
        """
        if not partial_query or len(partial_query) < 2:
            return []
        
        # Search in app names
        app_suggestions = AppListing.objects.filter(
            name__icontains=partial_query
        ).values_list('name', flat=True)[:limit]
        
        # Search in categories
        category_suggestions = AppListing.objects.filter(
            category__icontains=partial_query
        ).values_list('category', flat=True).distinct()[:limit]
        
        # Combine and deduplicate suggestions
        suggestions = list(set(list(app_suggestions) + list(category_suggestions)))[:limit]
        
        return [{'text': s, 'type': 'suggestion'} for s in suggestions]
    
    @staticmethod
    def get_trending_searches(limit=5):
        """Get trending search terms"""
        # This would typically use a cache or database of recent searches
        # For now, return popular categories
        return AppListing.objects.values('category').annotate(
            count=Count('id')
        ).order_by('-count')[:limit] 