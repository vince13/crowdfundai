from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from ..models import User, Release

class ApprovalService:
    """Service for handling multi-signature approvals"""
    
    @classmethod
    def request_approval(cls, release, requested_by):
        """
        Request approval for a release
        
        Args:
            release (Release): The release to be approved
            requested_by (User): The user requesting approval
            
        Returns:
            bool: True if request was created successfully
        
        Raises:
            ValidationError: If release is not in valid state for approval
        """
        if not release.can_request_approval():
            raise ValidationError("Release is not in valid state for approval request")
            
        # Set approval request details
        release.approval_requested_by = requested_by
        release.approval_requested_at = timezone.now()
        release.save()
        
        # TODO: Notify relevant approvers
        return True
        
    @classmethod
    def approve(cls, release, approved_by, notes=""):
        """
        Approve a release
        
        Args:
            release (Release): The release to approve
            approved_by (User): The user approving the release
            notes (str): Optional approval notes
            
        Returns:
            bool: True if approved successfully
            
        Raises:
            ValidationError: If release cannot be approved
        """
        if not release.can_be_approved():
            raise ValidationError("Release cannot be approved in current state")
            
        if not cls.is_valid_approver(approved_by):
            raise ValidationError("User is not authorized to approve releases")
            
        # Record approval
        release.approved_by = approved_by
        release.approval_notes = notes
        release.approval_date = timezone.now()
        release.status = Release.Status.APPROVED
        release.save()
        
        # TODO: Notify relevant parties
        return True
        
    @classmethod 
    def reject(cls, release, rejected_by, reason):
        """
        Reject a release approval
        
        Args:
            release (Release): The release to reject
            rejected_by (User): The user rejecting the release
            reason (str): Reason for rejection
            
        Returns:
            bool: True if rejected successfully
            
        Raises:
            ValidationError: If release cannot be rejected
        """
        if not release.can_be_rejected():
            raise ValidationError("Release cannot be rejected in current state")
            
        if not cls.is_valid_approver(rejected_by):
            raise ValidationError("User is not authorized to reject releases")
            
        # Record rejection
        release.rejected_by = rejected_by
        release.rejection_reason = reason
        release.rejected_at = timezone.now()
        release.status = Release.Status.REJECTED
        release.save()
        
        # TODO: Notify relevant parties
        return True
        
    @classmethod
    def is_valid_approver(cls, user):
        """Check if user is authorized to approve/reject releases"""
        return user.is_staff and user.has_perm('core.can_approve_releases')
        
    @classmethod
    def get_pending_approvals(cls):
        """Get all releases pending approval"""
        return Release.objects.filter(
            status=Release.Status.PENDING,
            approval_requested_at__isnull=False,
            approval_date__isnull=True,
            rejected_at__isnull=True
        ) 