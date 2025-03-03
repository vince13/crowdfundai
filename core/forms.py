from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User, AppListing, Investment, AIAssessment, PitchDeck, Blog, BlogCategory, Report, ContentModeration, ProjectMilestone, Deliverable, ProjectUpdate, ProjectTag, AppTag, Advertisement, LegalAgreement, AppTeamMember
import json
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, date, time
from django.db import models

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=[
            (User.Role.DEVELOPER, 'Developer - I want to list AI apps'),
            (User.Role.INVESTOR, 'Investor - I want to invest in AI apps')
        ],
        widget=forms.RadioSelect,
        required=True
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user

class AppListingForm(forms.ModelForm):
    nomination_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Describe the app idea, its potential impact, and why it should be developed...'
        })
    )
    
    nomination_budget_breakdown = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': '{"development": 40, "infrastructure": 30, "marketing": 30}'
        })
    )
    
    nomination_timeline = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': '{"estimated_months": 6, "phases": ["Design", "Development", "Testing", "Launch"]}'
        })
    )

    tech_stack = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': '{"languages": ["Python", "JavaScript"], "frameworks": ["Django", "React"]}'
        })
    )

    def clean_funding_goal(self):
        funding_goal = self.cleaned_data.get('funding_goal')
        listing_type = self.cleaned_data.get('listing_type')
        
        # Skip validation for community suggestions
        if listing_type == AppListing.ListingType.COMMUNITY:
            return funding_goal
            
        if funding_goal < 1000:
            raise ValidationError('Funding goal must be at least ₦1,000')
        return funding_goal
    
    def clean_nomination_budget_breakdown(self):
        listing_type = self.cleaned_data.get('listing_type')
        budget_breakdown = self.cleaned_data.get('nomination_budget_breakdown')
        
        if listing_type == AppListing.ListingType.NOMINATED:
            # If no budget_breakdown, try to get from use_of_funds
            if not budget_breakdown:
                use_of_funds = self.cleaned_data.get('use_of_funds')
                if use_of_funds:
                    if isinstance(use_of_funds, str):
                        try:
                            budget_breakdown = json.loads(use_of_funds)
                        except json.JSONDecodeError:
                            pass
                    else:
                        budget_breakdown = use_of_funds
            
            if not budget_breakdown:
                raise ValidationError('Budget breakdown is required for nominated apps')
            
            # Validate the budget breakdown
            if isinstance(budget_breakdown, str):
                try:
                    budget_dict = json.loads(budget_breakdown)
                except json.JSONDecodeError:
                    raise ValidationError('Invalid JSON format for budget breakdown')
            else:
                budget_dict = budget_breakdown
                
            if not isinstance(budget_dict, dict):
                raise ValidationError('Budget breakdown must be a valid JSON object')
            total = sum(budget_dict.values())
            if total != 100:
                raise ValidationError('Budget percentages must total 100%')
            return budget_dict
        return budget_breakdown
    
    def clean_nomination_timeline(self):
        listing_type = self.cleaned_data.get('listing_type')
        timeline = self.cleaned_data.get('nomination_timeline')
        
        if listing_type == AppListing.ListingType.NOMINATED:
            # If no timeline, try to create from funding_end_date
            if not timeline:
                funding_end_date = self.cleaned_data.get('funding_end_date')
                if funding_end_date:
                    months = (funding_end_date - timezone.now()).days / 30
                    timeline = {
                        "estimated_months": round(months),
                        "phases": ["Planning", "Development", "Testing", "Launch"]
                    }
            
            if not timeline:
                raise ValidationError('Timeline is required for nominated apps')
            
            # Validate the timeline
            if isinstance(timeline, str):
                try:
                    timeline_dict = json.loads(timeline)
                except json.JSONDecodeError:
                    raise ValidationError('Invalid JSON format for timeline')
            else:
                timeline_dict = timeline
                
            if not isinstance(timeline_dict, dict):
                raise ValidationError('Timeline must be a valid JSON object')
            if 'estimated_months' not in timeline_dict:
                raise ValidationError('Timeline must include estimated_months')
            if not isinstance(timeline_dict['estimated_months'], (int, float)):
                raise ValidationError('estimated_months must be a number')
            return timeline_dict
        return timeline

    def clean_tech_stack(self):
        tech_stack = self.cleaned_data.get('tech_stack')
        listing_type = self.cleaned_data.get('listing_type')
        
        if listing_type == AppListing.ListingType.FOR_SALE:
            if not tech_stack:
                return {}
            
            if isinstance(tech_stack, str):
                try:
                    tech_dict = json.loads(tech_stack)
                except json.JSONDecodeError:
                    raise ValidationError('Invalid JSON format for tech stack')
                return tech_dict
            
        return tech_stack

    class Meta:
        model = AppListing
        fields = [
            'name', 'description', 'ai_features', 
            'category', 'demo_video',
            'funding_goal', 'currency', 'available_percentage',
            'min_investment_percentage', 'price_per_percentage',
            'equity_percentage', 'funding_round', 'round_number',
            'lock_in_period', 'funding_end_date',
            'use_of_funds', 'github_url', 'demo_url',
            'listing_type', 'nomination_details', 'nomination_budget_breakdown',
            'nomination_timeline', 'suggested_by', 'suggestion_date',
            'development_stage', 'project_status', 'progress', 'estimated_completion_date',
            # Sales-specific fields
            'sale_price', 'sale_includes_source_code', 'sale_includes_assets',
            'sale_includes_support', 'support_duration_months', 'monthly_revenue',
            'monthly_users', 'tech_stack', 'deployment_type'
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe your app, its market potential, and business model...'
            }),
            'ai_features': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'List the AI/ML features of your app and their technical details...'
            }),
            'demo_video': forms.URLInput(attrs={
                'placeholder': 'Link to your app demonstration video'
            }),
            'available_percentage': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '1',
                'max': '100',
                'placeholder': 'Enter percentage (1-100)'
            }),
            'min_investment_percentage': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '1',
                'placeholder': 'Minimum investment percentage (e.g., 1%)'
            }),
            'equity_percentage': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.01',
                'max': '100',
                'placeholder': 'Total company equity percentage'
            }),
            'github_url': forms.URLInput(attrs={
                'placeholder': 'https://github.com/username/repository'
            }),
            'demo_url': forms.URLInput(attrs={
                'placeholder': 'https://your-demo-site.com'
            }),
            'funding_end_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'
            }),
            'use_of_funds': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '{"development": 40, "marketing": 30, "operations": 30}'
            }),
            'lock_in_period': forms.NumberInput(attrs={
                'min': '30',
                'placeholder': 'Number of days investors must hold their investment'
            }),
            'funding_goal': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter funding goal (minimum ₦1,000)'
            }),
            'price_per_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Price per 1% equity in ₦'
            }),
            'listing_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'development_stage': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select development stage'
            }),
            'project_status': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select project status'
            }),
            'progress': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '1',
                'placeholder': 'Enter progress (0-100)'
            }),
            'estimated_completion_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Select estimated completion date'
            })
        }
        help_texts = {
            'name': 'The name of your AI application',
            'description': 'Provide a detailed description including market analysis and business model',
            'ai_features': 'Detail the AI/ML components, technologies used, and their benefits',
            'category': 'Select the primary category that best fits your app',
            'demo_video': 'Link to a video demonstrating your app\'s functionality',
            'funding_goal': 'Minimum ₦1,000',
            'currency': 'Select your preferred funding currency',
            'available_percentage': 'Total percentage of equity available for funding (1-100%)',
            'min_investment_percentage': 'Minimum percentage that can be purchased (e.g., 1%)',
            'price_per_percentage': 'Price for 1% equity',
            'equity_percentage': 'Total percentage of company equity',
            'funding_round': 'Current funding round stage',
            'round_number': 'Sequential number of this funding round',
            'lock_in_period': 'Number of days investors must hold their investment',
            'funding_end_date': 'Deadline for reaching the funding goal',
            'use_of_funds': 'JSON object showing how funds will be used (percentages must total 100)',
            'github_url': 'Link to your GitHub repository (optional)',
            'demo_url': 'Link to a live demo of your app (optional)',
            'listing_type': 'Choose whether this is a direct listing or nominated app',
            'nomination_details': 'For nominated apps: Detailed description of the app idea and its potential impact',
            'nomination_budget_breakdown': 'For nominated apps: JSON object showing development cost breakdown',
            'nomination_timeline': 'For nominated apps: JSON object with estimated timeline and development phases',
            'development_stage': 'Current stage of development (Concept, Prototype, MVP, etc.)',
            'project_status': 'Current status of the project',
            'progress': 'Overall project progress (0-100%)',
            'estimated_completion_date': 'Estimated date of project completion',
            'sale_price': 'Fixed price for outright purchase of the app',
            'sale_includes_source_code': 'Whether the sale includes full source code',
            'sale_includes_assets': 'Whether the sale includes all assets (images, designs, etc.)',
            'sale_includes_support': 'Whether post-sale technical support is included',
            'support_duration_months': 'Duration of included technical support in months',
            'monthly_revenue': 'Current monthly revenue of the app',
            'monthly_users': 'Current monthly active users',
            'tech_stack': 'JSON object listing technologies and frameworks used',
            'deployment_type': 'Type of app deployment'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make certain fields required only for listed apps
        listed_fields = [
            'available_percentage', 'min_investment_percentage',
            'price_per_percentage', 'equity_percentage',
            'funding_round', 'round_number', 'lock_in_period'
        ]
        
        # Make certain fields required only for nominated apps
        nominated_fields = [
            'nomination_details', 'nomination_budget_breakdown',
            'nomination_timeline'
        ]

        # Make certain fields required only for apps for sale
        sale_fields = [
            'sale_price', 'sale_includes_source_code', 'sale_includes_assets',
            'sale_includes_support', 'tech_stack', 'deployment_type'
        ]

        # Hide community fields for non-community suggestions
        community_fields = ['suggested_by', 'suggestion_date']
        
        if self.instance.pk:  # If editing existing instance
            if self.instance.listing_type == AppListing.ListingType.LISTED:
                for field in nominated_fields + community_fields + sale_fields:
                    self.fields[field].widget = forms.HiddenInput()
            elif self.instance.listing_type == AppListing.ListingType.NOMINATED:
                for field in listed_fields + community_fields + sale_fields:
                    self.fields[field].widget = forms.HiddenInput()
            elif self.instance.listing_type == AppListing.ListingType.COMMUNITY:
                for field in listed_fields + nominated_fields + sale_fields:
                    self.fields[field].widget = forms.HiddenInput()
            elif self.instance.listing_type == AppListing.ListingType.FOR_SALE:
                for field in listed_fields + nominated_fields + community_fields:
                    self.fields[field].widget = forms.HiddenInput()
                # Make sale price required for apps for sale
                self.fields['sale_price'].required = True
                # Make description and AI features required for community suggestions
                self.fields['description'].required = True
                self.fields['ai_features'].required = True

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        
        if listing_type == AppListing.ListingType.COMMUNITY:
            # Ensure description and AI features are provided for community suggestions
            if not cleaned_data.get('description'):
                self.add_error('description', 'Description is required for community suggestions')
            if not cleaned_data.get('ai_features'):
                self.add_error('ai_features', 'AI features description is required for community suggestions')
        elif listing_type == AppListing.ListingType.NOMINATED:
            # Map between regular fields and nomination fields
            use_of_funds = cleaned_data.get('use_of_funds')
            funding_end_date = cleaned_data.get('funding_end_date')
            
            # If use_of_funds is provided but nomination_budget_breakdown isn't, use it
            if use_of_funds and not cleaned_data.get('nomination_budget_breakdown'):
                if isinstance(use_of_funds, str):
                    try:
                        use_of_funds = json.loads(use_of_funds)
                    except json.JSONDecodeError:
                        pass
                if isinstance(use_of_funds, dict):
                    cleaned_data['nomination_budget_breakdown'] = use_of_funds
            
            # If funding_end_date is provided but nomination_timeline isn't, create timeline
            if funding_end_date and not cleaned_data.get('nomination_timeline'):
                # Calculate months from now to funding_end_date
                months = (funding_end_date - timezone.now()).days / 30
                timeline = {
                    "estimated_months": round(months),
                    "phases": ["Planning", "Development", "Testing", "Launch"]
                }
                cleaned_data['nomination_timeline'] = timeline
        
        if listing_type == AppListing.ListingType.FOR_SALE:
            sale_price = cleaned_data.get('sale_price')
            if not sale_price:
                self.add_error('sale_price', 'Sale price is required for apps for sale')
            elif sale_price <= 0:
                self.add_error('sale_price', 'Sale price must be greater than zero')

            if cleaned_data.get('sale_includes_support') and not cleaned_data.get('support_duration_months'):
                self.add_error('support_duration_months', 'Support duration is required when support is included')

        return cleaned_data

class InvestmentForm(forms.Form):
    shares = forms.IntegerField(min_value=1)

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'bio', 'profile_picture']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }

    def clean_profile_picture(self):
        image = self.cleaned_data.get('profile_picture')
        if image:
            # Check file size
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("Image file size must be under 5MB.")
            
            # Check if it's an image file
            try:
                from PIL import Image
                img = Image.open(image)
                img.verify()  # Verify it's actually an image
                
                # Reopen the image after verify (verify closes the file)
                image.seek(0)
                img = Image.open(image)
                
                # Check image format
                if img.format not in ['JPEG', 'PNG', 'GIF']:
                    raise forms.ValidationError("Only JPEG, PNG and GIF images are allowed.")
                
                # Reset file pointer
                image.seek(0)
            except Exception as e:
                raise forms.ValidationError("Invalid image file. Please upload a valid image.")
        return image

