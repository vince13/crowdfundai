// Notifications handling
class NotificationManager {
    constructor() {
        this.eventSource = null;
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryInterval = 5000; // 5 seconds
        
        // Only initialize if we're not on login/admin pages and user is authenticated
        if (this.shouldInitializeSSE()) {
            this.initializeSSE();
        }
        this.setupUI();
        this.unreadCount = 0;
        this.notificationList = [];
        
        // Create toast container on initialization
        this.createToastContainer();
    }

    shouldInitializeSSE() {
        // Don't initialize on login, register, password reset pages
        const excludedPaths = ['/login/', '/register/', '/password/reset/', '/admin/'];
        const currentPath = window.location.pathname;
        
        return !excludedPaths.some(path => currentPath.includes(path));
    }

    initializeSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        try {
            this.eventSource = new EventSource('/notifications/stream/');
        
        this.eventSource.onopen = () => {
            console.log('SSE connection established');
                this.retryCount = 0; // Reset retry count on successful connection
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                    this.handleNotification(data);
                } catch (error) {
                    console.error('Error parsing notification:', error);
                }
            };

            this.eventSource.onerror = (error) => {
                // Check if the error is due to authentication
                if (error.target.readyState === EventSource.CLOSED) {
                    // If we get a 401/403, redirect to login
                    if (error.target.status === 401 || error.target.status === 403) {
                            window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
                        return;
                    }
                }

            console.error('SSE connection error:', error);
            if (!this.shouldInitializeSSE()) {
                return;
            }
            this.handleConnectionError();
        };
        } catch (error) {
            console.error('Error initializing SSE:', error);
        }
    }

    handleConnectionError() {
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            console.log(`Retrying connection (${this.retryCount}/${this.maxRetries})...`);
            setTimeout(() => this.initializeSSE(), this.retryInterval);
        } else {
            console.error('Max retry attempts reached');
            // Optionally show an error message to the user
            this.showErrorMessage('Unable to establish notification connection. Please refresh the page.');
        }
    }

    handleNotification(data) {
        // Create notification element
        const notificationElement = this.createNotificationElement(data);
        
        // Add to notification container
        const container = document.getElementById('notification-container');
        if (container) {
            container.insertBefore(notificationElement, container.firstChild);
            
            // Update unread count
            this.updateUnreadCount();
            
            // Show toast notification
            this.showToast(data);
        }
    }

    createNotificationElement(data) {
        const div = document.createElement('div');
        div.className = 'notification-item' + (data.is_read ? '' : ' unread');
        div.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="flex-grow-1">
                    <h6 class="mb-1">${data.title}</h6>
                    <p class="mb-1">${data.message}</p>
                    <small class="text-muted">${data.created_at}</small>
                </div>
                <div class="ms-2">
                    <button class="btn btn-sm btn-link mark-read" data-id="${data.id}">
                        <i class="bi bi-check2-circle"></i>
                    </button>
                </div>
            </div>
        `;
        return div;
    }

    updateUnreadCount() {
        const unreadCount = document.querySelectorAll('.notification-item.unread').length;
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? 'inline' : 'none';
        }
    }

    createToastContainer() {
        // Check if container already exists
        if (!document.getElementById('notificationToastContainer')) {
            const container = document.createElement('div');
            container.id = 'notificationToastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1050';
            document.body.appendChild(container);
        }
    }

    showToast(data) {
        try {
            const container = document.getElementById('notificationToastContainer');
            if (!container) {
                this.createToastContainer();
            }

            const toastId = `toast-${Date.now()}`;
            const toast = document.createElement('div');
            toast.id = toastId;
            toast.className = 'toast';
            toast.setAttribute('role', 'alert');
            toast.setAttribute('aria-live', 'assertive');
            toast.setAttribute('aria-atomic', 'true');
            
            toast.innerHTML = `
                <div class="toast-header">
                    <strong class="me-auto">${data.title || 'Notification'}</strong>
                    <small class="text-muted">${this.formatTimestamp(data.timestamp || new Date())}</small>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${data.message}
                </div>
            `;
            
            document.getElementById('notificationToastContainer').appendChild(toast);
            
            // Initialize and show the toast
            const bsToast = new bootstrap.Toast(toast, {
                autohide: true,
                delay: 5000
            });
            bsToast.show();
            
            // Remove toast from DOM after it's hidden
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        } catch (error) {
            console.error('Error showing toast notification:', error);
        }
    }

    showErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            <strong>Error:</strong> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.insertBefore(errorDiv, document.body.firstChild);
    }

    setupUI() {
        // Set up UI event listeners
        document.addEventListener('click', (event) => {
            if (event.target.matches('[data-notification-id]')) {
                const notificationId = event.target.dataset.notificationId;
                this.markAsRead(notificationId);
            }
        });

        // Setup dropdown listener to load notifications
        const notificationDropdown = document.querySelector('.notification-dropdown');
        if (notificationDropdown) {
            notificationDropdown.addEventListener('show.bs.dropdown', () => {
                this.loadNotifications();
            });
        }
    }

    handleNotifications(notifications) {
        notifications.forEach(notification => {
            this.notificationList.unshift(notification);
            this.unreadCount++;
        });
        this.updateNotificationBadge();
        this.updateDropdownList();
    }

    updateNotificationBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = this.unreadCount;
            if (this.unreadCount > 0) {
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
        }
        }
    }

    loadNotifications() {
        const notificationList = document.getElementById('notification-list');
        if (!notificationList || this.notificationList.length === 0) return;

        notificationList.innerHTML = this.notificationList.map(notification => `
            <div class="dropdown-item notification-item" data-notification-id="${notification.id}">
                <div class="d-flex align-items-center">
                    <div class="flex-grow-1">
                        <p class="mb-1 text-wrap">${notification.message}</p>
                        <small class="text-muted">${this.formatTimestamp(notification.created_at)}</small>
                    </div>
                    ${!notification.is_read ? '<span class="badge bg-primary ms-2">New</span>' : ''}
                </div>
            </div>
        `).join('') || '<div class="dropdown-item">No new notifications</div>';
    }

    updateDropdownList() {
        const dropdown = document.querySelector('.notification-dropdown');
        if (dropdown && dropdown.classList.contains('show')) {
            this.loadNotifications();
        }
    }

    markAsRead(notificationId) {
        fetch(`/notifications/mark-read/${notificationId}/`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.getCsrfToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.unreadCount = Math.max(0, this.unreadCount - 1);
                this.updateNotificationBadge();
                
                // Update notification in list
                const notification = this.notificationList.find(n => n.id === notificationId);
                if (notification) {
                    notification.is_read = true;
                    this.updateDropdownList();
                }
            }
        })
        .catch(error => console.error('Error marking notification as read:', error));
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        // Less than 24 hours
        if (diff < 24 * 60 * 60 * 1000) {
            return date.toLocaleTimeString();
        }
        // Less than 7 days
        if (diff < 7 * 24 * 60 * 60 * 1000) {
            return date.toLocaleDateString();
        }
        return date.toLocaleDateString();
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    }
}

// Initialize notification manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
});