/**
 * Help Documentation Screenshot Helper
 * 
 * This script guides users through capturing all necessary screenshots
 * for the help documentation. It creates a floating panel with instructions
 * and highlights areas that need to be captured.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Only run on the help page or when explicitly enabled
    if (!window.location.pathname.includes('/help') && !localStorage.getItem('screenshotHelperEnabled')) {
        return;
    }

    // Create the UI components
    createScreenshotHelper();

    // Initialize the helper
    initializeScreenshotHelper();
});

/**
 * Create the screenshot helper UI
 */
function createScreenshotHelper() {
    // Create helper container
    const helperContainer = document.createElement('div');
    helperContainer.id = 'screenshot-helper';
    helperContainer.className = 'screenshot-helper';
    helperContainer.innerHTML = `
        <div class="screenshot-helper-header">
            <h4>Screenshot Helper</h4>
            <button id="close-helper" class="btn-close"></button>
        </div>
        <div class="screenshot-helper-body">
            <div id="screenshot-instructions"></div>
            <div id="screenshot-progress" class="progress mt-3 mb-3">
                <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
            </div>
            <div class="screenshot-controls">
                <button id="prev-screenshot" class="btn btn-sm btn-secondary">Previous</button>
                <span id="screenshot-counter">1 of 10</span>
                <button id="next-screenshot" class="btn btn-sm btn-primary">Next</button>
            </div>
        </div>
    `;

    // Add styles
    const styles = document.createElement('style');
    styles.textContent = `
        .screenshot-helper {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 350px;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
            transition: all 0.3s ease;
            overflow: hidden;
        }
        
        .dark-mode .screenshot-helper {
            background-color: #2d3748;
            color: #f0f0f0;
        }
        
        .screenshot-helper-header {
            padding: 10px 15px;
            background: linear-gradient(135deg, var(--primary-color, #4e73df) 0%, var(--primary-color-dark, #224abe) 100%);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .screenshot-helper-header h4 {
            margin: 0;
            font-size: 16px;
        }
        
        .screenshot-helper-body {
            padding: 15px;
        }
        
        #screenshot-instructions {
            min-height: 120px;
        }
        
        .screenshot-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .highlight-element {
            outline: 3px dashed #ff5722 !important;
            position: relative;
            z-index: 999 !important;
            box-shadow: 0 0 10px rgba(255, 87, 34, 0.5);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { outline-color: #ff5722; }
            50% { outline-color: #ffeb3b; }
            100% { outline-color: #ff5722; }
        }
    `;

    // Add to document
    document.body.appendChild(styles);
    document.body.appendChild(helperContainer);

    // Event listeners
    document.getElementById('close-helper').addEventListener('click', function() {
        helperContainer.style.display = 'none';
        localStorage.setItem('screenshotHelperEnabled', 'false');
        removeAllHighlights();
    });

    document.getElementById('prev-screenshot').addEventListener('click', function() {
        navigateScreenshot(-1);
    });

    document.getElementById('next-screenshot').addEventListener('click', function() {
        navigateScreenshot(1);
    });
}

/**
 * Initialize the screenshot helper with instructions
 */
function initializeScreenshotHelper() {
    // Define all screenshots needed
    window.screenshotSteps = [
        {
            id: 1,
            name: 'dashboard_overview',
            title: 'Dashboard Overview',
            instructions: 'Take a screenshot of the main dashboard showing overview and statistics. Navigate to the Dashboard first.',
            targetPath: '/dashboard',
            selector: '.dashboard-container',
            highlight: true
        },
        {
            id: 2,
            name: 'sidebar_navigation',
            title: 'Sidebar Navigation',
            instructions: 'Capture the sidebar navigation menu. Make sure the full sidebar is visible.',
            selector: '.sidebar',
            highlight: true
        },
        {
            id: 3,
            name: 'new_project_form',
            title: 'New Project Form',
            instructions: 'Navigate to the New Project page and take a screenshot of the form.',
            targetPath: '/new-project',
            selector: 'form',
            highlight: true
        },
        {
            id: 4,
            name: 'new_letter_form',
            title: 'New Letter Form',
            instructions: 'Navigate to the New Letter page and take a screenshot of the form.',
            targetPath: '/new-letter',
            selector: 'form',
            highlight: true
        },
        {
            id: 5,
            name: 'letter_numbering',
            title: 'Letter Numbering Fields',
            instructions: 'Take a screenshot of the letter numbering fields in the New Letter form. Focus on the H.O. Number and Project Number fields.',
            targetPath: '/new-letter',
            selector: '.numbering-fields', 
            highlight: true
        },
        {
            id: 6,
            name: 'database_backup',
            title: 'Database Backup Interface',
            instructions: 'Navigate to Utilities and take a screenshot of the backup creation tab.',
            targetPath: '/database-utilities',
            selector: '#backup-tab-content',
            highlight: true
        },
        {
            id: 7,
            name: 'database_restore',
            title: 'Database Restore Interface',
            instructions: 'Navigate to Utilities and take a screenshot of the restore database tab.',
            targetPath: '/database-utilities',
            selector: '#restore-tab-content',
            highlight: true
        },
        {
            id: 8,
            name: 'light_mode',
            title: 'Light Mode',
            instructions: 'Ensure you are in light mode and take a screenshot of the main interface.',
            selector: 'main',
            highlight: true,
            prep: function() {
                // Make sure light mode is active
                if (document.body.classList.contains('dark-mode')) {
                    document.querySelector('.dark-mode-toggle').click();
                }
            }
        },
        {
            id: 9,
            name: 'dark_mode',
            title: 'Dark Mode',
            instructions: 'Switch to dark mode and take a screenshot of the same area as the previous step.',
            selector: 'main',
            highlight: true,
            prep: function() {
                // Make sure dark mode is active
                if (!document.body.classList.contains('dark-mode')) {
                    document.querySelector('.dark-mode-toggle').click();
                }
            }
        },
        {
            id: 10,
            name: 'notifications_panel',
            title: 'Notifications Panel',
            instructions: 'Click the notifications bell icon and take a screenshot of the dropdown.',
            selector: '.notification-dropdown.show',
            highlight: true,
            prep: function() {
                document.querySelector('.notification-bell').click();
            }
        }
    ];

    // Set current step
    window.currentScreenshotStep = 0;
    updateScreenshotHelper();
}

