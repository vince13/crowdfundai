from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json

from core.models import Blog, BlogCategory, Advertisement
from core.forms import BlogForm, BlogCategoryForm
from core.services.blog_generator import BlogGenerator

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

class BlogListView(ListView):
    model = Blog
    template_name = 'core/blog/list.html'
    context_object_name = 'posts'
    paginate_by = 10

    def get_queryset(self):
        queryset = Blog.objects.filter(status='published')
        
        # Search functionality
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(content__icontains=q) |
                Q(meta_keywords__icontains=q)
            )
            
        # Category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = BlogCategory.objects.all()
        
        # Get active advertisements
        now = timezone.now()
        print(f"\nChecking ads at {now}")
        
        # Get all ads first
        all_ads = Advertisement.objects.all()
        print(f"Total ads in system: {all_ads.count()}")
        
        # Check each condition
        active_status = all_ads.filter(status='ACTIVE')
        print(f"Ads with ACTIVE status: {active_status.count()}")
        
        active_flag = active_status.filter(is_active=True)
        print(f"Active ads with is_active=True: {active_flag.count()}")
        
        paid = active_flag.filter(payment_status='PAID')
        print(f"Active and paid ads: {paid.count()}")
        
        current_date = paid.filter(start_date__lte=now, end_date__gte=now)
        print(f"Active, paid ads within date range: {current_date.count()}")
        
        # Final filtered ads
        active_ads = current_date
        
        # Get one main ad and one sidebar ad
        context['main_ad'] = active_ads.filter(position='main').first()
        context['sidebar_ad'] = active_ads.filter(position='sidebar').first()
        
        print("\nSelected ads:")
        if context['main_ad']:
            print(f"Main ad: {context['main_ad'].title} (ID: {context['main_ad'].id})")
        else:
            print("No main ad selected")
            
        if context['sidebar_ad']:
            print(f"Sidebar ad: {context['sidebar_ad'].title} (ID: {context['sidebar_ad'].id})")
        else:
            print("No sidebar ad selected")
        
        return context

class BlogDetailView(DetailView):
    model = Blog
    template_name = 'core/blog/detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        if self.request.user.is_staff:
            return Blog.objects.all()
        return Blog.objects.filter(status='published')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not self.request.session.get(f'blog_viewed_{obj.id}'):
            obj.increment_view_count()
            self.request.session[f'blog_viewed_{obj.id}'] = True
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_posts'] = Blog.objects.filter(
            category=self.object.category,
            status='published'
        ).exclude(id=self.object.id)[:3]
        context['categories'] = BlogCategory.objects.all()
        context['popular_posts'] = Blog.objects.filter(
            status='published'
        ).order_by('-view_count')[:5]
        return context

class BlogCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Blog
    form_class = BlogForm
    template_name = 'core/blog/form.html'
    success_url = reverse_lazy('core:blog_list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

class BlogUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Blog
    form_class = BlogForm
    template_name = 'core/blog/form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

class BlogDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Blog
    template_name = 'core/blog/confirm_delete.html'
    success_url = reverse_lazy('core:blog_list')

class BlogCategoryCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = BlogCategory
    form_class = BlogCategoryForm
    template_name = 'core/blog/category_form.html'
    success_url = reverse_lazy('core:blog_list')

class BlogCategoryUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = BlogCategory
    form_class = BlogCategoryForm
    template_name = 'core/blog/category_form.html'
    success_url = reverse_lazy('core:blog_list')

@method_decorator(csrf_exempt, name='dispatch')
class BlogGenerateView(CreateView):
    model = Blog
    form_class = BlogForm
    template_name = 'core/blog/generate.html'
    success_url = reverse_lazy('core:blog_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'authentication_required'
            }, status=401)
        if not request.user.is_staff:
            return JsonResponse({
                'error': 'Admin access required',
                'code': 'admin_required'
            }, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        try:
            # Initialize blog generator
            generator = BlogGenerator()
            
            # Get data from request - handle both JSON and form data
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse({
                        'error': 'Invalid JSON data',
                        'code': 'invalid_json'
                    }, status=400)
            else:
                data = request.POST
                
            # Validate required fields
            source_url = data.get('source_url')
            if not source_url:
                return JsonResponse({
                    'error': 'Source URL is required',
                    'code': 'missing_source_url'
                }, status=400)
                
            try:
                word_count = int(data.get('word_count', 500))
            except (TypeError, ValueError):
                return JsonResponse({
                    'error': 'Invalid word count',
                    'code': 'invalid_word_count'
                }, status=400)
            
            # Generate blog content
            generated_content = generator.generate_blog_post(source_url, word_count)
            
            return JsonResponse({
                'success': True,
                'content': generated_content['content'],
                'title': generated_content['title'],
                'description': generated_content['description'],
                'keywords': generated_content['keywords']
            })
                
        except ValueError as e:
            return JsonResponse({
                'error': str(e),
                'code': 'configuration_error'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'code': 'generation_error'
            }, status=500)

@login_required
@require_POST
def increment_blog_views(request, post_id):
    """Increment the view count for a blog post"""
    try:
        post = Blog.objects.get(id=post_id)
        
        # Check if this is a custom view count addition
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            views_to_add = int(data.get('views', 1))
            post.view_count += views_to_add
        else:
            # Default increment by 1
            post.view_count += 1
            
        post.save()
        
        return JsonResponse({
            'success': True,
            'view_count': post.view_count
        })
    except Blog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Blog post not found'
        }, status=404)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({
            'success': False,
            'error': 'Invalid view count'
        }, status=400) 