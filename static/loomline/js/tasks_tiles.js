document.addEventListener('DOMContentLoaded', function() {
    // View Toggle
    const tileViewBtn = document.getElementById('tileView');
    const listViewBtn = document.getElementById('listView');
    const taskTiles = document.getElementById('taskTiles');
    const taskList = document.getElementById('taskList');

    if (tileViewBtn && listViewBtn && taskTiles && taskList) {
        tileViewBtn.addEventListener('change', function() {
            if (this.checked) {
                taskTiles.style.display = 'flex';
                taskList.style.display = 'none';
            }
        });

        listViewBtn.addEventListener('change', function() {
            if (this.checked) {
                taskTiles.style.display = 'none';
                taskList.style.display = 'block';
            }
        });
    }

    // Search Functionality
    const searchInput = document.getElementById('searchInput');
    const clearSearch = document.getElementById('clearSearch');
    const timelineItems = document.querySelectorAll('.timeline-item');

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase().trim();

            if (searchTerm) {
                clearSearch.style.display = 'block';
            } else {
                clearSearch.style.display = 'none';
            }

            timelineItems.forEach(item => {
                const searchText = item.dataset.searchText || '';
                if (searchText.includes(searchTerm)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    if (clearSearch) {
        clearSearch.addEventListener('click', function() {
            searchInput.value = '';
            this.style.display = 'none';
            timelineItems.forEach(item => {
                item.style.display = 'flex';
            });
            searchInput.focus();
        });
    }

    // Filter Modal
    const filterForm = document.getElementById('filterForm');
    const resetFilters = document.getElementById('resetFilters');
    const filterCount = document.getElementById('filterCount');

    function updateFilterCount() {
        const selects = filterForm.querySelectorAll('select');
        let count = 0;
        selects.forEach(select => {
            if (select.value) count++;
        });

        if (count > 0) {
            filterCount.textContent = count;
            filterCount.style.display = 'inline';
        } else {
            filterCount.style.display = 'none';
        }
    }

    if (filterForm) {
        updateFilterCount(); // Initial count

        filterForm.addEventListener('change', updateFilterCount);
    }

    if (resetFilters) {
        resetFilters.addEventListener('click', function() {
            filterForm.querySelectorAll('select').forEach(select => {
                select.value = '';
            });
            updateFilterCount();
        });
    }

    // Calculate and display time differences
    function calculateTimeDifferences() {
        const items = Array.from(timelineItems);
        console.log('Calculating time differences for', items.length, 'items');

        for (let i = 0; i < items.length - 1; i++) {
            const currentItem = items[i];
            const nextItem = items[i + 1];

            const currentDate = new Date(currentItem.dataset.completedAt);
            const nextDate = new Date(nextItem.dataset.completedAt);

            const diffMs = Math.abs(currentDate - nextDate);
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffDays = Math.floor(diffHours / 24);

            let timeDiffText = '';
            if (diffDays > 0) {
                timeDiffText = diffDays + ' Tag' + (diffDays > 1 ? 'e' : '');
            } else if (diffHours > 0) {
                timeDiffText = diffHours + ' Std.';
            } else {
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                timeDiffText = diffMinutes + ' Min.';
            }

            // Find connector after current item
            let nextSibling = currentItem.nextElementSibling;
            while (nextSibling && !nextSibling.classList.contains('timeline-connector')) {
                nextSibling = nextSibling.nextElementSibling;
            }

            if (nextSibling && nextSibling.classList.contains('timeline-connector')) {
                const badge = nextSibling.querySelector('.timeline-badge');
                if (badge) {
                    badge.setAttribute('title', timeDiffText);
                    badge.innerHTML = '<span class="time-diff">' + timeDiffText + '</span>';
                    console.log('Set time diff:', timeDiffText, 'for connector after item', i);
                }
            }
        }
    }

    // Call after DOM is ready
    setTimeout(calculateTimeDifferences, 100);

    // Task Tile Click Handler - Updated for flip containers with proper button handling
    document.querySelectorAll('.task-tile').forEach(tile => {
        // Allow flip animation but preserve button functionality
        tile.addEventListener('click', function(e) {
            // Don't interfere if clicking on buttons
            if (e.target.closest('.add-subtask-btn, .add-subtask-btn-back, .task-edit-btn-back, .task-delete-btn-back')) {
                e.stopPropagation();
                return; // Let button handlers work
            }
            // Prevent other click behaviors to allow flip animation
            e.preventDefault();
        });

        // Double-click functionality for main task tiles
        tile.addEventListener('dblclick', function(e) {
            // Don't interfere if clicking on buttons
            if (e.target.closest('.add-subtask-btn, .add-subtask-btn-back, .task-edit-btn-back, .task-delete-btn-back')) {
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            console.log('Main task tile double-clicked!');

            // Extract task data from the front side
            const taskFront = this.querySelector('.task-front');
            const taskTitle = taskFront.querySelector('.task-title').textContent.trim();
            const taskDescription = 'Beschreibung aus Rückseite'; // Will be extracted later
            const taskId = taskFront.querySelector('.add-subtask-btn').dataset.taskId;
            const taskUser = taskFront.querySelector('.task-user').textContent.trim();
            const taskDate = taskFront.querySelector('.task-date').textContent.trim();

            // Fill modal with task data
            document.getElementById('taskEditTitle').textContent = taskTitle;
            document.getElementById('taskEditDescription').textContent = taskDescription;
            document.getElementById('taskEditMeta').textContent = taskDate + ' • ' + taskUser;

            // Store task ID for actions
            document.getElementById('deleteTaskFromModalBtn').dataset.taskId = taskId;
            document.getElementById('deleteTaskFromModalBtn').dataset.taskTitle = taskTitle;

            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('taskEditModal'));
            modal.show();
        });
    });

    // Debug: Check if tooltips exist
    console.log('Found tooltips:', document.querySelectorAll('.task-tooltip').length);
    console.log('Found tiles:', document.querySelectorAll('.task-tile').length);

    // Quick Add Modal Form Handling
    const quickAddForm = document.getElementById('quickAddForm');
    if (quickAddForm) {
        quickAddForm.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Wird gespeichert...';
                submitBtn.disabled = true;
            }
        });
    }

    // Auto-focus on modal open
    const quickAddModal = document.getElementById('quickAddModal');
    if (quickAddModal) {
        quickAddModal.addEventListener('shown.bs.modal', function() {
            const titleInput = this.querySelector('input[name="title"]');
            if (titleInput) {
                titleInput.focus();
            }
        });

        // Reset form on modal close
        quickAddModal.addEventListener('hidden.bs.modal', function() {
            const form = this.querySelector('form');
            if (form) {
                form.reset();
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<i class="fas fa-check me-2"></i>Aufgabe hinzufügen';
                    submitBtn.disabled = false;
                }
            }
        });
    }

    // Sub-Aufgaben Modal Handling
    const addSubtaskModal = document.getElementById('addSubtaskModal');
    if (addSubtaskModal) {
        // Handle subtask button clicks with improved event handling
        function attachSubtaskHandlers() {
            document.querySelectorAll('.add-subtask-btn, .add-subtask-btn-back').forEach(btn => {
                btn.removeEventListener('click', handleSubtaskClick);
                btn.addEventListener('click', handleSubtaskClick);
            });
        }

        function handleSubtaskClick(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            console.log('Add subtask button clicked:', this.dataset.taskId);

            const taskId = this.dataset.taskId;
            const taskTitle = this.dataset.taskTitle;

            // Set parent task info in modal
            const parentTaskIdElement = document.getElementById('parentTaskId');
            const parentTaskTitleElement = document.getElementById('parentTaskTitle');

            if (parentTaskIdElement) parentTaskIdElement.value = taskId;
            if (parentTaskTitleElement) parentTaskTitleElement.textContent = taskTitle;
        }

        attachSubtaskHandlers();

        // Auto-focus on modal open
        addSubtaskModal.addEventListener('shown.bs.modal', function() {
            const titleInput = this.querySelector('#subtaskTitleInput');
            if (titleInput) {
                titleInput.focus();
            }
        });

        // Reset form on modal close
        addSubtaskModal.addEventListener('hidden.bs.modal', function() {
            const form = this.querySelector('form');
            if (form) {
                form.reset();
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<i class="fas fa-check me-2"></i>Sub-Aufgabe hinzufügen';
                    submitBtn.disabled = false;
                }
            }
        });

        // Form submission handling
        const addSubtaskForm = document.getElementById('addSubtaskForm');
        if (addSubtaskForm) {
            addSubtaskForm.addEventListener('submit', function(e) {
                const submitBtn = this.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Wird gespeichert...';
                    submitBtn.disabled = true;
                }
            });
        }
    }

    // Speech Recognition Functionality
    let recognition = null;
    let isListening = false;

    // Check if browser supports speech recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();

        recognition.continuous = false;
        recognition.interimResults = true; // Enable interim results for live preview
        recognition.lang = 'de-DE'; // German language

        recognition.onstart = function() {
            isListening = true;
            document.querySelectorAll('.speech-btn-inside.listening, .speech-btn.listening').forEach(btn => {
                btn.querySelector('i').className = 'fas fa-stop';
            });
        };

        recognition.onresult = function(event) {
            const listeningBtn = document.querySelector('.speech-btn-inside.listening, .speech-btn.listening');
            const targetId = listeningBtn ? listeningBtn.dataset.target : null;
            const targetInput = document.getElementById(targetId);

            if (targetInput) {
                let finalTranscript = '';
                let interimTranscript = '';

                // Process all results
                for (let i = 0; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interimTranscript += transcript;
                    }
                }

                // Get the original text before speech recognition started
                const originalText = targetInput.dataset.originalText || '';

                // Store original text on first interim result
                if (!targetInput.dataset.originalText) {
                    targetInput.dataset.originalText = targetInput.value;
                }

                // Combine original text with final and interim results
                let displayText = originalText;
                if (finalTranscript) {
                    displayText = displayText ? displayText + ' ' + finalTranscript : finalTranscript;
                    // Update original text with final result
                    targetInput.dataset.originalText = displayText;
                }
                if (interimTranscript) {
                    displayText = displayText ? displayText + ' ' + interimTranscript : interimTranscript;
                }

                // Update the input field
                targetInput.value = displayText;

                // Add visual feedback for interim results
                if (interimTranscript && !finalTranscript) {
                    targetInput.style.backgroundColor = '#fff3cd'; // Light yellow for interim
                } else {
                    targetInput.style.backgroundColor = ''; // Reset background
                }

                // Trigger input event for any listeners
                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            resetSpeechButton();
        };

        recognition.onend = function() {
            resetSpeechButton();
        };
    }

    function resetSpeechButton() {
        isListening = false;
        document.querySelectorAll('.speech-btn-inside, .speech-btn').forEach(btn => {
            btn.classList.remove('listening');
            btn.querySelector('i').className = 'fas fa-microphone';
            btn.disabled = false;

            // Reset input field styling and clear temporary data
            const targetId = btn.dataset.target;
            const targetInput = document.getElementById(targetId);
            if (targetInput) {
                targetInput.style.backgroundColor = '';
                delete targetInput.dataset.originalText;
            }
        });
    }

    // Add click handlers to speech buttons
    document.querySelectorAll('.speech-btn-inside, .speech-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!recognition) {
                alert('Spracherkennung wird von Ihrem Browser nicht unterstuetzt. Verwenden Sie Chrome, Edge oder Safari.');
                return;
            }

            if (isListening) {
                recognition.stop();
                return;
            }

            // Reset all buttons first
            resetSpeechButton();

            // Set this button as active
            this.classList.add('listening');
            this.querySelector('i').className = 'fas fa-microphone';
            this.disabled = true;

            // Start recognition
            try {
                recognition.start();
            } catch (error) {
                console.error('Error starting speech recognition:', error);
                resetSpeechButton();
                alert('Fehler beim Starten der Spracherkennung. Stellen Sie sicher, dass Sie die Mikrofon-Berechtigung erteilt haben.');
            }
        });
    });


    // Expand Button Click Handler
    document.querySelectorAll('.expand-btn').forEach(expandBtn => {
        expandBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            // Daten aus den data-Attributen extrahieren
            const title = this.getAttribute('data-title');
            const description = this.getAttribute('data-description');
            const date = this.getAttribute('data-date');
            const user = this.getAttribute('data-user');

            // Modal mit Daten füllen
            document.getElementById('subtaskModalTitle').textContent = title;
            document.getElementById('subtaskModalDescription').textContent = description;
            document.getElementById('subtaskModalMeta').textContent = date + ' • ' + user;

            // Modal anzeigen
            const modal = new bootstrap.Modal(document.getElementById('subtaskDescriptionModal'));
            modal.show();
        });
    });

    // Edit Task Button Handler for back buttons
    function attachEditHandlers() {
        document.querySelectorAll('.task-edit-btn-back').forEach(btn => {
            btn.removeEventListener('click', handleEditClick);
            btn.addEventListener('click', handleEditClick);
        });
    }

    function handleEditClick(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        const taskId = this.dataset.taskId;
        const taskTitle = this.dataset.taskTitle;
        const taskDescription = this.dataset.taskDescription || '';

        // Create and show edit modal
        showEditModal(taskId, taskTitle, taskDescription);
    }

    function showEditModal(taskId, taskTitle, taskDescription) {
        // Escape HTML attributes to prevent syntax errors
        const escapedTitle = taskTitle.replace(/\"/g, '&quot;').replace(/'/g, '&#x27;');
        const escapedDescription = taskDescription.replace(/</g, '&lt;').replace(/>/g, '&gt;');

        const editModalHtml = '<div class="modal fade" id="editTaskModalDirect" tabindex="-1">' +
            '<div class="modal-dialog">' +
                '<div class="modal-content">' +
                    '<div class="modal-header bg-warning text-white">' +
                        '<h5 class="modal-title">' +
                            '<i class="fas fa-edit me-2"></i>Aufgabe bearbeiten' +
                        '</h5>' +
                        '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>' +
                    '</div>' +
                    '<div class="modal-body">' +
                        '<form id="editTaskFormDirect">' +
                            '<div class="mb-3">' +
                                '<label class="form-label fw-bold">Titel</label>' +
                                '<input type="text" class="form-control" id="editTaskTitleDirect" value="' + escapedTitle + '" required>' +
                            '</div>' +
                            '<div class="mb-3">' +
                                '<label class="form-label fw-bold">Beschreibung</label>' +
                                '<textarea class="form-control" id="editTaskDescriptionDirect" rows="4">' + escapedDescription + '</textarea>' +
                            '</div>' +
                        '</form>' +
                    '</div>' +
                    '<div class="modal-footer">' +
                        '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>' +
                        '<button type="button" class="btn btn-warning" id="saveTaskChangesDirect">' +
                            '<i class="fas fa-save me-2"></i>Speichern' +
                        '</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</div>';

        // Remove existing modal if present
        const existingModal = document.getElementById('editTaskModalDirect');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', editModalHtml);

        // Show modal
        const editModal = new bootstrap.Modal(document.getElementById('editTaskModalDirect'));
        editModal.show();

        // Save button handler
        document.getElementById('saveTaskChangesDirect').onclick = function() {
            const newTitle = document.getElementById('editTaskTitleDirect').value;
            const newDescription = document.getElementById('editTaskDescriptionDirect').value;

            if (!newTitle.trim()) {
                alert('Titel ist erforderlich!');
                return;
            }

            // Send update request
            fetch('/loomline/aufgaben/' + taskId + '/bearbeiten/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: newTitle,
                    description: newDescription
                })
            }).then(response => response.json()).then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Fehler beim Speichern der Änderungen.');
                }
            }).catch(error => {
                console.error('Error:', error);
                alert('Fehler beim Speichern der Änderungen.');
            });
        };
    }

    // Initialize edit handlers
    attachEditHandlers();

    // Delete Task Button Handler - both front and back buttons with improved event handling
    function attachDeleteHandlers() {
        document.querySelectorAll('.delete-task-btn, .task-delete-btn-back').forEach(btn => {
            // Remove existing listeners to prevent duplicates
            btn.removeEventListener('click', handleDeleteClick);
            btn.addEventListener('click', handleDeleteClick);
        });
    }

    function handleDeleteClick(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        console.log('Delete button clicked:', this.dataset.taskId);

        const taskId = this.dataset.taskId;
        const taskTitle = this.dataset.taskTitle;

        if (confirm('Soll die Aufgabe "' + taskTitle + '" wirklich gelöscht werden?')) {
            // Get CSRF token (no optional chaining for compatibility)
            const csrfInputA = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfInputB = document.querySelector('input[name="csrfmiddlewaretoken"]');
            const csrfToken = (csrfInputA ? csrfInputA.value : null) || (csrfInputB ? csrfInputB.value : null);

            if (!csrfToken) {
                alert('CSRF Token fehlt. Bitte Seite neu laden.');
                return;
            }

            // Send delete request
            fetch('/loomline/aufgaben/' + taskId + '/loeschen/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                },
            }).then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    console.error('Delete failed with status:', response.status);
                    alert('Fehler beim Löschen der Aufgabe.');
                }
            }).catch(error => {
                console.error('Delete error:', error);
                alert('Fehler beim Löschen der Aufgabe.');
            });
        }
    }

    // Initialize delete handlers
    attachDeleteHandlers();

    // Delete Subtask Button Handler with improved event handling
    function attachDeleteSubtaskHandlers() {
        document.querySelectorAll('.delete-subtask-btn').forEach(btn => {
            btn.removeEventListener('click', handleDeleteSubtaskClick);
            btn.addEventListener('click', handleDeleteSubtaskClick);
        });
    }

    function handleDeleteSubtaskClick(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        console.log('Delete subtask button clicked:', this.dataset.subtaskId);

        const subtaskId = this.dataset.subtaskId;
        const subtaskTitle = this.dataset.subtaskTitle;

        if (confirm('Soll die Sub-Aufgabe "' + subtaskTitle + '" wirklich geloescht werden?')) {
            // Get CSRF token (no optional chaining for compatibility)
            const csrfInputC = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfInputD = document.querySelector('input[name="csrfmiddlewaretoken"]');
            const csrfToken = (csrfInputC ? csrfInputC.value : null) || (csrfInputD ? csrfInputD.value : null);

            if (!csrfToken) {
                alert('CSRF Token fehlt. Bitte Seite neu laden.');
                return;
            }

            // Send delete request
            fetch('/loomline/sub-aufgaben/' + subtaskId + '/loeschen/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                },
            }).then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    console.error('Delete subtask failed with status:', response.status);
                    alert('Fehler beim Loeschen der Sub-Aufgabe.');
                }
            }).catch(error => {
                console.error('Delete subtask error:', error);
                alert('Fehler beim Loeschen der Sub-Aufgabe.');
            });
        }
    }

    attachDeleteSubtaskHandlers();

    // Modal delete button handler
    const deleteFromModalBtn = document.getElementById('deleteTaskFromModalBtn');
    if (deleteFromModalBtn) {
        deleteFromModalBtn.addEventListener('click', function() {
            const taskId = this.dataset.taskId;
            const taskTitle = this.dataset.taskTitle;

            if (confirm('Soll die Aufgabe "' + taskTitle + '" wirklich geloescht werden?')) {
                fetch('/loomline/aufgaben/' + taskId + '/loeschen/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    },
                }).then(response => {
                    if (response.ok) {
                        location.reload();
                    } else {
                        alert('Fehler beim Loeschen der Aufgabe.');
                    }
                });
            }
        });
    }

    // Modal edit button - now with actual functionality
    const editTaskBtn = document.getElementById('editTaskBtn');
    if (editTaskBtn) {
        editTaskBtn.addEventListener('click', function() {
            const taskId = document.getElementById('deleteTaskFromModalBtn').dataset.taskId;
            const taskTitle = document.getElementById('taskEditTitle').textContent;
            const taskDescription = document.getElementById('taskEditDescription').textContent;

            // Create edit modal content with proper escaping
            const escapedTitle = taskTitle.replace(/\"/g, '&quot;').replace(/'/g, '&#x27;');
            const escapedDescription = taskDescription.replace(/</g, '&lt;').replace(/>/g, '&gt;');

            const editModalHtml = '<div class="modal fade" id="editTaskModalForm" tabindex="-1">' +
                '<div class="modal-dialog">' +
                    '<div class="modal-content">' +
                        '<div class="modal-header bg-warning text-white">' +
                            '<h5 class="modal-title">' +
                                '<i class="fas fa-edit me-2"></i>Aufgabe bearbeiten' +
                            '</h5>' +
                            '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>' +
                        '</div>' +
                        '<div class="modal-body">' +
                            '<form id="editTaskFormInner">' +
                                '<div class="mb-3">' +
                                    '<label class="form-label fw-bold">Titel</label>' +
                                    '<input type="text" class="form-control" id="editTaskTitleInput" value="' + escapedTitle + '" required>' +
                                '</div>' +
                                '<div class="mb-3">' +
                                    '<label class="form-label fw-bold">Beschreibung</label>' +
                                    '<textarea class="form-control" id="editTaskDescriptionInput" rows="4">' + escapedDescription + '</textarea>' +
                                '</div>' +
                            '</form>' +
                        '</div>' +
                        '<div class="modal-footer">' +
                            '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Abbrechen</button>' +
                            '<button type="button" class="btn btn-warning" id="saveTaskChangesBtn">' +
                                '<i class="fas fa-save me-2"></i>Speichern' +
                            '</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';

            // Add modal to DOM if not exists
            if (!document.getElementById('editTaskModalForm')) {
                document.body.insertAdjacentHTML('beforeend', editModalHtml);
            } else {
                // Update existing modal values
                document.getElementById('editTaskTitleInput').value = taskTitle;
                document.getElementById('editTaskDescriptionInput').value = taskDescription;
            }

            // Show edit modal
            const editModal = new bootstrap.Modal(document.getElementById('editTaskModalForm'));
            editModal.show();

            // Hide current modal
            bootstrap.Modal.getInstance(document.getElementById('taskEditModal')).hide();

            // Save button handler
            document.getElementById('saveTaskChangesBtn').onclick = function() {
                const newTitle = document.getElementById('editTaskTitleInput').value;
                const newDescription = document.getElementById('editTaskDescriptionInput').value;

                if (!newTitle.trim()) {
                    alert('Titel ist erforderlich!');
                    return;
                }

                // Send update request
                fetch('/loomline/aufgaben/' + taskId + '/bearbeiten/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        title: newTitle,
                        description: newDescription
                    })
                }).then(response => response.json()).then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Fehler beim Speichern der Änderungen.');
                    }
                }).catch(error => {
                    console.error('Error:', error);
                    alert('Fehler beim Speichern der Änderungen.');
                });
            };
        });
    }

    // Close tooltip when clicking outside (mobile)
    if (window.innerWidth <= 768) {
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.task-tile')) {
                document.querySelectorAll('.task-tooltip').forEach(t => {
                    t.style.opacity = '0';
                    t.style.visibility = 'hidden';
                });
            }
        });
    }
});