class AIAssessmentForm(forms.ModelForm):
    class Meta:
        model = AIAssessment
        fields = [
            'technical_analysis',
            'market_analysis',
            'team_analysis',
            'financial_analysis',
            'risk_analysis',
            'innovation_score',
            'market_potential_score',
            'execution_capability_score',
            'overall_score',
            'ai_insights'
        ]
        widgets = {
            'technical_analysis': forms.HiddenInput(),
            'market_analysis': forms.HiddenInput(),
            'team_analysis': forms.HiddenInput(),
            'financial_analysis': forms.HiddenInput(),
            'risk_analysis': forms.HiddenInput(),
            'innovation_score': forms.HiddenInput(),
            'market_potential_score': forms.HiddenInput(),
            'execution_capability_score': forms.HiddenInput(),
            'overall_score': forms.HiddenInput(),
            'ai_insights': forms.HiddenInput()
        }

class PitchDeckForm(forms.ModelForm):
    class Meta:
        model = PitchDeck
        fields = ['presentation_file']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['presentation_file'].widget = forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf'
        })
    
    def clean_presentation_file(self):
        file = self.cleaned_data.get('presentation_file')
        if file:
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                raise forms.ValidationError("File size must be under 10MB.")
        return file

class BlogForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = [
            'title', 'category', 'content', 'featured_image', 'status',
            'meta_title', 'meta_description', 'meta_keywords',
            'social_title', 'social_description', 'source_url', 'target_word_count'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'featured_image': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'meta_keywords': forms.TextInput(attrs={'class': 'form-control'}),
            'social_title': forms.TextInput(attrs={'class': 'form-control'}),
            'social_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'source_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter URL from Google News, TechCrunch, etc.'
            }),
            'target_word_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '100',
                'max': '2000',
                'step': '100'
            })
        }

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            return title

        # Generate the initial slug
        slug = slugify(title)
        
        # If this is an update, exclude the current instance
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            qs = Blog.objects.exclude(pk=instance.pk)
        else:
            qs = Blog.objects.all()

        # Check if slug exists and generate a unique one if needed
        original_slug = slug
        counter = 1
        while qs.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1

        # Store the generated slug to use it in the save method
        self.generated_slug = slug
        return title

    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(self, 'generated_slug'):
            instance.slug = self.generated_slug
        if commit:
            instance.save()
        return instance

    def clean_meta_title(self):
        meta_title = self.cleaned_data.get('meta_title')
        if len(meta_title) > 60:
            raise forms.ValidationError("Meta title must be 60 characters or less.")
        return meta_title

    def clean_meta_description(self):
        meta_description = self.cleaned_data.get('meta_description')
        if len(meta_description) > 160:
            raise forms.ValidationError("Meta description must be 160 characters or less.")
        return meta_description

