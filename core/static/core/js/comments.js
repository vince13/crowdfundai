// Function to update comment count in the UI
async function updateCommentCount() {
    try {
        const appIdElement = document.querySelector('[data-app-id]');
        if (!appIdElement) {
            console.error('App ID element not found');
            return;
        }
        const appId = appIdElement.dataset.appId;
        
        const response = await fetch(`/apps/${appId}/comment-count/`);
        if (!response.ok) {
            throw new Error('Failed to fetch comment count');
        }
        
        const data = await response.json();
        // Ensure count is always a number, default to 0 if null/undefined
        const count = parseInt(data.count) || 0;
        
        // Update all elements with class 'comment-count'
        const commentCountElements = document.querySelectorAll('.comment-count');
        commentCountElements.forEach(element => {
            if (element) {
                // Always set the text content, even if count is 0
                element.textContent = count.toLocaleString();
                // Ensure the element remains visible
                element.style.display = 'inline';
            }
        });
    } catch (error) {
        console.error('Error updating comment count:', error);
        // Set default value in case of error
        const commentCountElements = document.querySelectorAll('.comment-count');
        commentCountElements.forEach(element => {
            if (element) {
                element.textContent = '0';
                element.style.display = 'inline';
            }
        });
    }
}

// Ensure the function is called after DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initial update of comment count
    updateCommentCount();
    
    // Set up an interval to update the count periodically (every 30 seconds)
    setInterval(updateCommentCount, 30000);
});

