document.addEventListener('DOMContentLoaded', function() {
    // Get all vote buttons
    const voteButtons = document.querySelectorAll('.vote-btn');
    
    voteButtons.forEach(button => {
        button.addEventListener('click', async function() {
            const voteType = this.dataset.voteType;
            const appId = this.dataset.appId;
            const container = this.closest('.card-body');
            const messageDiv = container.querySelector('#vote-message');
            
            try {
                const response = await fetch(`/apps/${appId}/vote/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({ vote_type: voteType })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to process vote');
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // Update vote counts
                    const upvoteBtn = container.querySelector('button[data-vote-type="UPVOTE"]');
                    const likeBtn = container.querySelector('button[data-vote-type="LIKE"]');
                    
                    if (upvoteBtn) {
                        const upvoteCount = upvoteBtn.querySelector('span');
                        if (upvoteCount) upvoteCount.textContent = data.upvote_count;
                    }
                    
                    if (likeBtn) {
                        const likeCount = likeBtn.querySelector('span');
                        if (likeCount) likeCount.textContent = data.like_count;
                    }
                    
                    // Update button styles based on user's current votes
                    if (upvoteBtn) {
                        upvoteBtn.className = `btn btn-sm ${data.user_votes.includes('UPVOTE') ? 'btn-primary' : 'btn-outline-primary'} vote-btn`;
                    }
                    if (likeBtn) {
                        likeBtn.className = `btn btn-sm ${data.user_votes.includes('LIKE') ? 'btn-danger' : 'btn-outline-danger'} vote-btn`;
                    }
                    
                    // Show success message
                    if (messageDiv) {
                        messageDiv.className = 'alert alert-success mt-2';
                        messageDiv.textContent = data.message;
                        messageDiv.classList.remove('d-none');
                        
                        // Hide message after 3 seconds
                        setTimeout(() => {
                            messageDiv.classList.add('d-none');
                        }, 3000);
                    }
                } else {
                    throw new Error(data.message);
                }
            } catch (error) {
                // Show error message
                if (messageDiv) {
                    messageDiv.className = 'alert alert-danger mt-2';
                    messageDiv.textContent = error.message || 'An error occurred while processing your vote.';
                    messageDiv.classList.remove('d-none');
                    
                    // Hide message after 3 seconds
                    setTimeout(() => {
                        messageDiv.classList.add('d-none');
                    }, 3000);
                }
            }
        });
    });
}); 