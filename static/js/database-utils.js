document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const createBackupBtn = document.getElementById('createBackupBtn');
    const restoreForm = document.getElementById('restoreForm');
    const backupStatus = document.getElementById('backupStatus');
    const restoreStatus = document.getElementById('restoreStatus');
    const backupsList = document.getElementById('backupsList');
    const noBackupsMessage = document.getElementById('noBackupsMessage');
    const backupsListLoading = document.getElementById('backupsListLoading');
    const backupsListTab = document.getElementById('backups-list-tab');
    const settingsTab = document.getElementById('settings-tab');
    const settingsForm = document.getElementById('backupSettingsForm');
    const settingsStatus = document.getElementById('settingsStatus');
    const databaseUtilitiesModal = document.getElementById('databaseUtilitiesModal');
    
    // Flag to prevent multiple loading operations
    let isLoadingBackups = false;
    
    // Load backups list when the tab is clicked
    if (backupsListTab) {
        backupsListTab.addEventListener('shown.bs.tab', function() {
            loadBackupsList();
        });
        
        // Also load when the page loads if it's the active tab
        if (backupsListTab.classList.contains('active')) {
            loadBackupsList();
        }
    }
    
    // Load settings when the settings tab is clicked
    if (settingsTab) {
        settingsTab.addEventListener('shown.bs.tab', function() {
            loadSettings();
        });
        
        // Also load settings when the page loads if settings tab is active
        if (settingsTab.classList.contains('active')) {
            loadSettings();
        }
    }
    
    // Create backup
    if (createBackupBtn) {
        let isCreatingBackup = false; // Flag to prevent duplicate clicks
        
        createBackupBtn.addEventListener('click', function() {
            // Prevent multiple rapid clicks
            if (isCreatingBackup) {
                console.log("Backup creation already in progress");
                return;
            }
            
            isCreatingBackup = true;
            createBackupBtn.disabled = true;
            backupStatus.innerHTML = '<div class="alert alert-info">Creating backup... Please wait.</div>';
            
            console.log("Sending backup request");
            
            fetch('/api/database/backup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                console.log("Received backup response", response);
                return response.json();
            })
            .then(data => {
                console.log("Backup response data:", data);
                if (data.success) {
                    backupStatus.innerHTML = `<div class="alert alert-success">
                        <strong>Success!</strong> ${data.message}
                    </div>`;
                    // Reload the backups list after a short delay to ensure the server has processed everything
                    setTimeout(() => {
                        if (backupsList) {
                            loadBackupsList();
                        }
                    }, 1000);
                } else {
                    backupStatus.innerHTML = `<div class="alert alert-danger">
                        <strong>Error!</strong> ${data.message || data.error || 'Unknown error'}
                    </div>`;
                }
                
                createBackupBtn.disabled = false;
                isCreatingBackup = false;
            })
            .catch(error => {
                console.error("Backup error:", error);
                backupStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> ${error.message || 'Failed to create backup'}
                </div>`;
                createBackupBtn.disabled = false;
                isCreatingBackup = false;
            });
        });
    }
    
    // Restore database
    if (restoreForm) {
        restoreForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!confirm('WARNING: This will replace all current data with the backup file. This action cannot be undone. Are you sure you want to continue?')) {
                return;
            }
            
            const fileInput = document.getElementById('backupFile');
            const file = fileInput.files[0];
            
            if (!file) {
                restoreStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> Please select a backup file.
                </div>`;
                return;
            }
            
            const formData = new FormData();
            formData.append('backup_file', file);
            
            restoreStatus.innerHTML = '<div class="alert alert-info">Restoring database... Please wait.</div>';
            
            fetch('/api/database/restore', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    restoreStatus.innerHTML = `<div class="alert alert-success">
                        <strong>Success!</strong> ${data.message}
                    </div>`;
                } else {
                    restoreStatus.innerHTML = `<div class="alert alert-danger">
                        <strong>Error!</strong> ${data.message || data.error || 'Unknown error'}
                    </div>`;
                }
            })
            .catch(error => {
                restoreStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> ${error.message || 'Failed to restore database'}
                </div>`;
            });
        });
    }
    
    // Settings form
    if (settingsForm) {
        settingsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const autoBackupEnabled = document.getElementById('autoBackupEnabled').checked;
            const autoBackupKeepCount = document.getElementById('autoBackupKeepCount').value;
            
            // Validate inputs
            if (!autoBackupKeepCount || autoBackupKeepCount < 1) {
                settingsStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> Please enter a valid number of backups to keep (minimum 1).
                </div>`;
                return;
            }
            
            // Prepare settings data
            const settings = {
                auto_backup_enabled: autoBackupEnabled,
                auto_backup_keep_count: autoBackupKeepCount
            };
            
            // Update settings via API
            settingsStatus.innerHTML = '<div class="alert alert-info">Saving settings... Please wait.</div>';
            
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                    settingsStatus.innerHTML = `<div class="alert alert-success">
                        <strong>Success!</strong> Settings saved successfully.
                    </div>`;
                } else {
                    settingsStatus.innerHTML = `<div class="alert alert-danger">
                        <strong>Error!</strong> ${data.message || data.error || 'Unknown error'}
                    </div>`;
                }
            })
            .catch(error => {
                settingsStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> ${error.message || 'Failed to save settings'}
                </div>`;
            });
        });
    }
    
    // Load settings from API
    function loadSettings() {
        const autoBackupEnabled = document.getElementById('autoBackupEnabled');
        const autoBackupKeepCount = document.getElementById('autoBackupKeepCount');
        
        if (!autoBackupEnabled || !autoBackupKeepCount) {
            return;
        }
        
        settingsStatus.innerHTML = '<div class="alert alert-info">Loading settings... Please wait.</div>';
        
        fetch('/api/settings?keys=auto_backup_enabled,auto_backup_keep_count')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.settings) {
                // Clear previous status
                settingsStatus.innerHTML = '';
                
                // Update form values
                if (data.settings.auto_backup_enabled) {
                    autoBackupEnabled.checked = data.settings.auto_backup_enabled.value;
                }
                
                if (data.settings.auto_backup_keep_count) {
                    autoBackupKeepCount.value = data.settings.auto_backup_keep_count.value;
                }
                    } else {
                settingsStatus.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> ${data.message || data.error || 'Failed to load settings'}
                </div>`;
                    }
                })
                .catch(error => {
            settingsStatus.innerHTML = `<div class="alert alert-danger">
                <strong>Error!</strong> ${error.message || 'Failed to load settings'}
            </div>`;
        });
    }
    
    // Load backups list
    function loadBackupsList() {
        if (isLoadingBackups) return; // Prevent multiple calls
        isLoadingBackups = true;
        
        if (!backupsList || !backupsListLoading || !noBackupsMessage) {
            isLoadingBackups = false;
            return;
        }
        
        backupsListLoading.style.display = "block";
        backupsList.innerHTML = ""; // Clear the list before loading
        noBackupsMessage.style.display = "none";
        
        fetch('/api/database/backups')
        .then(response => response.json())
        .then(data => {
            backupsListLoading.style.display = "none";
            console.log("Raw backups data:", data);
            
            if (data.success && data.backups && data.backups.length > 0) {
                // Clear any existing content before rendering
                backupsList.innerHTML = "";
                
                // Render each backup directly from the server data
                // (Server guarantees uniqueness, so no need to check here)
                data.backups.forEach(backup => {
                    const fileSize = formatFileSize(backup.size);
                    const backupDate = new Date(backup.modified).toLocaleString();
                    
                    const item = document.createElement("div");
                    item.className = "list-group-item d-flex justify-content-between align-items-center";
                    item.innerHTML = `
                        <div>
                            <h6 class="mb-1">${backup.filename}</h6>
                            <p class="mb-1 text-muted small">Created: ${backupDate}</p>
                            <p class="mb-0 text-muted small">Size: ${fileSize}</p>
                        </div>
                        <div class="btn-group">
                            <a href="${backup.download_url}" class="btn btn-sm btn-primary me-2">
                                <i class="fas fa-download"></i> Download
                            </a>
                            <button class="btn btn-sm btn-warning restore-backup-btn me-2" data-filename="${backup.filename}">
                                <i class="fas fa-upload"></i> Restore
                            </button>
                            <button class="btn btn-sm btn-danger delete-backup-btn" data-filename="${backup.filename}">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </div>
                    `;
                    backupsList.appendChild(item);
                });
                
                // Add event listeners to restore buttons
                document.querySelectorAll('.restore-backup-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const filename = this.getAttribute('data-filename');
                        if (confirm(`WARNING: This will replace all current data with the backup "${filename}". This action cannot be undone. Are you sure you want to continue?`)) {
                            restoreFromBackup(filename);
                        }
                    });
                });
                
                // Add event listeners to delete buttons
                document.querySelectorAll('.delete-backup-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const filename = this.getAttribute('data-filename');
                        if (confirm(`Are you sure you want to delete the backup "${filename}"? This action cannot be undone.`)) {
                            deleteBackup(filename);
                        }
                    });
                });
                
                noBackupsMessage.style.display = "none";
            } else {
                noBackupsMessage.style.display = "block";
            }
            isLoadingBackups = false;
        })
        .catch(error => {
            backupsListLoading.style.display = "none";
            isLoadingBackups = false;
            backupsList.innerHTML = `<div class="alert alert-danger">
                <strong>Error!</strong> Failed to load backups: ${error.message || 'Unknown error'}
            </div>`;
        });
    }
    
    // Function to restore from existing backup
    function restoreFromBackup(filename) {
        backupsList.innerHTML = `<div class="alert alert-info">
            Restoring from backup "${filename}"... Please wait. This may take a while.
        </div>`;
        
        fetch('/api/database/restore-from-backup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                backupsList.innerHTML = `<div class="alert alert-success">
                    <strong>Success!</strong> ${data.message || 'Database restored successfully.'}
                    <div class="mt-2">The application will need to be restarted to apply the changes.</div>
                </div>`;
            } else {
                loadBackupsList(); // Reload the list
                alert(`Error: ${data.error || data.message || 'Failed to restore database.'}`);
            }
        })
        .catch(error => {
            loadBackupsList(); // Reload the list
            alert(`Error: ${error.message || 'An unexpected error occurred.'}`);
        });
    }
    
    // Function to delete a backup
    function deleteBackup(filename) {
        backupsList.innerHTML = `<div class="alert alert-info">
            Deleting backup "${filename}"... Please wait.
        </div>`;
        
        fetch('/api/database/delete-backup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadBackupsList(); // Reload the list
            } else {
                backupsList.innerHTML = `<div class="alert alert-danger">
                    <strong>Error!</strong> ${data.error || data.message || 'Failed to delete backup.'}
                </div>`;
                setTimeout(loadBackupsList, 3000); // Reload list after 3 seconds
            }
        })
        .catch(error => {
            backupsList.innerHTML = `<div class="alert alert-danger">
                <strong>Error!</strong> ${error.message || 'An unexpected error occurred.'}
            </div>`;
            setTimeout(loadBackupsList, 3000); // Reload list after 3 seconds
        });
    }
    
    // Helper function to format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});