/**
 * Navigate between screenshot steps
 * @param {number} direction 1 for next, -1 for previous
 */
function navigateScreenshot(direction) {
    // Remove current highlights
    removeAllHighlights();
    
    // Update step
    window.currentScreenshotStep += direction;
    
    // Ensure within bounds
    if (window.currentScreenshotStep < 0) {
        window.currentScreenshotStep = 0;
    } else if (window.currentScreenshotStep >= window.screenshotSteps.length) {
        window.currentScreenshotStep = window.screenshotSteps.length - 1;
    }
    
    // Update UI
    updateScreenshotHelper();
}

/**
 * Update the screenshot helper UI for current step
 */
function updateScreenshotHelper() {
    const step = window.screenshotSteps[window.currentScreenshotStep];
    const instructionsEl = document.getElementById('screenshot-instructions');
    const counterEl = document.getElementById('screenshot-counter');
    const progressBar = document.querySelector('#screenshot-progress .progress-bar');
    
    // Update UI
    instructionsEl.innerHTML = `
        <h5>${step.title}</h5>
        <p>${step.instructions}</p>
        <div class="text-muted small">
            <strong>File name:</strong> ${step.name}.png<br>
            <strong>Save to:</strong> /static/images/help/
        </div>
    `;
    
    counterEl.textContent = `${window.currentScreenshotStep + 1} of ${window.screenshotSteps.length}`;
    
    const progress = ((window.currentScreenshotStep + 1) / window.screenshotSteps.length) * 100;
    progressBar.style.width = `${progress}%`;
    progressBar.textContent = `${Math.round(progress)}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    
    // Navigate to target page if specified
    if (step.targetPath && window.location.pathname !== step.targetPath) {
        alert(`Please navigate to ${step.targetPath} for this screenshot.`);
    }
    
    // Run prep function if exists
    if (typeof step.prep === 'function') {
        setTimeout(step.prep, 300);
    }
    
    // Highlight target element
    if (step.highlight && step.selector) {
        setTimeout(function() {
            highlightElement(step.selector);
        }, 500);
    }
}

/**
 * Highlight an element on the page
 * @param {string} selector CSS selector for the element
 */
function highlightElement(selector) {
    removeAllHighlights();
    const element = document.querySelector(selector);
    if (element) {
        element.classList.add('highlight-element');
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Remove all highlights from the page
 */
function removeAllHighlights() {
    document.querySelectorAll('.highlight-element').forEach(el => {
        el.classList.remove('highlight-element');
    });
}

// Create a toggle button to enable/disable the helper
function createToggleButton() {
    const toggleButton = document.createElement('button');
    toggleButton.id = 'toggle-screenshot-helper';
    toggleButton.className = 'btn btn-sm btn-primary fixed-bottom m-3';
    toggleButton.style.left = 'auto';
    toggleButton.style.right = '20px';
    toggleButton.innerHTML = '<i class="fas fa-camera me-2"></i> Toggle Screenshot Helper';
    
    toggleButton.addEventListener('click', function() {
        const helper = document.getElementById('screenshot-helper');
        if (helper) {
            if (helper.style.display === 'none') {
                helper.style.display = 'block';
                localStorage.setItem('screenshotHelperEnabled', 'true');
            } else {
                helper.style.display = 'none';
                localStorage.setItem('screenshotHelperEnabled', 'false');
            }
        } else {
            localStorage.setItem('screenshotHelperEnabled', 'true');
            location.reload();
        }
    });
    
    document.body.appendChild(toggleButton);
}

// Initialize toggle button
setTimeout(createToggleButton, 1000); 