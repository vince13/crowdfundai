// Singleton pattern for AIAssessmentForm
const AIAssessmentForm = (function() {
    let instance;

    function createInstance() {
        // Private variables
        let currentSection = 1;
        let totalSections = 4;
        let formData = {};

        // Private methods
        function validateSection(section) {
            const inputs = document.querySelectorAll(`#section${section} [required]`);
            let isValid = true;
            inputs.forEach(input => {
                if (!input.value) {
                    isValid = false;
                    input.classList.add('is-invalid');
                } else {
                    input.classList.remove('is-invalid');
                }
            });
            return isValid;
        }

        function updateProgressBar() {
            const progress = (currentSection / totalSections) * 100;
            const progressBar = document.querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.setAttribute('aria-valuenow', progress);
            }
        }

        // Public methods
        return {
            init: function() {
                // Get form URL from modal data attribute
                const modal = document.getElementById('aiAssessmentModal');
                if (!modal) return;

                const formUrl = modal.dataset.formUrl;
                
                // Fetch form content when modal is shown
                modal.addEventListener('show.bs.modal', async () => {
                    try {
                        const response = await fetch(formUrl);
                        if (!response.ok) throw new Error('Failed to fetch form');
                        
                        const html = await response.text();
                        const wizard = modal.querySelector('.assessment-wizard');
                        if (wizard) {
                            wizard.innerHTML = html;
                            this.setupEventListeners();
                        }
                    } catch (error) {
                        console.error('Error loading form:', error);
                        modal.querySelector('.assessment-wizard').innerHTML = `
                            <div class="alert alert-danger">
                                Failed to load the assessment form. Please try again.
                            </div>
                        `;
                    }
                });
            },

            setupEventListeners: function() {
                const form = document.getElementById('aiAssessmentForm');
                if (!form) return;

                // Handle next button clicks
                document.querySelectorAll('.btn-next').forEach(button => {
                    button.addEventListener('click', () => {
                        if (validateSection(currentSection)) {
                            document.getElementById(`section${currentSection}`).style.display = 'none';
                            currentSection++;
                            document.getElementById(`section${currentSection}`).style.display = 'block';
                            updateProgressBar();
                        }
                    });
                });

                // Handle previous button clicks
                document.querySelectorAll('.btn-prev').forEach(button => {
                    button.addEventListener('click', () => {
                        document.getElementById(`section${currentSection}`).style.display = 'none';
                        currentSection--;
                        document.getElementById(`section${currentSection}`).style.display = 'block';
                        updateProgressBar();
                    });
                });

                // Handle form submission
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    if (!validateSection(currentSection)) return;

                    const formData = new FormData(form);
                    try {
                        const response = await fetch(form.action, {
                            method: 'POST',
                            body: formData,
                            headers: {
                                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                            }
                        });

                        if (!response.ok) throw new Error('Submission failed');
                        
                        const result = await response.json();
                        if (result.success) {
                            // Show success message and close modal
                            const modal = document.getElementById('aiAssessmentModal');
                            if (modal) {
                                const bsModal = bootstrap.Modal.getInstance(modal);
                                if (bsModal) bsModal.hide();
                            }
                            // Reload page to show updated assessment
                            window.location.reload();
                        } else {
                            throw new Error(result.message || 'Submission failed');
                        }
                    } catch (error) {
                        console.error('Error submitting form:', error);
                        const errorAlert = document.createElement('div');
                        errorAlert.className = 'alert alert-danger mt-3';
                        errorAlert.textContent = 'Failed to submit the assessment. Please try again.';
                        form.appendChild(errorAlert);
                    }
                });
            }
        };
    }

    return {
        getInstance: function() {
            if (!instance) {
                instance = createInstance();
            }
            return instance;
        }
    };
})();

// Initialize form when document is ready
document.addEventListener('DOMContentLoaded', () => {
    const form = AIAssessmentForm.getInstance();
    form.init();
}); 