from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def about_us(request):
    """View for the About Us page."""
    return render(request, 'core/about.html', {
        'title': 'About Us'
    })

@login_required
def support_home(request):
    """View for the main support page."""
    return render(request, 'core/support/home.html', {
        'title': 'Support Center'
    })

@login_required
def submit_ticket(request):
    """View for submitting a support ticket."""
    if request.method == 'POST':
        # Here you would handle the ticket submission
        # For now, just show a success message
        messages.success(request, "Your support ticket has been submitted. We'll get back to you soon.")
        return redirect('core:support_home')
        
    return render(request, 'core/support/submit_ticket.html', {
        'title': 'Submit Support Ticket'
    })

@login_required
def faq(request):
    """View for the FAQ page."""
    faqs = [
        {
            'category': 'Investment',
            'questions': [
                {
                    'question': 'How do I invest in an app?',
                    'answer': 'To invest in an app, navigate to the app listing, click on "Invest", enter your desired investment amount, and follow the payment process.'
                },
                {
                    'question': 'What is the minimum investment amount?',
                    'answer': 'The minimum investment is 1% of the available equity for any given app.'
                }
            ]
        },
        {
            'category': 'Certificates',
            'questions': [
                {
                    'question': 'How do I download my investment certificate?',
                    'answer': 'You can download your investment certificate from your portfolio page by clicking on the specific investment and selecting "Download Certificate".'
                },
                {
                    'question': 'What if my certificate is not generating?',
                    'answer': 'If your certificate is not generating, please ensure your payment has been confirmed and try refreshing the page. If the issue persists, contact support.'
                }
            ]
        },
        {
            'category': 'Account',
            'questions': [
                {
                    'question': 'How do I update my profile?',
                    'answer': 'You can update your profile by clicking on your username in the top right corner and selecting "Profile". Here you can edit your information.'
                },
                {
                    'question': 'How do I change my password?',
                    'answer': 'Go to your profile settings and click on "Change Password". Follow the prompts to set a new password.'
                }
            ]
        }
    ]
    return render(request, 'core/support/faq.html', {
        'title': 'Frequently Asked Questions',
        'faqs': faqs
    }) 