from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

class DeveloperRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_developer()

    def handle_no_permission(self):
        messages.error(self.request, 'Only developers can access this page.')
        return redirect('home')

class InvestorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_investor()

    def handle_no_permission(self):
        messages.error(self.request, 'Only investors can access this page.')
        return redirect('home') 