from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Prepare email content
        email_subject = f"Contact Form: {subject}"
        email_message = f"""
        Name: {name}
        Email: {email}
        Subject: {subject}
        
        Message:
        {message}
        """
        
        try:
            # Send email
            send_mail(
                email_subject,
                email_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('core:contact')
        except Exception as e:
            messages.error(request, 'There was an error sending your message. Please try again.')
    
    # If subject is provided in GET parameters, pre-fill it
    initial_subject = request.GET.get('subject', '')
    
    return render(request, 'core/contact.html', {
        'initial_subject': initial_subject
    }) 