/**
 * Sapheneia TimesFM Web Application JavaScript
 * Handles user interactions, API calls, and dynamic content updates
 */

class SapheneiaTimesFM {
    constructor() {
        this.modelInitialized = false;
        this.currentData = null;
        this.currentResults = null;
        this.currentPlotFigure = null;
        this.currentPlotConfig = null;
        this.resizeTimeout = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormValidation();
    }

    bindEvents() {
        // Model configuration
        document.getElementById('modelConfigForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.initializeModel();
        });

        document.getElementById('modelSource').addEventListener('change', (e) => {
            this.toggleModelSourceFields(e.target.value);
        });

        // Data upload
        document.getElementById('uploadBtn').addEventListener('click', () => {
            this.uploadData();
        });

        // Sample data generation removed as per requirements

        // Forecasting
        document.getElementById('forecastConfigForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.runForecast();
        });

        // Quantile selector is now always visible, no toggle needed

        // Download chart
        document.getElementById('downloadChart').addEventListener('click', () => {
            this.downloadChart();
        });

        // Download data
        document.getElementById('downloadData').addEventListener('click', () => {
            this.downloadData();
        });


        // Tab switching - preserve scroll position
        this.setupTabSwitching();
        
        // Bind quantile events
        this.bindQuantileEvents();
    }

    setupFormValidation() {
        // Add real-time validation for numeric inputs
        const numericInputs = ['contextLen', 'horizonLen'];
        numericInputs.forEach(id => {
            const input = document.getElementById(id);
            input.addEventListener('input', (e) => {
                this.validateNumericInput(e.target);
            });
        });
    }

    validateNumericInput(input) {
        const value = parseInt(input.value);
        const min = parseInt(input.min);
        const max = parseInt(input.max);

        if (isNaN(value) || value < min || value > max) {
            input.classList.add('is-invalid');
            return false;
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            return true;
        }
    }

    toggleModelSourceFields(source) {
        const huggingfaceRow = document.getElementById('huggingfaceRow');
        const localPathRow = document.getElementById('localPathRow');
        
        if (source === 'local') {
            huggingfaceRow.style.display = 'none';
            localPathRow.style.display = 'block';
        } else {
            huggingfaceRow.style.display = 'block';
            localPathRow.style.display = 'none';
        }
    }

    showAlert(type, title, message) {
        const alertContainer = document.getElementById('alertContainer');
        const alertId = 'alert_' + Date.now();
        
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show slide-in" role="alert" id="${alertId}">
                <strong>${title}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }

    showLoading(title = 'Processing...', subtitle = 'Please wait while we process your request.') {
        const loadingTextElement = document.getElementById('loadingText');
        const loadingSubtextElement = document.getElementById('loadingSubtext');
        const modalElement = document.getElementById('loadingModal');
        
        if (!loadingTextElement || !loadingSubtextElement || !modalElement) {
            console.error('Loading modal elements not found:', {
                loadingText: !!loadingTextElement,
                loadingSubtext: !!loadingSubtextElement, 
                loadingModal: !!modalElement
            });
            return;
        }
        
        loadingTextElement.textContent = title;
        loadingSubtextElement.textContent = subtitle;
        
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }

    hideLoading() {
        console.log('hideLoading() called');
        
        // Multiple approaches to ensure modal is hidden
        const modalElement = document.getElementById('loadingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        
        console.log('Modal instance:', modal);
        console.log('Modal element classes:', modalElement?.classList.toString());
        
        // Approach 1: Try Bootstrap's hide method
        if (modal) {
            modal.hide();
            console.log('Called Bootstrap modal.hide()');
        }
        
        // Approach 2: Force hide with a slight delay to ensure Bootstrap completes
        setTimeout(() => {
            console.log('Force hiding modal after timeout...');
            console.log('Modal element before force hide:', modalElement);
            console.log('Modal is visible?', modalElement?.offsetParent !== null);
            
            if (modalElement) {
                // Remove Bootstrap classes and attributes more aggressively
                modalElement.classList.remove('show', 'd-block');
                modalElement.classList.add('d-none');
                modalElement.setAttribute('aria-hidden', 'true');
                modalElement.removeAttribute('aria-modal');
                modalElement.removeAttribute('role');
                modalElement.style.display = 'none !important';
                
                // Also hide the modal dialog
                const modalDialog = modalElement.querySelector('.modal-dialog');
                if (modalDialog) {
                    modalDialog.style.display = 'none';
                }
                
                // Clean up body classes and attributes
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
                
                // Remove backdrop more precisely - only actual modal backdrops
                const backdrops = document.querySelectorAll('.modal-backdrop');
                console.log('Found modal backdrops:', backdrops.length);
                backdrops.forEach((element, index) => {
                    console.log(`Removing backdrop ${index}:`, element);
                    element.remove();
                });
                
                // Double-check for any remaining modal-related elements (but don't remove them)
                const remainingModals = document.querySelectorAll('.modal.show, .modal.d-block');
                remainingModals.forEach(m => {
                    // Only hide modals, don't remove them from DOM
                    if (m !== modalElement) { // Don't double-process our target modal
                        m.classList.remove('show', 'd-block');
                        m.classList.add('d-none');
                        m.style.display = 'none';
                    }
                });
                
                console.log('Modal force hidden - classes now:', modalElement.classList.toString());
                console.log('Modal visible after force hide?', modalElement.offsetParent !== null);
                console.log('Body classes after cleanup:', document.body.classList.toString());
            }
        }, 100);
    }

    updateModelStatus(status, info = null) {
        const statusElement = document.getElementById('modelStatus');
        
        if (status === 'initializing') {
            statusElement.innerHTML = '<span class="badge bg-warning">Initializing...</span>';
        } else if (status === 'ready') {
            statusElement.innerHTML = '<span class="badge bg-success">Ready</span>';
            this.modelInitialized = true;
            this.updateForecastButtonState();
        } else if (status === 'error') {
            statusElement.innerHTML = '<span class="badge bg-danger">Error</span>';
            this.modelInitialized = false;
        } else {
            statusElement.innerHTML = '<span class="badge bg-secondary">Not Initialized</span>';
            this.modelInitialized = false;
        }
    }

    async initializeModel() {
        const form = document.getElementById('modelConfigForm');
        const formData = new FormData(form);
        
        const config = {
            backend: document.getElementById('backend').value,
            context_len: parseInt(document.getElementById('contextLen').value),
            horizon_len: parseInt(document.getElementById('horizonLen').value)
        };

        const modelSource = document.getElementById('modelSource').value;
        if (modelSource === 'local') {
            config.local_path = document.getElementById('localPath').value;
            if (!config.local_path) {
                this.showAlert('danger', 'Error', 'Please provide a local model path.');
                return;
            }
        } else {
            config.checkpoint = document.getElementById('checkpoint').value;
        }

        this.updateModelStatus('initializing');
        this.showLoading('Initializing TimesFM Model', 'This may take a few minutes on first run...');

        try {
            const response = await fetch('/api/model/init', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const result = await response.json();
            
            if (result.success) {
                this.updateModelStatus('ready', result.model_info);
                this.showAlert('success', 'Success', 'TimesFM model initialized successfully!');
                
                // Update UI with model capabilities
                if (result.model_info && result.model_info.capabilities) {
                    this.updateCapabilitiesUI(result.model_info.capabilities);
                }
            } else {
                this.updateModelStatus('error');
                this.showAlert('danger', 'Initialization Failed', result.message || 'Unknown error occurred');
            }
        } catch (error) {
            this.updateModelStatus('error');
            this.showAlert('danger', 'Network Error', 'Failed to communicate with server: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    updateCapabilitiesUI(capabilities) {
        // Quantile selector is now always visible and enabled
        // No need to update any checkboxes since they're always shown
    }

    async uploadData() {
        const fileInput = document.getElementById('dataFile');
        const file = fileInput.files[0];

        if (!file) {
            this.showAlert('warning', 'No File Selected', 'Please select a CSV file to upload.');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.csv')) {
            this.showAlert('danger', 'Invalid File Type', 'Please upload a CSV file.');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        this.showLoading('Uploading Data', 'Processing your CSV file...');

        try {
            console.log('Starting file upload...');
            const response = await fetch('/api/data/upload', {
                method: 'POST',
                body: formData
            });

            console.log('Response received:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Get response text first to debug potential JSON parsing issues
            const responseText = await response.text();
            console.log('Raw response text:', responseText.substring(0, 200) + '...');

            let result;
            try {
                result = JSON.parse(responseText);
                console.log('Parsed result:', result);
            } catch (jsonError) {
                console.error('JSON parsing failed:', jsonError);
                console.error('Response text that failed to parse:', responseText);
                throw new Error(`Failed to parse JSON response: ${jsonError.message}`);
            }

            if (result.success) {
                console.log('Processing successful result...');
                try {
                    this.currentData = result.data_info;
                    console.log('Set currentData:', this.currentData);
                    
                    this.showAlert('success', 'Upload Successful', 'Data uploaded and processed successfully!');
                    console.log('Showed success alert');
                    
                    this.displayDataInfo(result.data_info);
                    console.log('Displayed data info');
                    
                    this.generateDataDefinition(result.data_info.columns);
                    console.log('Generated data definition');
                    
                    this.updateForecastButtonState();
                    console.log('Updated forecast button state');
                    
                } catch (processingError) {
                    console.error('Error processing successful result:', processingError);
                    this.showAlert('danger', 'Processing Error', `Error processing upload result: ${processingError.message}`);
                }
            } else {
                console.log('Upload failed, showing error:', result.message);
                
                // Handle forecast output data error specially
                if (result.is_forecast_output) {
                    const suggestedColumns = result.suggested_columns ? result.suggested_columns.join(', ') : 'date, value, price, amount, count, sales, revenue';
                    this.showAlert('warning', 'Wrong Data Type', 
                        `${result.message}<br><br><strong>Expected columns:</strong> ${suggestedColumns}<br><br>` +
                        'Please upload your original time series data, not forecast output data.');
                } else {
                    this.showAlert('danger', 'Upload Failed', result.message || 'Upload failed');
                }
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showAlert('danger', 'Network Error', 'Failed to upload file: ' + error.message);
        } finally {
            console.log('Upload process completed');
            this.hideLoading();
        }
    }

    // Sample data generation removed as per requirements

    displayDataInfo(dataInfo) {
        const dataInfoDiv = document.getElementById('dataInfo');
        const dataDetailsDiv = document.getElementById('dataDetails');

        let html = `
            <div class="row">
                <div class="col-md-6">
                    <table class="table table-sm data-info-table">
                        <tr><th>Filename</th><td>${dataInfo.filename}</td></tr>
                        <tr><th>Shape</th><td>${dataInfo.shape[0]} rows × ${dataInfo.shape[1]} columns</td></tr>
                        ${dataInfo.date_range ? `
                            <tr><th>Date Range</th><td>${dataInfo.date_range.start} to ${dataInfo.date_range.end}</td></tr>
                            <tr><th>Total Periods</th><td>${dataInfo.date_range.periods}</td></tr>
                        ` : ''}
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Data Preview</h6>
                    <div class="table-responsive">
                        <table class="table table-sm table-striped">
                            <thead>
                                <tr>
                                    ${dataInfo.columns.map(col => `<th>${col}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${dataInfo.head.slice(0, 3).map(row => `
                                    <tr>
                                        ${dataInfo.columns.map(col => `<td>${this.formatValue(row[col])}</td>`).join('')}
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        if (dataDetailsDiv) {
            dataDetailsDiv.innerHTML = html;
        }
        if (dataInfoDiv) {
            dataInfoDiv.style.display = 'block';
            dataInfoDiv.classList.add('fade-in');
        }
        
        // Generate data definition with integrated checkboxes
        this.generateDataDefinition(dataInfo.columns);
        
        // Initialize date configuration
        this.initializeDateConfiguration(dataInfo);
    }

    formatValue(value) {
        if (value == null) return 'null';
        if (typeof value === 'number') {
            return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
        }
        return String(value).substring(0, 20) + (String(value).length > 20 ? '...' : '');
    }


    bindColumnSelectionEvents() {
        // Select all button
        document.getElementById('selectAllColumns').addEventListener('click', () => {
            document.querySelectorAll('.column-checkbox').forEach(cb => {
                cb.checked = true;
            });
        });

        // Deselect all button
        document.getElementById('deselectAllColumns').addEventListener('click', () => {
            document.querySelectorAll('.column-checkbox').forEach(cb => {
                cb.checked = false;
            });
        });

        // Individual checkbox change events
        document.querySelectorAll('.column-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                this.updateColumnSelectionState();
            });
        });
    }

    updateColumnSelectionState() {
        // This function can be used for any additional state updates if needed
        // Currently, the checkboxes are integrated into the data definition section
    }

    getSelectedColumns() {
        return Array.from(document.querySelectorAll('.column-checkbox:checked'))
                   .map(cb => cb.value);
    }


    generateDataDefinition(columns, isSampleData = false) {
        const definitionDiv = document.getElementById('dataDefinition');
        const columnsDiv = document.getElementById('columnDefinitions');

        let html = '<div class="row">';

        columns.forEach((col, index) => {
            if (col === 'date') return; // Skip date column

            // Default to target for first column, others as dynamic_numerical
            const defaultValue = index === 1 ? 'target' : 'dynamic_numerical';
            
            html += `
                <div class="col-md-6 col-lg-4">
                    <div class="column-definition">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div class="column-name">${col}</div>
                            <div class="form-check form-switch">
                                <input class="form-check-input column-checkbox" type="checkbox" 
                                       id="col_${col}" value="${col}" checked>
                                <label class="form-check-label" for="col_${col}">
                                </label>
                            </div>
                        </div>
                        <select class="form-select form-select-sm" id="def_${col}">
                            <option value="target" ${defaultValue === 'target' ? 'selected' : ''}>Target (main forecast variable)</option>
                            <option value="dynamic_numerical" ${defaultValue === 'dynamic_numerical' ? 'selected' : ''}>Dynamic Numerical</option>
                            <option value="dynamic_categorical" ${defaultValue === 'dynamic_categorical' ? 'selected' : ''}>Dynamic Categorical</option>
                            <option value="static_numerical" ${defaultValue === 'static_numerical' ? 'selected' : ''}>Static Numerical</option>
                            <option value="static_categorical" ${defaultValue === 'static_categorical' ? 'selected' : ''}>Static Categorical</option>
                        </select>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        
        // Add control buttons
        html += `
            <div class="mt-3">
                <button type="button" class="btn btn-outline-primary btn-sm" id="selectAllColumns">
                    <i class="fas fa-check-square me-1"></i>Select All
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm ms-2" id="deselectAllColumns">
                    <i class="fas fa-square me-1"></i>Deselect All
                </button>
            </div>
        `;

        if (columnsDiv) {
            columnsDiv.innerHTML = html;
        }
        if (definitionDiv) {
            definitionDiv.style.display = 'block';
            definitionDiv.classList.add('fade-in');
        }

        // Bind event listeners
        this.bindColumnSelectionEvents();
    }

    getDataDefinition() {
        const definition = {};
        const selectedColumns = this.getSelectedColumns();

        selectedColumns.forEach(col => {
            const select = document.getElementById(`def_${col}`);
            if (select) {
                definition[col] = select.value;
            }
        });

        return definition;
    }

    initializeDateConfiguration(dataInfo) {
        const contextDatesSection = document.getElementById('contextDatesSection');
        if (!contextDatesSection) {
            console.error('Context dates section not found');
            return;
        }
        
        contextDatesSection.style.display = 'block';
        contextDatesSection.classList.add('fade-in');

        // Store data range for constraints
        this.dataDateRange = dataInfo.date_range;
        this.dataPeriods = dataInfo.date_range.periods; // Actual number of periods in data
        this.availableDates = dataInfo.date_range.available_dates || []; // All available dates in data
        
        if (this.dataDateRange && this.dataDateRange.start && this.dataDateRange.end) {
            // Update available data information
            const availableDataLength = document.getElementById('availableDataLength');
            const availableDataRange = document.getElementById('availableDataRange');
            const contextStartDate = document.getElementById('contextStartDate');
            const contextEndDate = document.getElementById('contextEndDate');
            
            if (availableDataLength) availableDataLength.textContent = this.dataPeriods;
            if (availableDataRange) availableDataRange.textContent = 
                `${this.dataDateRange.start} to ${this.dataDateRange.end}`;

            // Set up date constraints
            this.setupDateConstraints(contextStartDate, contextEndDate);

            // Initialize context dates to full data range
            if (contextStartDate) contextStartDate.value = this.dataDateRange.start;
            if (contextEndDate) contextEndDate.value = this.dataDateRange.end;

            // Calculate and display context length
            this.updateContextLengthFromDates();
            
            // Test: Force update after a short delay to ensure elements are ready
            setTimeout(() => {
                console.log('Forcing context length update after delay');
                this.updateContextLengthFromDates();
            }, 100);
        }

        // Bind date change events
        this.bindDateChangeEvents();
    }

    setupDateConstraints(contextStartDate, contextEndDate) {
        if (!this.availableDates || this.availableDates.length === 0) {
            console.warn('No available dates found in data');
            return;
        }

        console.log('Setting up date constraints with available dates:', this.availableDates);

        // Populate select dropdowns with available dates
        if (contextStartDate) {
            this.populateDateSelect(contextStartDate, this.availableDates);
        }
        if (contextEndDate) {
            this.populateDateSelect(contextEndDate, this.availableDates);
        }
    }

    populateDateSelect(selectElement, availableDates) {
        // Clear existing options except the first placeholder
        while (selectElement.children.length > 1) {
            selectElement.removeChild(selectElement.lastChild);
        }
        
        // Add options for each available date
        availableDates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            selectElement.appendChild(option);
        });
    }

    bindDateChangeEvents() {
        // Context start date change event - validates and updates context length
        const contextStartDate = document.getElementById('contextStartDate');
        if (contextStartDate) {
            console.log('Binding context start date event listener');
            contextStartDate.addEventListener('change', () => {
                this.updateContextFromStartDate();
            });
        } else {
            console.error('Context start date element not found');
        }

        // Context end date change event - updates context length
        const contextEndDate = document.getElementById('contextEndDate');
        if (contextEndDate) {
            console.log('Binding context end date event listener');
            contextEndDate.addEventListener('change', () => {
                this.updateContextFromEndDate();
            });
        } else {
            console.error('Context end date element not found');
        }
    }


    updateModelConfiguration(contextLen, horizonLen) {
        const contextLenElement = document.getElementById('contextLen');
        const horizonLenElement = document.getElementById('horizonLen');
        
        if (contextLenElement) contextLenElement.value = contextLen;
        if (horizonLenElement) horizonLenElement.value = horizonLen;
    }

    calculateDaysDifference(startDate, endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const timeDiff = end.getTime() - start.getTime();
        return Math.ceil(timeDiff / (1000 * 3600 * 24)) + 1; // +1 to include both start and end dates
    }



    updateContextFromStartDate() {
        // When context start date changes, validate and update context length
        console.log('Context start date changed');
        const contextStartElement = document.getElementById('contextStartDate');
        if (!contextStartElement) return;
        
        const contextStart = contextStartElement.value;
        if (!contextStart) return;

        // Since we're using select dropdowns with available dates, no need for range validation
        console.log('Selected context start date:', contextStart);

        // Recalculate context length and validate constraints
        this.updateContextLengthFromDates();
    }

    updateContextFromEndDate() {
        // When context end date changes, validate and update context length
        console.log('Context end date changed');
        const contextEndElement = document.getElementById('contextEndDate');
        if (!contextEndElement) return;
        
        const contextEnd = contextEndElement.value;
        if (!contextEnd) return;

        // Since we're using select dropdowns with available dates, no need for range validation
        console.log('Selected context end date:', contextEnd);

        // Recalculate context length and validate constraints
        this.updateContextLengthFromDates();
    }


    updateContextLengthFromDates() {
        // Calculate context length based on actual data periods between selected dates
        console.log('updateContextLengthFromDates called');
        const contextStartElement = document.getElementById('contextStartDate');
        const contextEndElement = document.getElementById('contextEndDate');
        
        if (!contextStartElement || !contextEndElement || !this.availableDates) {
            console.log('Missing elements or available dates:', {
                contextStartElement: !!contextStartElement,
                contextEndElement: !!contextEndElement,
                availableDates: !!this.availableDates
            });
            return;
        }
        
        const contextStart = contextStartElement.value;
        const contextEnd = contextEndElement.value;
        
        if (!contextStart || !contextEnd) {
            console.log('Missing date values:', { contextStart, contextEnd });
            return;
        }
        
        // Find the indices of the selected dates in the available dates array
        const startIndex = this.availableDates.indexOf(contextStart);
        const endIndex = this.availableDates.indexOf(contextEnd);
        
        if (startIndex === -1 || endIndex === -1) {
            console.error('Selected dates not found in available dates');
            return;
        }
        
        // Calculate context length as the number of periods between the dates (inclusive)
        let contextLen = endIndex - startIndex + 1;
        
        console.log('Context length calculation:', {
            contextStart,
            contextEnd,
            startIndex,
            endIndex,
            contextLen,
            availableDatesCount: this.availableDates.length
        });
        
        // Ensure context length is positive and doesn't exceed available data
        if (contextLen <= 0) {
            console.warn('Context length is zero or negative, setting to 1');
            contextLen = 1;
        }
        
        if (contextLen > this.dataPeriods) {
            console.warn(`Context length (${contextLen}) exceeds available data periods (${this.dataPeriods}), adjusting`);
            contextLen = this.dataPeriods;
        }
        
        // Get horizon length from model configuration
        const horizonLen = parseInt(document.getElementById('horizonLen').value) || 24;
        
        // Apply 32-multiple truncation (truncate earlier periods)
        const truncatedContextLen = contextLen - (contextLen % 32);
        
        // Validate TimesFM constraints
        const totalLength = truncatedContextLen + horizonLen;
        const isMultipleOf32 = truncatedContextLen % 32 === 0;
        const isWithinLimit = totalLength <= 4096;
        
        if (truncatedContextLen < 32) {
            this.showAlert('error', 'Insufficient Context', 
                `Context length ${truncatedContextLen} is less than minimum 32 periods required by TimesFM.`);
            return;
        }
        
        if (!isWithinLimit) {
            this.showAlert('warning', 'Constraint Warning', 
                `Total length ${totalLength} exceeds TimesFM limit of 4096.`);
        }
        
        // Update model configuration and display
        this.updateModelConfiguration(truncatedContextLen, horizonLen);
        
        const contextLengthDisplay = document.getElementById('contextLengthDisplay');
        if (contextLengthDisplay) {
            contextLengthDisplay.textContent = truncatedContextLen;
        }
        
        this.updateConstraintFeedback(truncatedContextLen, horizonLen);
    }

    updateConstraintFeedback(contextLen, horizonLen) {
        const totalLength = contextLen + horizonLen;
        const isMultipleOf32 = contextLen % 32 === 0;
        const isWithinLimit = totalLength <= 4096;
        
        // Update context length display with color coding
        const contextDisplay = document.getElementById('contextLengthDisplay');
        if (contextDisplay) {
            if (isMultipleOf32) {
                contextDisplay.style.color = 'green';
            } else {
                contextDisplay.style.color = 'red';
            }
        }
        
        // Update total length display with color coding
        const totalDisplay = document.getElementById('totalLengthDisplay');
        if (totalDisplay) {
            if (isWithinLimit) {
                totalDisplay.style.color = 'green';
            } else {
                totalDisplay.style.color = 'red';
            }
        }
        
        // Show warning if constraints are violated
        if (!isMultipleOf32 || !isWithinLimit) {
            this.showAlert('warning', 'Constraint Warning', 
                `TimesFM 2.0 constraints: Context length must be multiple of 32 (${contextLen}), total length must be ≤ 4096 (${totalLength})`);
        }
    }

    updateForecastButtonState() {
        const forecastBtn = document.getElementById('forecastBtn');
        const canForecast = this.modelInitialized && this.currentData;
        
        forecastBtn.disabled = !canForecast;
        
        if (canForecast) {
            forecastBtn.classList.remove('btn-secondary');
            forecastBtn.classList.add('btn-warning');
        } else {
            forecastBtn.classList.add('btn-secondary');
            forecastBtn.classList.remove('btn-warning');
        }
    }

    async runForecast() {
        if (!this.modelInitialized || !this.currentData) {
            this.showAlert('warning', 'Cannot Forecast', 'Please initialize model and upload data first.');
            return;
        }

        // Clear any previous results/errors
        this.clearForecastResults();

        const selectedColumns = this.getSelectedColumns();
        if (selectedColumns.length === 0) {
            this.showAlert('warning', 'No Variables Selected', 'Please select at least one variable for forecasting.');
            return;
        }

        const dataDefinition = this.getDataDefinition();
        
        // Validate that at least one target column is defined
        const hasTarget = Object.values(dataDefinition).includes('target');
        if (!hasTarget) {
            this.showAlert('warning', 'No Target Variable', 'Please define at least one selected column as the target variable.');
            return;
        }

        const config = {
            filename: this.currentData.filename,
            data_definition: dataDefinition,
            use_covariates: document.getElementById('useCovariates').checked,
            context_len: parseInt(document.getElementById('contextLen').value),
            horizon_len: parseInt(document.getElementById('horizonLen').value),
            context_start_date: document.getElementById('contextStartDate').value,
            context_end_date: document.getElementById('contextEndDate').value
        };
        
        // Attach user-selected quantile ticks (no default - respect user selection)
        let ticks = Array.from(document.querySelectorAll('.quantile-tick'))
            .filter(cb => cb.checked)
            .map(cb => parseInt(cb.value))
            .sort((a,b) => a - b);
        // Don't set default quantiles - pass empty array if none selected
        config.quantile_indices = ticks;
        
        // FRONTEND DEBUGGING - Show what we're sending to backend
        console.log("=".repeat(80));
        console.log("FRONTEND DEBUGGING - SENDING TO BACKEND");
        console.log("=".repeat(80));
        console.log("Configuration being sent to backend:");
        console.log("  - Filename:", config.filename);
        console.log("  - Use Covariates:", config.use_covariates);
        console.log("  - Context Length:", config.context_len);
        console.log("  - Horizon Length:", config.horizon_len);
        console.log("  - Context Start Date:", config.context_start_date);
        console.log("  - Context End Date:", config.context_end_date);
        console.log("  - Quantile Indices:", config.quantile_indices);
        
        // Show current UI state
        console.log("Current UI state:");
        console.log("  - Context Start Date element value:", document.getElementById('contextStartDate').value);
        console.log("  - Context End Date element value:", document.getElementById('contextEndDate').value);
        console.log("  - Context Length element value:", document.getElementById('contextLen').value);
        console.log("  - Horizon Length element value:", document.getElementById('horizonLen').value);
        console.log("  - Context Length display:", document.getElementById('contextLengthDisplay').textContent);
        console.log("  - Use Covariates checkbox:", document.getElementById('useCovariates').checked);
        
        // Show data definition
        console.log("Data definition:");
        console.log("  - Selected columns:", Object.keys(dataDefinition));
        console.log("  - Column types:", dataDefinition);
        
        console.log("=".repeat(80));

        this.showLoading('Running Forecast', 'TimesFM is analyzing your data and generating forecasts...');

        try {
            const response = await fetch('/api/forecast', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                console.log('Forecast successful, proceeding to display and visualize...');
                this.currentResults = result;
                this.showAlert('success', 'Forecast Complete', 'Forecasting completed successfully!');
                
                try {
                    await this.displayResults(result);
                    console.log('displayResults completed successfully');
                } catch (displayError) {
                    console.error('Error in displayResults:', displayError);
                }
                
                console.log('About to call generateVisualization...');
                try {
                    this.generateVisualization(result);
                } catch (vizError) {
                    console.error('Error calling generateVisualization:', vizError);
                }
            } else {
                // Handle both HTTP errors and API errors
                const errorMessage = result.message || `HTTP ${response.status}: ${response.statusText}`;
                console.log('Forecast error received:', { result, response: { status: response.status, statusText: response.statusText } });
                this.displayForecastError(errorMessage);
                this.showAlert('danger', 'Forecast Failed', 'Please check the error details below.');
            }
        } catch (error) {
            this.displayForecastError('Network Error: ' + error.message);
            this.showAlert('danger', 'Network Error', 'Please check the error details below.');
        } finally {
            this.hideLoading();
        }
    }

    displayForecastError(errorMessage) {
        console.log('Displaying forecast error:', errorMessage);
        const resultsCard = document.getElementById('resultsCard');
        const cardBody = resultsCard.querySelector('.card-body');
        
        console.log('Found elements:', { resultsCard, cardBody });
        
        // Clear any existing results and hide tabs
        const resultTabs = document.getElementById('resultTabs');
        const resultTabContent = document.getElementById('resultTabContent');
        
        if (resultTabs) resultTabs.style.display = 'none';
        if (resultTabContent) resultTabContent.style.display = 'none';
        
        // Create error display
        const errorHtml = `
            <div class="alert alert-danger" role="alert">
                <h5 class="alert-heading">
                    <i class="fas fa-exclamation-triangle me-2"></i>Forecast Error
                </h5>
                <hr>
                <div class="error-details">
                    <h6>Error Details:</h6>
                    <pre class="bg-light p-3 rounded mt-2" style="white-space: pre-wrap; font-size: 0.9rem;">${errorMessage}</pre>
                </div>
                <div class="mt-3">
                    <h6>Common Solutions:</h6>
                    <ul class="mb-0">
                        <li>Check that your data definition is correct (especially static vs dynamic covariates)</li>
                        <li>Ensure all selected variables have valid data (no missing values in critical columns)</li>
                        <li>Verify that at least one variable is defined as "Target"</li>
                        <li>Check that your data has enough historical points for the selected context length</li>
                    </ul>
                </div>
            </div>
        `;
        
        cardBody.innerHTML = errorHtml;
        resultsCard.style.display = 'block';
        resultsCard.classList.add('fade-in');
    }

    clearForecastResults() {
        const resultsCard = document.getElementById('resultsCard');
        
        if (resultsCard) {
            resultsCard.style.display = 'none';
            // Reset the card body to its original structure
            const cardBody = resultsCard.querySelector('.card-body');
            if (cardBody) {
                // Restore original structure
                cardBody.innerHTML = `
                    <!-- Tabs for different result views -->
                    <ul class="nav nav-tabs" id="resultTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" id="visualization-tab" data-bs-toggle="tab" 
                                    data-bs-target="#visualization" type="button" role="tab">
                                <i class="fas fa-chart-area me-1"></i>
                                Visualization
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="summary-tab" data-bs-toggle="tab" 
                                    data-bs-target="#summary" type="button" role="tab">
                                <i class="fas fa-list me-1"></i>
                                Summary
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="data-tab" data-bs-toggle="tab" 
                                    data-bs-target="#data" type="button" role="tab">
                                <i class="fas fa-table me-1"></i>
                                Data
                            </button>
                        </li>
                    </ul>

                    <!-- Tab Content -->
                    <div class="tab-content mt-3" id="resultTabContent">
                        <!-- Visualization Tab -->
                        <div class="tab-pane fade show active" id="visualization" role="tabpanel">
                            <div class="chart-container">
                                <div id="forecastChart"></div>
                            </div>
                            <div class="mt-3">
                                <button type="button" class="btn btn-outline-primary" id="downloadChart">
                                    <i class="fas fa-download me-2"></i>
                                    Download Chart
                                </button>
                                <button type="button" class="btn btn-outline-success ms-2" id="downloadData">
                                    <i class="fas fa-table me-2"></i>
                                    Download Data
                                </button>
                            </div>
                            <!-- Quantile selection (always visible) -->
                            <div class="row mt-3" id="quantileSelector">
                                <div class="col-12">
                                    <label class="form-label">Select quantiles to shade (choose lower and upper)</label>
                                    <div class="d-flex flex-wrap gap-2" id="quantileCheckboxes">
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="1" id="q1" checked>
                                            <label class="form-check-label" for="q1">Q10</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="2" id="q2">
                                            <label class="form-check-label" for="q2">Q20</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="3" id="q3">
                                            <label class="form-check-label" for="q3">Q30</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="4" id="q4">
                                            <label class="form-check-label" for="q4">Q40</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="5" id="q5">
                                            <label class="form-check-label" for="q5">Q50</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="6" id="q6">
                                            <label class="form-check-label" for="q6">Q60</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="7" id="q7">
                                            <label class="form-check-label" for="q7">Q70</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="8" id="q8">
                                            <label class="form-check-label" for="q8">Q80</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input quantile-tick" type="checkbox" value="9" id="q9" checked>
                                            <label class="form-check-label" for="q9">Q90</label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Summary Tab -->
                        <div class="tab-pane fade" id="summary" role="tabpanel">
                            <div id="forecastSummary">
                                <p class="text-muted">Summary will appear here after forecasting.</p>
                            </div>
                        </div>

                        <!-- Data Tab -->
                        <div class="tab-pane fade" id="data" role="tabpanel">
                            <div id="forecastData">
                                <p class="text-muted">Data will appear here after forecasting.</p>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Re-bind quantile change events
            this.bindQuantileEvents();
            
            // Re-bind download button events
            this.bindDownloadEvents();
        }
    }

    bindQuantileEvents() {
        // Bind change events to quantile checkboxes
        document.querySelectorAll('.quantile-tick').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.refreshVisualization();
            });
        });
    }

    refreshVisualization() {
        // Only refresh if we have current results
        if (this.currentResults && this.currentResults.success) {
            console.log('Refreshing visualization with new quantile selection...');
            
            // Get selected quantiles (empty array if none selected)
            const selectedQuantiles = document.querySelectorAll('.quantile-tick:checked');
            const quantileIndices = Array.from(selectedQuantiles)
                .map(cb => parseInt(cb.value))
                .sort((a, b) => a - b);
            
            console.log('Selected quantile indices:', quantileIndices);
            console.log('Number of selected quantiles:', quantileIndices.length);
            
            // Create a copy of results with updated quantile indices
            const updatedResults = { ...this.currentResults };
            updatedResults.quantile_indices = quantileIndices;
            
            this.generateVisualization(updatedResults);
        }
    }

    bindDownloadEvents() {
        // Re-bind download button events after HTML recreation
        const downloadChartBtn = document.getElementById('downloadChart');
        const downloadDataBtn = document.getElementById('downloadData');
        
        if (downloadChartBtn) {
            downloadChartBtn.addEventListener('click', () => {
                this.downloadChart();
            });
        }
        
        if (downloadDataBtn) {
            downloadDataBtn.addEventListener('click', () => {
                this.downloadData();
            });
        }
    }

    async displayResults(result) {
        const resultsCard = document.getElementById('resultsCard');
        
        if (!resultsCard) {
            console.error('resultsCard element not found');
            return;
        }
        
        resultsCard.style.display = 'block';
        resultsCard.classList.add('fade-in');

        // Populate summary tab
        this.displaySummary(result.forecast_summary, result.results);
        
        // Populate data tab
        this.displayDataTable(result.results);
    }

    displaySummary(summary, results) {
        const summaryDiv = document.getElementById('forecastSummary');
        
        if (!summaryDiv) {
            console.error('forecastSummary element not found');
            return;
        }

        const methodsCount = summary.methods_used.length;
        const mainForecast = results.enhanced_forecast || results.point_forecast;
        const avgForecast = mainForecast ? (mainForecast.reduce((a, b) => a + b, 0) / mainForecast.length) : 0;

        let html = `
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="summary-card bg-primary">
                        <div class="summary-value">${summary.context_length}</div>
                        <div class="summary-label">Context Length</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="summary-card bg-success">
                        <div class="summary-value">${summary.horizon_length}</div>
                        <div class="summary-label">Forecast Periods</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="summary-card bg-info">
                        <div class="summary-value">${methodsCount}</div>
                        <div class="summary-label">Methods Used</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="summary-card bg-warning">
                        <div class="summary-value">$${avgForecast.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                        <div class="summary-label">Avg. Forecast</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <h6>Configuration</h6>
                    <table class="table table-sm">
                        <tr><th>Target Variable</th><td>${summary.target_column}</td></tr>
                        <tr><th>Covariates Used</th><td>${summary.covariates_used ? 'Yes' : 'No'}</td></tr>
                        <tr><th>Methods</th><td>${summary.methods_used.join(', ')}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Forecast Methods</h6>
                    <ul class="list-group list-group-flush">
        `;

        summary.methods_used.forEach(method => {
            const methodName = method.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            const forecast = results[method];
            
            // Check if forecast is an array and has numeric values
            if (Array.isArray(forecast) && forecast.length > 0 && typeof forecast[0] === 'number') {
                const minVal = Math.min(...forecast);
                const maxVal = Math.max(...forecast);
                
                html += `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        ${methodName}
                        <span class="badge bg-secondary">$${minVal.toLocaleString()} - $${maxVal.toLocaleString()}</span>
                    </li>
                `;
            } else {
                // Fallback for non-array or non-numeric data
                html += `
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        ${methodName}
                        <span class="badge bg-secondary">Available</span>
                    </li>
                `;
            }
        });

        html += `
                    </ul>
                </div>
            </div>
        `;

        summaryDiv.innerHTML = html;
    }

    displayDataTable(results) {
        const dataDiv = document.getElementById('forecastData');
        
        if (!dataDiv) {
            console.error('forecastData element not found');
            return;
        }
        
        // Create table with forecast results
        const forecastLength = results.point_forecast ? results.point_forecast.length : 
                              results.enhanced_forecast ? results.enhanced_forecast.length : 0;

        if (forecastLength === 0) {
            dataDiv.innerHTML = '<p>No forecast data available.</p>';
            return;
        }

        let html = `
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Period</th>
        `;

        Object.keys(results).forEach(method => {
            if (method !== 'prediction_intervals') {
                const methodName = method.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                html += `<th>${methodName}</th>`;
            }
        });

        html += `</tr></thead><tbody>`;

        for (let i = 0; i < forecastLength; i++) {
            html += `<tr><td>${i + 1}</td>`;
            
            Object.entries(results).forEach(([method, values]) => {
                if (method !== 'prediction_intervals' && Array.isArray(values)) {
                    const value = values[i];
                    html += `<td>$${value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
                }
            });
            
            html += '</tr>';
        }

        html += '</tbody></table></div>';
        dataDiv.innerHTML = html;
    }

    async generateVisualization(result) {
        console.log('generateVisualization called with result:', result);
        console.log('Visualization data:', result.visualization_data);
        console.log('Historical data length:', result.visualization_data?.historical_data?.length);
        console.log('Historical dates length:', result.visualization_data?.dates_historical?.length);
        console.log('Target name:', result.visualization_data?.target_name);
        this.showLoading('Generating Chart', 'Creating professional forecast visualization...');

        try {
            const response = await fetch('/api/visualize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    visualization_data: result.visualization_data,
                    results: result.results,
                    quantile_indices: (function(){
                        let t = Array.from(document.querySelectorAll('.quantile-tick'))
                            .filter(cb => cb.checked)
                            .map(cb => parseInt(cb.value))
                            .sort((a,b) => a-b);
                        console.log('generateVisualization - quantile indices being sent:', t);
                        console.log('generateVisualization - number of quantiles:', t.length);
                        // Don't set default quantiles - pass empty array if none selected
                        return t;
                    })()
                })
            });

            const vizResult = await response.json();
            
            console.log('Visualization result received:', vizResult);
            console.log('Visualization success:', vizResult.success);
            if (vizResult.figure) {
                console.log('Figure data type:', typeof vizResult.figure);
                if (typeof vizResult.figure === 'string') {
                    console.log('Figure string length:', vizResult.figure.length);
                } else {
                    console.log('Figure object keys:', Object.keys(vizResult.figure));
                    if (vizResult.figure.data) {
                        console.log('Figure data traces:', vizResult.figure.data.length);
                        vizResult.figure.data.forEach((trace, i) => {
                            console.log(`Trace ${i}: name='${trace.name}', type='${trace.type}', visible=${trace.visible}`);
                            if (trace.y) {
                                console.log(`Trace ${i} y-data length: ${trace.y.length || 'scalar'}`);
                            }
                        });
                    }
                }
            }

            if (vizResult.success) {
                if (typeof Plotly === 'undefined') {
                    console.error('Plotly library not found on window');
                    this.showAlert('danger', 'Visualization Error', 'Plotly library is not loaded.');
                    return;
                }

                const chartContainer = document.getElementById('forecastChart');

                if (!chartContainer) {
                    console.error('Chart container element not found!');
                    this.showAlert('danger', 'Display Error', 'Chart display element not found');
                    return;
                }

                const figurePayload = typeof vizResult.figure === 'string'
                    ? JSON.parse(vizResult.figure)
                    : (vizResult.figure || {});

                if (!figurePayload.data || !Array.isArray(figurePayload.data) || figurePayload.data.length === 0) {
                    console.error('Figure payload missing data:', figurePayload);
                    this.currentPlotFigure = null;
                    this.currentPlotConfig = null;
                    this.showAlert('warning', 'Visualization Failed', 'Received empty plot data.');
                    return;
                }

                const defaultConfig = { 
                    responsive: true, 
                    displaylogo: false,
                    autosizable: true
                };
                const plotConfig = Object.assign({}, defaultConfig, vizResult.config || {});
                const layout = Object.assign({}, figurePayload.layout || {}, { 
                    autosize: true,
                    width: null,
                    height: null
                });

                try {
                    await Plotly.react(chartContainer, figurePayload.data, layout, plotConfig);
                    chartContainer.style.display = 'block';
                    
                    // Make chart responsive to window resize with debouncing
                    window.addEventListener('resize', () => {
                        clearTimeout(this.resizeTimeout);
                        this.resizeTimeout = setTimeout(() => {
                            if (typeof Plotly !== 'undefined' && chartContainer) {
                                Plotly.Plots.resize(chartContainer);
                            }
                        }, 250);
                    });

                    // Cache the latest figure/config for downloads and refreshes
                    this.currentPlotFigure = Object.assign({}, figurePayload, { layout });
                    this.currentPlotConfig = plotConfig;

                    const resultsCard = document.getElementById('resultsCard');
                    if (resultsCard) {
                        resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                } catch (plotlyError) {
                    console.error('Plotly rendering failed:', plotlyError);
                    this.currentPlotFigure = null;
                    this.currentPlotConfig = null;
                    this.showAlert('danger', 'Visualization Error', 'Failed to render interactive chart.');
                }
            } else {
                console.error('Visualization failed:', vizResult.message);
                this.currentPlotFigure = null;
                this.currentPlotConfig = null;
                this.showAlert('warning', 'Visualization Failed', vizResult.message || 'Failed to generate chart');
            }
        } catch (error) {
            this.currentPlotFigure = null;
            this.currentPlotConfig = null;
            this.showAlert('danger', 'Chart Error', 'Failed to generate visualization: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    downloadChart() {
        const chartContainer = document.getElementById('forecastChart');

        if (!chartContainer || !this.currentPlotFigure) {
            this.showAlert('warning', 'No Chart', 'No chart available for download.');
            return;
        }

        if (typeof Plotly === 'undefined') {
            this.showAlert('danger', 'Download Error', 'Plotly library is not available.');
            return;
        }

        const filename = `sapheneia_forecast_${new Date().toISOString().slice(0, 10)}`;

        Plotly.downloadImage(chartContainer, {
            format: 'png',
            filename,
            width: this.currentPlotFigure.layout?.width || 1200,
            height: this.currentPlotFigure.layout?.height || 800
        })
            .then(() => {
                this.showAlert('success', 'Download Started', 'Chart download has started.');
            })
            .catch((error) => {
                console.error('Plotly download failed:', error);
                this.showAlert('danger', 'Download Error', 'Failed to download chart image.');
            });
    }

    downloadData() {
        if (!this.currentResults || !this.currentResults.results) {
            this.showAlert('warning', 'No Data', 'No forecast data available for download.');
            return;
        }

        const results = this.currentResults.results;
        const vizData = this.currentResults.visualization_data || {};
        const forecastLength = results.point_forecast ? results.point_forecast.length :
                              results.enhanced_forecast ? results.enhanced_forecast.length : 0;

        if (forecastLength === 0) {
            this.showAlert('warning', 'No Data', 'No forecast data available for download.');
            return;
        }

        // Get future dates from visualization data
        const datesFuture = vizData.dates_future || [];

        // Create CSV content
        let csvContent = 'Date,Point_Forecast';

        // Add raw quantile columns (skip index 0 - legacy mean)
        if (results.quantile_forecast && Array.isArray(results.quantile_forecast)) {
            const numQuantiles = results.quantile_forecast[0] ? results.quantile_forecast[0].length : 0;
            // Skip index 0 (legacy mean), add Q10, Q20, Q30, Q40, Q50, Q60, Q70, Q80, Q90
            for (let i = 1; i < numQuantiles; i++) {
                const percentile = i * 10; // 1->Q10, 2->Q20, etc.
                csvContent += `,Q${percentile}`;
            }
        }

        // Only include Date, Point_Forecast, and Q10-Q90 columns
        // No additional columns needed

        csvContent += '\n';

        // Add data rows
        for (let i = 0; i < forecastLength; i++) {
            // Use actual date if available, otherwise fall back to period number
            const dateValue = (datesFuture && datesFuture[i]) ?
                              datesFuture[i].split('T')[0] : // Extract date part from ISO format
                              `${i + 1}`;
            csvContent += `${dateValue}`;

            // Point forecast
            const pointForecast = results.enhanced_forecast || results.point_forecast;
            csvContent += `,${pointForecast[i]}`;

            // Raw quantiles (skip index 0 - legacy mean)
            if (results.quantile_forecast && Array.isArray(results.quantile_forecast)) {
                const quantileRow = results.quantile_forecast[i];
                if (quantileRow && Array.isArray(quantileRow)) {
                    // Skip index 0, add Q10, Q20, Q30, Q40, Q50, Q60, Q70, Q80, Q90
                    for (let j = 1; j < quantileRow.length; j++) {
                        csvContent += `,${quantileRow[j]}`;
                    }
                }
            }

            // Only include Date, Point_Forecast, and Q10-Q90 data
            // No additional data needed

            csvContent += '\n';
        }

        // Create and download file
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `sapheneia_forecast_data_${new Date().toISOString().slice(0, 10)}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.showAlert('success', 'Download Started', 'Forecast data download has started.');
    }

    setupTabSwitching() {
        // Store scroll position when switching away from visualization tab
        const visualizationTab = document.getElementById('visualization-tab');
        const summaryTab = document.getElementById('summary-tab');
        const dataTab = document.getElementById('data-tab');
        
        // Store scroll position when leaving visualization tab
        visualizationTab.addEventListener('hidden.bs.tab', () => {
            this.visualizationScrollPosition = window.pageYOffset;
        });
        
        // Restore scroll position when returning to visualization tab
        visualizationTab.addEventListener('shown.bs.tab', () => {
            if (this.visualizationScrollPosition !== undefined) {
                setTimeout(() => {
                    window.scrollTo(0, this.visualizationScrollPosition);
                }, 100); // Small delay to ensure content is rendered
            }
            
            // Resize chart when visualization tab is shown
            if (this.currentPlotFigure && typeof Plotly !== 'undefined') {
                setTimeout(() => {
                    Plotly.Plots.resize(document.getElementById('forecastChart'));
                }, 200);
            }
        });
        
        // Store scroll position when leaving summary tab
        summaryTab.addEventListener('hidden.bs.tab', () => {
            this.summaryScrollPosition = window.pageYOffset;
        });
        
        // Restore scroll position when returning to summary tab
        summaryTab.addEventListener('shown.bs.tab', () => {
            if (this.summaryScrollPosition !== undefined) {
                setTimeout(() => {
                    window.scrollTo(0, this.summaryScrollPosition);
                }, 100);
            }
        });
        
        // Store scroll position when leaving data tab
        dataTab.addEventListener('hidden.bs.tab', () => {
            this.dataScrollPosition = window.pageYOffset;
        });
        
        // Restore scroll position when returning to data tab
        dataTab.addEventListener('shown.bs.tab', () => {
            if (this.dataScrollPosition !== undefined) {
                setTimeout(() => {
                    window.scrollTo(0, this.dataScrollPosition);
                }, 100);
            }
        });
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.sapheneiaApp = new SapheneiaTimesFM();
});