class BlogCategoryForm(forms.ModelForm):
    class Meta:
        model = BlogCategory
        fields = ['name', 'description', 'meta_keywords']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if BlogCategory.objects.filter(slug=slugify(name)).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("A category with this name already exists.")
        return name

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'description']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Please provide details about your report...'
            })
        }

class ModerationForm(forms.ModelForm):
    class Meta:
        model = ContentModeration
        fields = ['status', 'moderation_notes']
        widgets = {
            'moderation_notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Add moderation notes...'
            })
        }

class ProjectMilestoneForm(forms.ModelForm):
    class Meta:
        model = ProjectMilestone
        fields = ['title', 'description', 'status', 'target_date', 'progress', 'release_percentage']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'target_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'progress': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100'
            }),
            'release_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01'
            })
        }
        
    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop('app', None)
        super().__init__(*args, **kwargs)
        
    def clean_release_percentage(self):
        release_percentage = self.cleaned_data.get('release_percentage')
        
        # If no release percentage is set, return 0
        if release_percentage is None:
            return Decimal('0')
            
        # If this is an update and the release percentage hasn't changed, return it
        if self.instance.pk and release_percentage == self.instance.release_percentage:
            return release_percentage
            
        # Calculate total release percentage of other milestones
        if self.app:
            existing_total = self.app.milestones.exclude(
                pk=self.instance.pk if self.instance.pk else None
            ).aggregate(
                total=models.Sum('release_percentage')
            )['total'] or Decimal('0')
            
            # Check if adding this percentage would exceed 100%
            total_percentage = existing_total + release_percentage
            if total_percentage > 100:
                remaining = 100 - existing_total
                raise forms.ValidationError(
                    f'Total release percentage cannot exceed 100%. '
                    f'Maximum allowed for this milestone is {remaining}%'
                )
                
        return release_percentage

