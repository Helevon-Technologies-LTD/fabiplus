/**
 * FABI+ Admin JavaScript
 * Enhanced functionality for the admin interface
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('FABI+ Admin interface loaded');
    
    // Initialize admin functionality
    initializeAdmin();
});

function initializeAdmin() {
    // Setup HTMX configuration
    setupHTMX();
    
    // Setup form enhancements
    setupForms();
    
    // Setup table enhancements
    setupTables();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Setup tooltips and popovers
    setupBootstrapComponents();
}

function setupHTMX() {
    // Configure HTMX for admin
    document.body.addEventListener('htmx:configRequest', function(evt) {
        // Add custom headers
        evt.detail.headers['X-Requested-With'] = 'XMLHttpRequest';
        evt.detail.headers['X-Admin-Request'] = 'true';
    });
    
    // Handle HTMX loading states
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        showLoadingState(evt.target);
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        hideLoadingState(evt.target);
        
        // Handle successful responses
        if (evt.detail.successful) {
            showSuccessMessage('Operation completed successfully');
        }
    });
    
    // Handle HTMX errors
    document.body.addEventListener('htmx:responseError', function(evt) {
        console.error('HTMX Error:', evt.detail);
        showErrorMessage('An error occurred. Please try again.');
    });
}

function setupForms() {
    // Auto-resize textareas
    document.querySelectorAll('textarea').forEach(textarea => {
        autoResizeTextarea(textarea);
        textarea.addEventListener('input', function() {
            autoResizeTextarea(this);
        });
    });
    
    // Form validation enhancements
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });
    
    // Real-time validation
    document.querySelectorAll('input[required], textarea[required], select[required]').forEach(field => {
        field.addEventListener('blur', function() {
            validateField(this);
        });
    });
}

function setupTables() {
    // Select all functionality
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const itemCheckboxes = document.querySelectorAll('input[name="selected_items"]');
            itemCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateBulkActionsVisibility();
        });
    }
    
    // Individual checkbox handling
    document.querySelectorAll('input[name="selected_items"]').forEach(checkbox => {
        checkbox.addEventListener('change', updateBulkActionsVisibility);
    });
    
    // Table row hover effects
    document.querySelectorAll('table tbody tr').forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+S to save forms
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const form = document.querySelector('form');
            if (form) {
                form.dispatchEvent(new Event('submit'));
            }
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal.show');
            if (modal) {
                const modalInstance = bootstrap.Modal.getInstance(modal);
                if (modalInstance) {
                    modalInstance.hide();
                }
            }
        }
        
        // Ctrl+N for new item (if on list page)
        if (e.ctrlKey && e.key === 'n') {
            const addButton = document.querySelector('a[href*="/add/"]');
            if (addButton) {
                e.preventDefault();
                window.location.href = addButton.href;
            }
        }
    });
}

function setupBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

// Utility functions
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!validateField(field)) {
            isValid = false;
        }
    });
    
    return isValid;
}

function validateField(field) {
    const value = field.value.trim();
    const isValid = value !== '';
    
    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
    }
    
    return isValid;
}

function updateBulkActionsVisibility() {
    const selectedCount = document.querySelectorAll('input[name="selected_items"]:checked').length;
    const bulkActionsContainer = document.getElementById('bulk-actions');
    
    if (bulkActionsContainer) {
        if (selectedCount > 0) {
            bulkActionsContainer.style.display = 'block';
            bulkActionsContainer.querySelector('.selected-count').textContent = selectedCount;
        } else {
            bulkActionsContainer.style.display = 'none';
        }
    }
    
    console.log(`${selectedCount} items selected`);
}

function showLoadingState(element) {
    if (element.tagName === 'BUTTON') {
        element.disabled = true;
        const originalText = element.innerHTML;
        element.dataset.originalText = originalText;
        element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    }
}

function hideLoadingState(element) {
    if (element.tagName === 'BUTTON' && element.dataset.originalText) {
        element.disabled = false;
        element.innerHTML = element.dataset.originalText;
        delete element.dataset.originalText;
    }
}

function showSuccessMessage(message) {
    showToast(message, 'success');
}

function showErrorMessage(message) {
    showToast(message, 'danger');
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    // Initialize and show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });
    
    toast.show();
    
    // Remove toast element after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Sidebar toggle for mobile
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('show');
    }
}

// Export functions for global use
window.adminUtils = {
    showSuccessMessage,
    showErrorMessage,
    showToast,
    toggleSidebar,
    validateForm,
    validateField
};
