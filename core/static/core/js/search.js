document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.querySelector('.search-form');
    const searchInput = searchForm.querySelector('input[name="q"]');
    const suggestionsContainer = document.getElementById('search-suggestions');
    
    // Handle suggestion clicks
    suggestionsContainer.addEventListener('click', function(e) {
        const suggestion = e.target.closest('.suggestion-item');
        if (suggestion) {
            searchInput.value = suggestion.dataset.value;
            searchForm.submit();
        }
    });
    
    // Close suggestions on click outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            suggestionsContainer.innerHTML = '';
        }
    });
    
    // Handle form submission with filters
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(searchForm);
        const params = new URLSearchParams(formData);
        
        // Remove empty parameters
        for (const [key, value] of params.entries()) {
            if (!value) {
                params.delete(key);
            }
        }
        
        window.location.href = `${searchForm.action}?${params.toString()}`;
    });
}); 