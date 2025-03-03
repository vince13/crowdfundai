from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_protect
import json
import logging
from core.services.blog_generator import BlogGenerator
from core.services.text_formatter import TextFormatter

logger = logging.getLogger(__name__)

def is_staff(user):
    return user.is_staff

@csrf_protect
@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def generate_blog_content(request):
    """API endpoint to generate blog content from a URL"""
    logger.info(f"Blog generation request from user: {request.user.username} (is_staff: {request.user.is_staff})")
    
    try:
        data = json.loads(request.body)
        source_url = data.get('source_url')
        word_count = int(data.get('word_count', 500))
        
        logger.debug(f"Request data - source_url: {source_url}, word_count: {word_count}")
        
        if not source_url:
            logger.warning("Missing source URL in request")
            return JsonResponse({
                'success': False,
                'error': 'Source URL is required'
            }, status=400)
            
        try:
            # Initialize blog generator
            generator = BlogGenerator()
            
            # Generate content
            logger.info(f"Generating content from URL: {source_url}")
            content = generator.generate_blog_post(source_url, word_count)
            
            # Format the content
            formatter = TextFormatter()
            formatted_content = {
                'content': formatter.format_blog_content(content.get('content', '')),
                'title': formatter.format_title(content.get('title', '')),
                'description': formatter.format_meta_description(content.get('description', '')),
                'keywords': formatter.format_keywords(content.get('keywords', ''))
            }
            
            logger.info("Content generated successfully")
            return JsonResponse({
                'success': True,
                'content': formatted_content['content'],
                'meta_title': formatted_content['title'],
                'meta_description': formatted_content['description'],
                'meta_keywords': formatted_content['keywords']
            })
            
        except ValueError as e:
            logger.error(f"API Configuration Error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'API Configuration Error: {str(e)}'
            }, status=503)  # Service Unavailable
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON data in request")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500) 