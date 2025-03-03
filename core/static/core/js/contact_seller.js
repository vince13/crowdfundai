document.addEventListener('DOMContentLoaded', function() {
    const contactSellerForm = document.getElementById('contactSellerForm');
    if (contactSellerForm) {
        contactSellerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const submitButton = this.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Sending...';

            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Hide the modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('contactSellerModal'));
                    modal.hide();
                    
                    // Create success alert
                    const successAlert = document.createElement('div');
                    successAlert.className = 'alert alert-success alert-dismissible fade show position-fixed bottom-0 end-0 m-3';
                    successAlert.style.zIndex = '1050';
                    successAlert.innerHTML = `
                        <i class="fas fa-check-circle me-2"></i>
                        ${data.message}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    `;
                    document.body.appendChild(successAlert);
                    
                    // Auto remove after 5 seconds
                    setTimeout(() => {
                        successAlert.remove();
                    }, 5000);
                    
                    // Reset form
                    contactSellerForm.reset();
                } else {
                    throw new Error(data.message || 'Failed to send message');
                }
            })
            .catch(error => {
                // Show error message
                const errorAlert = document.createElement('div');
                errorAlert.className = 'alert alert-danger alert-dismissible fade show';
                errorAlert.innerHTML = `
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${error.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                contactSellerForm.insertBefore(errorAlert, contactSellerForm.firstChild);
            })
            .finally(() => {
                submitButton.disabled = false;
                submitButton.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send Message';
            });
        });
    }
}); 