class DeliverableForm(forms.ModelForm):
    class Meta:
        model = Deliverable
        fields = ['title', 'description', 'status', 'due_date', 'evidence_file', 'evidence_link']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'evidence_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Link to external evidence (e.g. GitHub repo, demo video)'
            }),
            'evidence_file': forms.FileInput(attrs={
                'class': 'form-control'
            })
        }

    def clean_evidence_file(self):
        file = self.cleaned_data.get('evidence_file')
        if file:
            if file.size > 50 * 1024 * 1024:  # 50MB limit
                raise forms.ValidationError("File size must be under 50MB.")
        return file

class ProjectUpdateForm(forms.ModelForm):
    class Meta:
        model = ProjectUpdate
        fields = ['title', 'content', 'update_type', 'milestone']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'update_type': forms.Select(attrs={'class': 'form-select'}),
            'milestone': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, app=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if app:
            self.fields['milestone'].queryset = ProjectMilestone.objects.filter(app=app)

class ProjectTagForm(forms.ModelForm):
    class Meta:
        model = ProjectTag
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
        }

class AppTagForm(forms.Form):
    tags = forms.ModelMultipleChoiceField(
        queryset=ProjectTag.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )

class AdvertisementForm(forms.ModelForm):
    class Meta:
        model = Advertisement
        fields = [
            'title', 'content', 'image', 'position', 'target_url', 'company_name', 
            'contact_email', 'start_date', 'end_date', 'app'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'app': forms.Select(attrs={'class': 'form-select'})
        }
        help_texts = {
            'image': 'Upload an image for your advertisement. Recommended size: 800x400px for main position, 400x400px for sidebar.'
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # Only show apps owned by the user
            self.fields['app'].queryset = AppListing.objects.filter(developer=user)
            self.fields['app'].required = False
            self.fields['app'].empty_label = "No app (general advertisement)"
            
            # Pre-fill company name and contact email if available
            if not self.instance.pk:  # Only for new ads
                if user.is_developer():
                    self.initial['company_name'] = user.get_full_name() or user.username
                self.initial['contact_email'] = user.email

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            # Ensure we're comparing datetime objects
            if isinstance(start_date, date):
                start_date = datetime.combine(start_date, time.min)
                start_date = timezone.make_aware(start_date)

            # Check if start date is not in the past
            if start_date < timezone.now():
                raise forms.ValidationError("Start date cannot be in the past.")

            # Ensure consistent datetime comparison for end_date too
            if isinstance(end_date, date):
                end_date = datetime.combine(end_date, time.min)
                end_date = timezone.make_aware(end_date)

            # Check if end date is after start date
            if end_date <= start_date:
                raise forms.ValidationError("End date must be after start date.")

        return cleaned_data

class LegalAgreementForm(forms.ModelForm):
    """Form for creating and updating legal agreements"""
    class Meta:
        model = LegalAgreement
        fields = ['agreement_type', 'version', 'content', 'effective_date']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 20}),
            'effective_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        agreement_type = cleaned_data.get('agreement_type')
        version = cleaned_data.get('version')
        
        # Check if version already exists for this agreement type
        if LegalAgreement.objects.filter(
            agreement_type=agreement_type,
            version=version
        ).exists():
            raise forms.ValidationError(
                f"Version {version} already exists for {agreement_type}"
            )
        
        return cleaned_data

