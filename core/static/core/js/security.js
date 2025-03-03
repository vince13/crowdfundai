// Security Dashboard functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Auto-refresh data every 30 seconds
    setInterval(refreshSecurityData, 30000);
});

function refreshSecurityData() {
    fetch('/administration/security/data/')
        .then(response => response.json())
        .then(data => {
            updateDashboard(data);
        })
        .catch(error => console.error('Error refreshing security data:', error));
}

function updateDashboard(data) {
    // Update statistics
    document.querySelectorAll('[data-stat]').forEach(element => {
        const stat = element.dataset.stat;
        if (data.stats && data.stats[stat] !== undefined) {
            element.textContent = data.stats[stat];
        }
    });

    // Update recent activity if new data is available
    if (data.recent_logs) {
        const tbody = document.querySelector('#recent-activity tbody');
        if (tbody) {
            tbody.innerHTML = data.recent_logs.map(log => `
                <tr>
                    <td>${new Date(log.timestamp).toLocaleString()}</td>
                    <td>${log.user || 'Anonymous'}</td>
                    <td>${log.action}</td>
                    <td>
                        <span class="badge bg-${log.status === 'success' ? 'success' : 'danger'}">
                            ${log.status}
                        </span>
                    </td>
                </tr>
            `).join('');
        }
    }
} 