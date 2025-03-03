class AppListing(models.Model):
    # ... existing model fields ...

    @property
    def has_user_upvoted(self):
        if not hasattr(self, '_has_user_upvoted'):
            user = getattr(self, '_current_user', None)
            if user and user.is_authenticated:
                self._has_user_upvoted = self.community_votes.filter(
                    user=user, 
                    vote_type='UPVOTE'
                ).exists()
            else:
                self._has_user_upvoted = False
        return self._has_user_upvoted

    @property
    def has_user_liked(self):
        if not hasattr(self, '_has_user_liked'):
            user = getattr(self, '_current_user', None)
            if user and user.is_authenticated:
                self._has_user_liked = self.community_votes.filter(
                    user=user, 
                    vote_type='LIKE'
                ).exists()
            else:
                self._has_user_liked = False
        return self._has_user_liked

    @property
    def upvotes_count(self):
        if not hasattr(self, '_upvotes_count'):
            self._upvotes_count = self.community_votes.filter(vote_type='UPVOTE').count()
        return self._upvotes_count

    @property
    def likes_count(self):
        if not hasattr(self, '_likes_count'):
            self._likes_count = self.community_votes.filter(vote_type='LIKE').count()
        return self._likes_count

class AppTeamMember(models.Model):
    ROLE_CHOICES = [
        ('DEVELOPER', 'Developer'),
        ('DESIGNER', 'Designer'),
        ('PROJECT_MANAGER', 'Project Manager'),
        ('QA', 'Quality Assurance'),
        ('DEVOPS', 'DevOps Engineer'),
        ('OTHER', 'Other'),
    ]

    app = models.ForeignKey('App', on_delete=models.CASCADE, related_name='team_members')
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    custom_role = models.CharField(max_length=50, blank=True, null=True, help_text="Specify role if 'Other' is selected")
    email = models.EmailField(blank=True, null=True)
    github_profile = models.URLField(blank=True, null=True)
    linkedin_profile = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    contribution_details = models.TextField(help_text="Describe the team member's contributions to the app")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.name} - {self.get_role_display()} at {self.app.name}"

    def get_display_role(self):
        if self.role == 'OTHER' and self.custom_role:
            return self.custom_role
        return self.get_role_display() 