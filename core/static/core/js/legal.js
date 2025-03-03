document.addEventListener('DOMContentLoaded', function() {
    const acceptButtons = document.querySelectorAll('.accept-legal-document');
    
    acceptButtons.forEach(button => {
        button.addEventListener('click', function() {
            const documentId = this.dataset.documentId;
            acceptLegalDocument(documentId);
        });
    });
});

function acceptLegalDocument(documentId) {
    // Get CSRF token from meta tag
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch(`/legal/accept/${documentId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Check if there's a next URL to redirect to
            if (data.next_url) {
                window.location.href = data.next_url;
            } else {
                window.location.href = '/dashboard/';
            }
        } else {
            alert(data.message || 'Error accepting agreement. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error accepting agreement. Please try again.');
    });
}

// Helper function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
} 