document.addEventListener('DOMContentLoaded', function() {
    // Get all the necessary elements once
    const commentForm = document.getElementById('comment-form');
    const commentsContainer = document.getElementById('comments-container');
    const commentTemplate = document.getElementById('comment-template');
    const replyTemplate = document.getElementById('reply-template');
    const replyFormTemplate = document.getElementById('reply-form-template');
    const deleteModal = document.getElementById('deleteCommentModal');
    const MAX_COMMENT_LENGTH = 1000;
    
    // Initialize modal globally
    window.commentToDelete = null;
    window.deleteModalInstance = deleteModal ? new bootstrap.Modal(deleteModal) : null;

    // Handle delete confirmation
    if (deleteModal) {
        const confirmDeleteBtn = deleteModal.querySelector('#confirmDeleteComment');
        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener('click', async function() {
                if (!window.commentToDelete) return;
                
                try {
                    const commentId = window.commentToDelete.dataset.commentId;
                    const appId = window.commentToDelete.dataset.appId;
                    
                    if (!commentId || !appId) {
                        throw new Error('Missing comment ID or app ID');
                    }

                    const response = await fetch(`/apps/${appId}/comments/${commentId}/delete/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        }
                    });
                    
                    if (!response.ok) throw new Error('Failed to delete comment');
                    
                    const data = await response.json();
                    if (data.success) {
                        // Remove the comment element
                        window.commentToDelete.remove();
                        // Update comment count
                        updateCommentCount();
                        // Hide modal
                        window.deleteModalInstance.hide();
                        showMessage('Comment deleted successfully', 'success');
                    }
                } catch (error) {
                    console.error('Error deleting comment:', error);
                    showMessage('Failed to delete comment. Please try again.', 'danger');
                } finally {
                    // Clear the stored comment
                    window.commentToDelete = null;
                }
            });
        } else {
            console.error('Delete confirmation button not found in modal');
        }
    }
    
    // Make replyFormTemplate globally available
    window.replyFormTemplate = replyFormTemplate;
    
    // Toggle comments collapse
    const toggleCommentsBtn = document.querySelector('[data-bs-toggle="collapse"]');
    if (toggleCommentsBtn) {
        toggleCommentsBtn.addEventListener('click', function() {
            const icon = this.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        });
    }
    
    // Load initial comments with loading state
    loadComments();

    // Handle reply button clicks
    document.addEventListener('click', function(e) {
        const replyBtn = e.target.closest('.reply-btn');
        if (replyBtn) {
            e.preventDefault();
            
            const comment = replyBtn.closest('.comment');
            const commentId = comment.dataset.commentId;
            const repliesContainer = comment.querySelector('.replies-container');
            
            // Remove any existing reply forms
            const existingForm = document.querySelector('.reply-form');
            if (existingForm) {
                existingForm.remove();
            }
            
            // Create and insert reply form
            const replyForm = replyFormTemplate.content.cloneNode(true).querySelector('.reply-form');
            replyForm.dataset.parentId = commentId;
            
            // Add character counter functionality
            const textarea = replyForm.querySelector('textarea');
            const charCounter = replyForm.querySelector('.char-counter');
            const submitBtn = replyForm.querySelector('button[type="submit"]');
            
            textarea.addEventListener('input', function() {
                const remaining = MAX_COMMENT_LENGTH - this.value.length;
                charCounter.textContent = `${remaining} characters remaining`;
                charCounter.className = `text-${remaining < 50 ? 'danger' : 'muted'} d-block mt-1`;
                submitBtn.disabled = remaining < 0;
            });
            
            // Handle reply form submission
            replyForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const content = textarea.value.trim();
                const appId = commentForm.dataset.appId;
                
                try {
                    const response = await fetch(`/apps/${appId}/comments/add/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        },
                        body: JSON.stringify({
                            content: content,
                            parent_id: commentId
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error('Failed to add reply');
                    }
                    
                    const data = await response.json();
                    if (data.success) {
                        // Add reply to UI
                        const replyElement = createReplyElement(data.comment);
                        repliesContainer.appendChild(replyElement);
                        
                        // Update comment count
                        updateCommentCount();
                        
                        // Clear and remove form
                        replyForm.remove();
                    }
                } catch (error) {
                    console.error('Error adding reply:', error);
                    alert('Failed to add reply. Please try again.');
                }
            });
            
            // Handle cancel button
            const cancelBtn = replyForm.querySelector('.cancel-reply-btn');
            cancelBtn.addEventListener('click', () => replyForm.remove());
            
            repliesContainer.insertBefore(replyForm, repliesContainer.firstChild);
            textarea.focus();
        }
    });
    
    // Handle delete button clicks with improved modal handling
    document.addEventListener('click', function(e) {
        const deleteBtn = e.target.closest('.delete-comment-btn');
        if (deleteBtn) {
            e.preventDefault();
            e.stopPropagation();
            
            // Store the comment to be deleted
            commentToDelete = deleteBtn.closest('.comment, .reply');
            
            // Update modal content if needed
            const modalTitle = deleteModal.querySelector('.modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Delete ' + 
                    (commentToDelete.classList.contains('reply') ? 'Reply' : 'Comment');
            }
            
            // Show modal
            if (window.deleteModalInstance) {
                window.deleteModalInstance.show();
            }
        }
    });
    
    // Initialize comment form if it exists
    if (commentForm) {
        initializeCommentForm(commentForm);
    }

    // Function to initialize comment form
    function initializeCommentForm(form) {
        const textarea = form.querySelector('textarea[name="content"]');
        const submitButton = form.querySelector('button[type="submit"]');
        const charCounter = form.querySelector('.char-counter');
        
        if (!textarea || !submitButton || !charCounter) {
            console.error('Required form elements not found');
            return;
        }

        // Character counter
            textarea.addEventListener('input', function() {
            const maxLength = parseInt(textarea.getAttribute('maxlength')) || 200;
            const remaining = maxLength - this.value.length;
                charCounter.textContent = `${remaining} characters remaining`;
                charCounter.className = `text-${remaining < 50 ? 'danger' : 'muted'} d-block mb-2`;
                    submitButton.disabled = remaining < 0;
            });
        
        // Form submission
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const content = textarea.value.trim();
            if (!content) {
                alert('Please enter a comment');
                return;
            }

            submitButton.disabled = true;
            const appId = this.dataset.appId;
            
            try {
                const response = await fetch(`/apps/${appId}/comments/add/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({ content })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to add comment');
                }
                
                const data = await response.json();
                if (data.success) {
                    // Add comment to UI
                    const commentElement = createCommentElement(data.comment);
                    if (commentElement && commentsContainer) {
                    commentsContainer.insertBefore(commentElement, commentsContainer.firstChild);
                    }
                    
                    // Clear form
                    textarea.value = '';
                    const maxLength = parseInt(textarea.getAttribute('maxlength')) || 200;
                    charCounter.textContent = `${maxLength} characters remaining`;
                    charCounter.className = 'text-muted d-block mb-2';

                    // Update comment count
                    if (typeof updateCommentCount === 'function') {
                        updateCommentCount();
                    }
                }
            } catch (error) {
                console.error('Error adding comment:', error);
                alert('Failed to add comment. Please try again.');
            } finally {
                submitButton.disabled = false;
            }
        });
    }

    // Handle comments section collapse
    const commentsSection = document.getElementById('commentsSection');
    const toggleIcon = document.querySelector('.comment-toggle-icon');
    
    if (commentsSection && toggleIcon) {
        commentsSection.addEventListener('show.bs.collapse', function () {
            toggleIcon.classList.remove('bi-chevron-down');
            toggleIcon.classList.add('bi-chevron-up');
            
            // Load comments when section is expanded
            if (!this.dataset.loaded) {
                loadComments();
                this.dataset.loaded = 'true';
            }
        });

        commentsSection.addEventListener('hide.bs.collapse', function () {
            toggleIcon.classList.remove('bi-chevron-up');
            toggleIcon.classList.add('bi-chevron-down');
        });
    }
});

async function loadComments() {
    const commentsContainer = document.getElementById('comments-container');
    if (!commentsContainer) return;

    // Show loading spinner
    commentsContainer.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading comments...</span>
            </div>
        </div>
    `;

    try {
        const appId = commentsContainer.dataset.appId;
        if (!appId) {
            console.error('App ID not found in comments container');
            return;
        }

        const response = await fetch(`/apps/${appId}/comments/`);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        if (!data.success) {
            throw new Error(data.message || 'Failed to load comments');
        }

        if (!data.comments) {
            throw new Error('No comments data received');
        }

        if (data.comments.length === 0) {
            commentsContainer.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-comments text-muted fa-2x mb-3"></i>
                    <p class="text-muted">No comments yet. Be the first to comment!</p>
                </div>
            `;
            return;
        }

        renderComments(data.comments);
        updateCommentCount();
    } catch (error) {
        console.error('Error loading comments:', error);
        commentsContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle me-2"></i>
                Failed to load comments. Please try again.
            </div>
        `;
    }
}

function renderComments(comments) {
    const commentsContainer = document.getElementById('comments-container');
    if (!commentsContainer) {
        console.error('Comments container not found');
        return;
    }

    const commentTemplate = document.getElementById('comment-template');
    if (!commentTemplate) {
        console.error('Comment template not found');
        return;
    }

    commentsContainer.innerHTML = '';
    
    if (!Array.isArray(comments)) {
        console.error('Comments is not an array:', comments);
        return;
    }

    comments.forEach(comment => {
        try {
            const commentElement = createCommentElement(comment);
            if (commentElement) {
                commentsContainer.appendChild(commentElement);
            }
        } catch (error) {
            console.error('Error rendering comment:', comment, error);
        }
    });
}

function createCommentElement(comment) {
    try {
        const commentElement = document.querySelector('#comment-template').content.cloneNode(true).querySelector('.comment');
        
        // Get app_id from either the comment object or the comments container
        const appId = comment.app_id || document.getElementById('comments-container').dataset.appId;
        if (!appId) {
            console.error('App ID not found');
            return null;
        }
        
        // Set data attributes
        commentElement.dataset.commentId = comment.id;
        commentElement.dataset.appId = appId;
        
        // Get all required elements
        const author = commentElement.querySelector('.comment-author');
        const content = commentElement.querySelector('.comment-content');
        const timestamp = commentElement.querySelector('.comment-timestamp');
        const avatar = commentElement.querySelector('.comment-avatar');
        const deleteBtn = commentElement.querySelector('.delete-comment-btn');
        const toggleRepliesBtn = commentElement.querySelector('.toggle-replies-btn');
        const repliesContainer = commentElement.querySelector('.replies-container');
        const repliesCount = commentElement.querySelector('.replies-count');
        const repliesText = commentElement.querySelector('.replies-text');
        
        // Verify all required elements exist
        if (!author || !content || !timestamp || !avatar) {
            console.error('Required comment elements not found in template');
            return null;
        }

        // Set content with null checks
        author.textContent = comment.author_name || comment.author || 'Anonymous';
        content.textContent = comment.content || '';
        timestamp.textContent = comment.created_at ? formatDate(comment.created_at) : 'Just now';
        avatar.src = comment.author_avatar || '/static/core/images/default-avatar.png';
        
        // Handle delete button
        const canDelete = Boolean(comment.can_delete || comment.is_author);
        if (deleteBtn) {
            deleteBtn.style.display = canDelete ? 'block' : 'none';
        }

        // Handle replies
        if (toggleRepliesBtn && repliesContainer && repliesCount && repliesText) {
            if (comment.replies && Array.isArray(comment.replies) && comment.replies.length > 0) {
                const replyCount = comment.replies.length;
                repliesCount.textContent = replyCount;
                repliesText.textContent = `repl${replyCount === 1 ? 'y' : 'ies'}`;
                toggleRepliesBtn.classList.remove('d-none');

                // Add replies to container
                comment.replies.forEach(reply => {
                    if (reply) {
                        const replyElement = createReplyElement(reply);
                        if (replyElement) {
                            repliesContainer.appendChild(replyElement);
                        }
                    }
                });
            } else {
                toggleRepliesBtn.classList.add('d-none');
            }
        }

        // Handle reply button
        const replyBtn = commentElement.querySelector('.reply-btn');
        const replyFormContainer = commentElement.querySelector('.reply-form-container');
        
        if (replyBtn && replyFormContainer) {
            replyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Remove any existing reply forms
                const existingForms = document.querySelectorAll('.reply-form');
                existingForms.forEach(form => form.remove());

                // Get the reply form template
                const replyFormTemplate = document.getElementById('reply-form-template');
                if (!replyFormTemplate) {
                    console.error('Reply form template not found');
                    return;
                }

                // Clone the template
                const replyForm = replyFormTemplate.content.cloneNode(true).querySelector('.reply-form');
                if (!replyForm) {
                    console.error('Reply form not found in template');
                    return;
                }

                // Set up the reply form
                replyForm.dataset.parentId = comment.id;
                const textarea = replyForm.querySelector('textarea[name="content"]');
                const charCounter = replyForm.querySelector('.char-counter');

                // Handle character counter
                if (textarea && charCounter) {
                    textarea.addEventListener('input', function() {
                        const maxLength = parseInt(this.getAttribute('maxlength')) || 200;
                        const remaining = maxLength - this.value.length;
                        charCounter.textContent = `${remaining} characters remaining`;
                    });
                }

                // Handle form submission
                replyForm.addEventListener('submit', async function(e) {
                    e.preventDefault();
                    if (!textarea) return;
                    
                    const content = textarea.value.trim();
                    if (!content) return;

                    try {
                        const appId = commentElement.dataset.appId;
                        const response = await fetch(`/apps/${appId}/comments/add/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                            },
                            body: JSON.stringify({
                                content: content,
                                parent_id: comment.id
                            })
                        });

                        if (!response.ok) throw new Error('Failed to add reply');

                        const data = await response.json();
                        if (data.success) {
                            const replyElement = createReplyElement(data.comment);
                            if (replyElement) {
                                repliesContainer.appendChild(replyElement);
                                replyForm.remove();

                                // Update reply count and show replies
                                const currentCount = parseInt(repliesCount.textContent) || 0;
                                repliesCount.textContent = currentCount + 1;
                                repliesText.textContent = `repl${currentCount + 1 === 1 ? 'y' : 'ies'}`;
                                toggleRepliesBtn.classList.remove('d-none');
                                repliesContainer.classList.add('show');
                            }
                        }
                    } catch (error) {
                        console.error('Error adding reply:', error);
                        alert('Failed to add reply. Please try again.');
                    }
                });

                // Handle cancel button
                const cancelBtn = replyForm.querySelector('.cancel-reply');
                if (cancelBtn) {
                    cancelBtn.addEventListener('click', () => replyForm.remove());
                }

                // Add the form to the container
                replyFormContainer.innerHTML = '';
                replyFormContainer.appendChild(replyForm);
                if (textarea) textarea.focus();
            });
        }

        // Handle comment options
        const deleteOption = commentElement.querySelector('.delete-comment');
        const shareOption = commentElement.querySelector('.share-comment button');
        const reportOption = commentElement.querySelector('.report-comment button');

        // Show delete option if user can delete
        if (deleteOption) {
            const canDelete = Boolean(comment.can_delete || comment.is_author);
            console.log('Comment can_delete:', canDelete);
            
            if (canDelete) {
                deleteOption.style.display = 'list-item';
                const deleteButton = deleteOption.querySelector('button');
                if (deleteButton) {
                    deleteButton.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Store the comment element for deletion
                        window.commentToDelete = commentElement;
                        
                        // Show modal
                        if (window.deleteModalInstance) {
                            window.deleteModalInstance.show();
                        }
                    });
                }
            } else {
                deleteOption.style.display = 'none';
            }
        }

        // Handle share
        if (shareOption) {
            shareOption.addEventListener('click', async () => {
                try {
                    // Create a unique comment URL with the comment ID
                    const commentUrl = `${window.location.origin}${window.location.pathname}#comment-${comment.id}`;
                    await navigator.clipboard.writeText(commentUrl);
                    showMessage('Comment link copied to clipboard!', 'success');
                } catch (error) {
                    console.error('Error sharing comment:', error);
                    showMessage('Failed to copy link. Please try again.', 'danger');
                }
            });
        }

        // Handle report
        if (reportOption) {
            reportOption.addEventListener('click', async () => {
                try {
                    // Use the appId from the comment element's dataset
                    const response = await fetch(`/apps/${appId}/comments/${comment.id}/report/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        },
                        body: JSON.stringify({ reason: 'inappropriate content' })
                    });

                    if (!response.ok) {
                        const data = await response.json();
                        throw new Error(data.message || 'Failed to report comment');
                    }

                    showMessage('Comment reported successfully. Our team will review it.', 'success');
                } catch (error) {
                    console.error('Error reporting comment:', error);
                    showMessage(error.message || 'Failed to report comment. Please try again.', 'danger');
                }
            });
        }

        return commentElement;
    } catch (error) {
        console.error('Error creating comment element:', error);
        return null;
    }
}

function addCommentToUI(comment) {
    const commentsContainer = document.getElementById('comments-container');
    const noCommentsMessage = commentsContainer.querySelector('.text-center');
    
    // Remove "no comments" message if it exists
    if (noCommentsMessage) {
        noCommentsMessage.remove();
    }
    
    if (comment.parent_id) {
        // This is a reply - add it to the parent comment's replies container
        const parentComment = document.querySelector(`.comment[data-comment-id="${comment.parent_id}"]`);
        if (parentComment) {
            const repliesContainer = parentComment.querySelector('.replies-container');
            const replyElement = createCommentElement(comment);
            replyElement.classList.add('reply');
            repliesContainer.appendChild(replyElement);
            
            // Hide the reply form
            const replyForm = parentComment.querySelector('.reply-form');
            if (replyForm) {
                replyForm.remove();
            }
        }
    } else {
        // This is a new top-level comment - add it at the top of the comments
        const commentElement = createCommentElement(comment);
        if (commentsContainer.firstChild) {
            commentsContainer.insertBefore(commentElement, commentsContainer.firstChild);
        } else {
            commentsContainer.appendChild(commentElement);
        }
    }
    
    // Scroll the new comment into view
    const newComment = document.querySelector(`.comment[data-comment-id="${comment.id}"]`);
    if (newComment) {
        newComment.scrollIntoView({ behavior: 'smooth', block: 'center' });
        newComment.classList.add('comment-highlight');
        setTimeout(() => {
            newComment.classList.remove('comment-highlight');
        }, 2000);
    }
}

function showReplyForm(commentId) {
    const comment = document.querySelector(`.comment[data-comment-id="${commentId}"]`);
    const replyForm = document.getElementById('comment-form').cloneNode(true);
    
    replyForm.id = `reply-form-${commentId}`;
    replyForm.dataset.parentId = commentId;
    
    const existingForm = comment.querySelector('.reply-form');
    if (existingForm) {
        existingForm.remove();
    } else {
        comment.appendChild(replyForm);
        replyForm.querySelector('textarea').focus();
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showMessage(message, type = 'info') {
    const messageDiv = document.getElementById('message-container');
    if (messageDiv) {
        messageDiv.textContent = message;
        messageDiv.className = `alert alert-${type}`;
        messageDiv.style.display = 'block';
        
        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

function createReplyElement(reply) {
    console.log('Creating reply element with data:', reply);
    
    try {
        const replyElement = document.getElementById('reply-template').content.cloneNode(true).querySelector('.reply');
        if (!replyElement) {
            console.error('Failed to create reply element from template');
            return null;
        }

        // Get app_id from either the reply object or the comments container
        const appId = reply.app_id || document.getElementById('comments-container').dataset.appId;
        if (!appId) {
            console.error('App ID not found');
            return null;
        }

        // Set data attributes
        replyElement.dataset.commentId = reply.id;
        replyElement.dataset.appId = appId;
        
        // Get all required elements
        const author = replyElement.querySelector('.comment-author');
        const content = replyElement.querySelector('.comment-content');
        const timestamp = replyElement.querySelector('.comment-timestamp');
        const avatar = replyElement.querySelector('.comment-avatar');
        const deleteOption = replyElement.querySelector('.delete-comment');
        
        if (!author || !content || !timestamp || !avatar) {
            console.error('Required reply elements not found in template');
            return null;
        }

        // Set content
        author.textContent = reply.author_name || reply.author || 'Anonymous';
        content.textContent = reply.content || '';
        timestamp.textContent = reply.created_at ? formatDate(reply.created_at) : 'Just now';
        avatar.src = reply.author_avatar || '/static/core/images/default-avatar.png';
        
        // Handle delete option
        if (deleteOption) {
            const canDelete = Boolean(reply.can_delete || reply.is_author);
            console.log('Reply can_delete:', canDelete);
            
            if (canDelete) {
                deleteOption.style.display = 'list-item';
                const deleteButton = deleteOption.querySelector('button');
                if (deleteButton) {
                    deleteButton.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Store the reply element for deletion
                        window.commentToDelete = replyElement;
                        
                        // Show modal
                        if (window.deleteModalInstance) {
                            window.deleteModalInstance.show();
                        }
                    });
                }
            } else {
                deleteOption.style.display = 'none';
            }
        }

        // Handle share and report options
        const shareOption = replyElement.querySelector('.share-comment button');
        const reportOption = replyElement.querySelector('.report-comment button');

        if (shareOption) {
            shareOption.addEventListener('click', async () => {
                try {
                    // Create a unique reply URL with both parent comment and reply IDs
                    const replyUrl = `${window.location.origin}${window.location.pathname}#reply-${reply.id}`;
                    await navigator.clipboard.writeText(replyUrl);
                    showMessage('Reply link copied to clipboard!', 'success');
                } catch (error) {
                    console.error('Error sharing reply:', error);
                    showMessage('Failed to copy link. Please try again.', 'danger');
                }
            });
        }

        if (reportOption) {
            reportOption.addEventListener('click', async () => {
                try {
                    const response = await fetch(`/apps/${appId}/comments/${reply.id}/report/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                        },
                        body: JSON.stringify({ reason: 'inappropriate content' })
                    });

                    if (!response.ok) {
                        const data = await response.json();
                        throw new Error(data.message || 'Failed to report reply');
                    }

                    showMessage('Reply reported successfully. Our team will review it.', 'success');
                } catch (error) {
                    console.error('Error reporting reply:', error);
                    showMessage(error.message || 'Failed to report reply. Please try again.', 'danger');
                }
            });
        }

        return replyElement;
    } catch (error) {
        console.error('Error creating reply element:', error);
        return null;
    }
} 

