from django import forms

class AppEngagementForm(forms.Form):
    add_views = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of views to add"
    )
    
    add_likes = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of likes to add"
    )
    
    add_upvotes = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of upvotes to add"
    )
    
    add_comments = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Number of comments to add"
    )
    
    engagement_note = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add a note explaining why these metrics are being added...'
        }),
        help_text="Required: Explain why you're adjusting these metrics"
    ) 