/**
 * PDF Comparison Frontend Application
 */

// State management
let currentJobId = null;
let pollInterval = null;

// Provider configuration
const PROVIDER_CONFIG = {
    openai: {
        modelPlaceholder: 'gpt-4-turbo-preview',
        modelHint: 'Examples: gpt-4, gpt-4-turbo-preview, gpt-3.5-turbo',
        apiKeyPlaceholder: 'sk-...'
    },
    anthropic: {
        modelPlaceholder: 'claude-3-sonnet-20240229',
        modelHint: 'Examples: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307',
        apiKeyPlaceholder: 'sk-ant-...'
    },
    gemini: {
        modelPlaceholder: 'gemini-1.5-pro',
        modelHint: 'Examples: gemini-1.5-pro, gemini-1.5-flash, gemini-pro',
        apiKeyPlaceholder: 'AIza...'
    },
    custom: {
        modelPlaceholder: 'your-model-name',
        modelHint: 'Enter the model name for your custom endpoint',
        apiKeyPlaceholder: 'your-api-key'
    }
};

// DOM Elements
const elements = {
    form: document.getElementById('comparisonForm'),
    sourcePdf: document.getElementById('sourcePdf'),
    copyPdf: document.getElementById('copyPdf'),
    sourceLabel: document.getElementById('sourceLabel'),
    copyLabel: document.getElementById('copyLabel'),
    llmProvider: document.getElementById('llmProvider'),
    apiKey: document.getElementById('apiKey'),
    modelName: document.getElementById('modelName'),
    temperature: document.getElementById('temperature'),
    tempValue: document.getElementById('tempValue'),
    customEndpointSection: document.getElementById('customEndpointSection'),
    customEndpoint: document.getElementById('customEndpoint'),
    maxTokens: document.getElementById('maxTokens'),
    modelHint: document.getElementById('modelHint'),
    submitBtn: document.getElementById('submitBtn'),
    progressSection: document.getElementById('progressSection'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    resultsSection: document.getElementById('resultsSection'),
    summaryContent: document.getElementById('summaryContent'),
    downloadBtn: document.getElementById('downloadBtn'),
    errorSection: document.getElementById('errorSection'),
    errorMessage: document.getElementById('errorMessage')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Load saved config from localStorage
    loadSavedConfig();

    // Setup event listeners
    elements.sourcePdf.addEventListener('change', (e) => updateFileLabel(e, elements.sourceLabel));
    elements.copyPdf.addEventListener('change', (e) => updateFileLabel(e, elements.copyLabel));
    elements.llmProvider.addEventListener('change', handleProviderChange);
    elements.temperature.addEventListener('input', handleTemperatureChange);
    elements.form.addEventListener('submit', handleFormSubmit);
    elements.downloadBtn.addEventListener('click', handleDownload);

    // Initialize provider-specific UI
    handleProviderChange();
}

function updateFileLabel(event, label) {
    const file = event.target.files[0];
    if (file) {
        label.textContent = `✓ ${file.name}`;
        label.classList.add('has-file');
    }
}

function handleProviderChange() {
    const provider = elements.llmProvider.value;
    const config = PROVIDER_CONFIG[provider];

    // Update placeholders and hints
    elements.modelName.placeholder = config.modelPlaceholder;
    elements.modelHint.textContent = config.modelHint;
    elements.apiKey.placeholder = config.apiKeyPlaceholder;

    // Show/hide custom endpoint field
    if (provider === 'custom') {
        elements.customEndpointSection.classList.remove('hidden');
        elements.customEndpoint.required = true;
    } else {
        elements.customEndpointSection.classList.add('hidden');
        elements.customEndpoint.required = false;
    }

    // Save provider choice
    localStorage.setItem('lastProvider', provider);
}

function handleTemperatureChange() {
    const value = elements.temperature.value;
    elements.tempValue.textContent = value;
}

function loadSavedConfig() {
    const lastProvider = localStorage.getItem('lastProvider');
    if (lastProvider) {
        elements.llmProvider.value = lastProvider;
        handleProviderChange();
    }

    const lastModel = localStorage.getItem('lastModel');
    if (lastModel) {
        elements.modelName.value = lastModel;
    }

    const lastTemp = localStorage.getItem('lastTemperature');
    if (lastTemp) {
        elements.temperature.value = lastTemp;
        handleTemperatureChange();
    }
}

function saveConfig() {
    localStorage.setItem('lastProvider', elements.llmProvider.value);
    localStorage.setItem('lastModel', elements.modelName.value);
    localStorage.setItem('lastTemperature', elements.temperature.value);
}

async function handleFormSubmit(event) {
    event.preventDefault();

    // Clear previous errors
    hideError();
    hideResults();

    // Validate files
    if (!elements.sourcePdf.files[0] || !elements.copyPdf.files[0]) {
        showError('Please select both PDF files');
        return;
    }

    // Save config
    saveConfig();

    // Prepare form data
    const formData = new FormData();
    formData.append('source_file', elements.sourcePdf.files[0]);
    formData.append('copy_file', elements.copyPdf.files[0]);

    // Prepare LLM config
    const llmConfig = {
        provider: elements.llmProvider.value,
        api_key: elements.apiKey.value,
        model: elements.modelName.value,
        temperature: parseFloat(elements.temperature.value),
        max_tokens: parseInt(elements.maxTokens.value) || 4000
    };

    if (elements.llmProvider.value === 'custom') {
        llmConfig.custom_endpoint = elements.customEndpoint.value;
    }

    formData.append('llm_config', JSON.stringify(llmConfig));

    // Disable form
    elements.submitBtn.disabled = true;
    elements.submitBtn.textContent = 'Uploading...';

    try {
        // Start comparison
        const response = await fetch('/api/compare', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start comparison');
        }

        const result = await response.json();
        currentJobId = result.job_id;

        // Show progress section
        showProgress();

        // Start polling for status
        startPolling();

    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
        elements.submitBtn.disabled = false;
        elements.submitBtn.textContent = 'Start Comparison';
    }
}

function showProgress() {
    elements.progressSection.classList.remove('hidden');
    elements.resultsSection.classList.add('hidden');
}

function hideProgress() {
    elements.progressSection.classList.add('hidden');
}

function showResults() {
    elements.resultsSection.classList.remove('hidden');
}

function hideResults() {
    elements.resultsSection.classList.add('hidden');
}

function showError(message) {
    elements.errorSection.classList.remove('hidden');
    elements.errorMessage.textContent = message;
}

function hideError() {
    elements.errorSection.classList.add('hidden');
}

function startPolling() {
    // Poll every 2 seconds
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${currentJobId}`);

            if (!response.ok) {
                throw new Error('Failed to fetch job status');
            }

            const status = await response.json();

            // Update progress
            updateProgress(status.progress, status.current_step);

            // Check if completed
            if (status.status === 'completed') {
                clearInterval(pollInterval);
                await handleCompletion();
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                hideProgress();
                showError(status.error || 'Comparison failed');
                resetForm();
            }

        } catch (error) {
            console.error('Polling error:', error);
            clearInterval(pollInterval);
            hideProgress();
            showError('Lost connection to server');
            resetForm();
        }
    }, 2000);
}

function updateProgress(progress, step) {
    elements.progressFill.style.width = `${progress}%`;
    elements.progressText.textContent = step || `Processing... ${progress}%`;
}

async function handleCompletion() {
    try {
        // Fetch results
        const response = await fetch(`/api/result/${currentJobId}`);

        if (!response.ok) {
            throw new Error('Failed to fetch results');
        }

        const result = await response.json();

        // Hide progress, show results
        hideProgress();
        displayResults(result);
        showResults();
        resetForm();

    } catch (error) {
        console.error('Error fetching results:', error);
        showError('Failed to load results');
        resetForm();
    }
}

function displayResults(result) {
    const summary = result.summary;

    const html = `
        <div class="result-item">
            <span class="result-label">Total Pages:</span> ${summary.total_pages}
        </div>
        <div class="result-item">
            <span class="result-label">Pages with Differences:</span> ${summary.pages_with_differences}
        </div>
        <div class="result-item">
            <span class="result-label">Similarity Score:</span> ${summary.similarity_score}%
        </div>
        <div class="result-item">
            <span class="result-label">LLM Used:</span> ${summary.llm_used}
        </div>
        <div class="result-item">
            <span class="result-label">Differences Found:</span> ${result.differences.length}
        </div>
        <div class="result-item">
            <span class="result-label">Methodology:</span>
            <p style="margin-top: 8px; color: #666; font-size: 14px;">${summary.methodology}</p>
        </div>
    `;

    elements.summaryContent.innerHTML = html;

    // Store job ID for download
    elements.downloadBtn.dataset.jobId = currentJobId;
}

function handleDownload() {
    const jobId = elements.downloadBtn.dataset.jobId;
    if (jobId) {
        window.open(`/api/download/${jobId}`, '_blank');
    }
}

function resetForm() {
    elements.submitBtn.disabled = false;
    elements.submitBtn.textContent = 'Start Comparison';
}