class AppTeamMemberForm(forms.ModelForm):
    class Meta:
        model = AppTeamMember
        fields = ['name', 'role', 'custom_role', 'email', 'github_profile', 'linkedin_profile', 'bio', 'contribution_details']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control', 'onchange': 'toggleCustomRole(this.value)'}),
            'custom_role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter custom role'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'github_profile': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'GitHub profile URL'}),
            'linkedin_profile': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'LinkedIn profile URL'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief bio'}),
            'contribution_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe their contributions to the project'})
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        custom_role = cleaned_data.get('custom_role')
        
        if role == 'OTHER' and not custom_role:
            raise ValidationError({
                'custom_role': 'Please specify the custom role when selecting "Other"'
            })
        
        return cleaned_data

class AppEngagementForm(forms.Form):
    add_views = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of views to add"
    )
    
    add_likes = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of likes to add"
    )
    
    add_upvotes = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of upvotes to add"
    )
    
    add_comments = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of comments to add"
    )
    
    engagement_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional: Add a note explaining why these metrics are being added...'
        }),
        help_text="Optional: Explain why you're adjusting these metrics"
    )

class AppForSaleForm(forms.ModelForm):
    """Form specifically for listing apps for sale"""
    
    tech_stack = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Python, Django, JavaScript, React, PostgreSQL'
        }),
        help_text="List the technologies and frameworks used in your app (comma-separated)"
    )

    class Meta:
        model = AppListing
        fields = [
            'name', 'description', 'ai_features', 'category',
            'sale_price', 'sale_includes_source_code', 'sale_includes_assets',
            'sale_includes_support', 'support_duration_months',
            'monthly_revenue', 'monthly_users', 'tech_stack',
            'deployment_type', 'demo_video', 'github_url', 'demo_url'
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Describe your app, its features, and business potential...'
            }),
            'ai_features': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Detail the AI/ML components and their benefits...'
            }),
            'sale_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': 'Enter your asking price'
            }),
            'support_duration_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of months of support included'
            }),
            'monthly_revenue': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': 'Current monthly revenue'
            }),
            'monthly_users': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Current number of monthly active users'
            }),
            'demo_video': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Link to app demonstration video'
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Link to GitHub repository'
            }),
            'demo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Link to live demo'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make certain fields required
        required_fields = [
            'sale_price', 'tech_stack', 'deployment_type',
            'sale_includes_source_code', 'sale_includes_assets'
        ]
        for field in required_fields:
            self.fields[field].required = True
        
        # Make support duration required if support is included
        if self.data.get('sale_includes_support'):
            self.fields['support_duration_months'].required = True

    def clean_tech_stack(self):
        tech_stack = self.cleaned_data.get('tech_stack', '')
        # Convert comma-separated string to list and clean it up
        technologies = [tech.strip() for tech in tech_stack.split(',') if tech.strip()]
        # Convert to the format expected by the model
        return {'technologies': technologies}

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('sale_includes_support') and not cleaned_data.get('support_duration_months'):
            raise ValidationError({
                'support_duration_months': 'Support duration is required when support is included.'
            })
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.listing_type = AppListing.ListingType.FOR_SALE
        
        # Set default values for required fields that aren't relevant for sale listings
        instance.funding_goal = 0
        instance.currency = AppListing.Currency.NGN
        instance.available_percentage = 0
        instance.min_investment_percentage = 0
        instance.price_per_percentage = 0
        instance.equity_percentage = 0
        instance.exchange_rate = 1
        instance.remaining_percentage = 0
        instance.funding_end_date = timezone.now() + timezone.timedelta(days=365)  # Set to 1 year from now
        instance.project_status = AppListing.Status.ACTIVE
        
        if commit:
            instance.save()
        return instance
