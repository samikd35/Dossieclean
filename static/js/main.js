/**
 * DossieClean Main JavaScript
 * Handles theme switching and interactive elements
 */

document.addEventListener('DOMContentLoaded', function() {
    // Theme switching functionality
    initThemeSwitch();
    
    // File input enhancement
    initFileInputs();
});

/**
 * Initialize theme switching functionality
 */
function initThemeSwitch() {
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    // Set initial theme
    if (currentTheme === 'dark') {
        document.body.classList.add('dark-theme');
        document.body.classList.remove('light-theme');
    } else {
        document.body.classList.add('light-theme');
        document.body.classList.remove('dark-theme');
    }
    
    // Toggle theme on button click
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            if (document.body.classList.contains('dark-theme')) {
                document.body.classList.remove('dark-theme');
                document.body.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
                console.log('Switched to light theme');
            } else {
                document.body.classList.remove('light-theme');
                document.body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark');
                console.log('Switched to dark theme');
            }
        });
    }
}

/**
 * Enhance file input fields with custom styling
 */
function initFileInputs() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        const fileNameElement = document.getElementById('file-name');
        
        if (input && fileNameElement) {
            input.addEventListener('change', function(e) {
                const fileName = e.target.files[0]?.name || 'No file selected';
                fileNameElement.textContent = fileName;
            });
        }
    });
}

/**
 * Show loading indicator for form submissions
 */
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitButtons = this.querySelectorAll('button[type="submit"]');
            
            submitButtons.forEach(button => {
                const originalText = button.innerHTML;
                button.disabled = true;
                button.innerHTML = '<span class="spinner"></span> Processing...';
                
                // Store original text for restoration if needed
                button.dataset.originalText = originalText;
            });
        });
    });
});

/**
 * Initialize charts on dashboard if Chart.js is loaded
 */
function initCharts() {
    if (typeof Chart !== 'undefined') {
        // Charts are initialized in the templates where needed
        console.log('Chart.js is available for use');
    }
}

/**
 * Format file sizes in human-readable format
 * @param {number} bytes - Size in bytes
 * @returns {string} - Formatted size with units
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}




