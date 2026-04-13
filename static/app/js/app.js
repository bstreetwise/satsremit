/**
 * SatsRemit User Application
 * Main application logic and flow management
 */

console.log('=== APP.JS LOADED AT', new Date().toISOString(), '===');

const APP_STATE = {
    currentTransfer: null,
    userPhone: localStorage.getItem('user_phone') || null,
};

// ===== INITIALIZATION =====

document.addEventListener('DOMContentLoaded', async function () {
    init_navigation();
    init_event_listeners();

    // Check service health
    try {
        await API.getHealth();
    } catch (error) {
        show_alert('Service unavailable - please try again later', 'error');
    }

    // Navigate to home if not already navigated
    if (!window.location.hash) {
        navigate_to_page('home');
    }
});

// ===== NAVIGATION =====

function init_navigation() {
    // Handle hash-based routing
    window.addEventListener('hashchange', () => {
        const page = window.location.hash.substring(1) || 'home';
        navigate_to_page(page);
    });

    // Initial navigation from hash
    const initialPage = window.location.hash.substring(1) || 'home';
    navigate_to_page(initialPage);
}

function navigate_to_page(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => {
        p.style.display = 'none';
        p.classList.remove('active');
    });

    // Show requested page
    const pageElement = document.getElementById(`page-${page}`);
    if (pageElement) {
        pageElement.style.display = 'block';
        pageElement.classList.add('active');

        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        const activeLink = document.querySelector(`[href="#${page}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }

        // Load page-specific content
        if (page === 'transfer') {
            load_transfer_page();
        } else if (page === 'status') {
            load_status_page();
        } else if (page === 'history') {
            load_history_page();
        }
    }
}

// ===== EVENT LISTENERS =====

function init_event_listeners() {
    // Transfer form submission
    const transferForm = document.getElementById('transfer-form');
    if (transferForm) {
        transferForm.addEventListener('submit', handle_transfer_submit);
    }

    // Phone input - save to localStorage
    const phoneInput = document.getElementById('sender-phone');
    if (phoneInput) {
        phoneInput.addEventListener('change', (e) => {
            APP_STATE.userPhone = e.target.value;
            localStorage.setItem('user_phone', e.target.value);
        });
    }

    // Amount input - fetch quote on blur only
    const amountInput = document.getElementById('amount-zar');
    if (amountInput) {
        // Silently handle input (no validation)
        amountInput.addEventListener('input', (e) => {
            // Optional: show preview of amount, but don't validate yet
        });
        
        // Validate and fetch quote when user leaves the field
        amountInput.addEventListener('blur', async (e) => {
            await update_quote_display();
        });
    }

    // Location selector
    const locationSelect = document.getElementById('receiver-location');
    if (locationSelect) {
        locationSelect.addEventListener('change', () => {
            update_quote_display();
        });
    }

    // Homepage Quote Calculator
    const homepageAmountInput = document.getElementById('homepage-amount-send');
    const homepageLocationSelect = document.getElementById('homepage-location');
    if (homepageAmountInput) {
        homepageAmountInput.addEventListener('input', () => {
            update_homepage_quote();
        });
    }
    if (homepageLocationSelect) {
        homepageLocationSelect.addEventListener('change', () => {
            update_homepage_quote();
        });
    }
}

// ===== TRANSFER FORM HANDLING =====

async function load_transfer_page() {
    console.log('*** LOAD_TRANSFER_PAGE CALLED ***');
    
    const phoneInput = document.getElementById('sender-phone');
    if (phoneInput && APP_STATE.userPhone) {
        phoneInput.value = APP_STATE.userPhone;
    }
    
    // Setup amount input blur listener for quote calculation
    const amountInput = document.getElementById('amount-zar');
    console.log('Amount input element found?', !!amountInput);
    
    if (amountInput) {
        console.log('Setting up blur listener on amount input');
        
        // Add blur listener for quote fetch
        amountInput.addEventListener('blur', async (e) => {
            console.log('*** BLUR EVENT TRIGGERED on amount input ***');
            await update_quote_display();
        });
    }
    
    update_quote_display();
}

async function update_quote_display() {
    const amountInput = document.getElementById('amount-zar');
    const quoteDisplay = document.getElementById('quote-display');
    const receiverAmount = parseFloat(amountInput.value);

    console.log('=== UPDATE_QUOTE_DISPLAY CALLED ===');
    console.log('Receiver amount entered:', receiverAmount);

    if (!receiverAmount || receiverAmount <= 0) {
        if (quoteDisplay) {
            quoteDisplay.innerHTML = '<p class="text-muted">Enter an amount to see fees and payment total</p>';
        }
        return;
    }

    try {
        // Calculate sender amount needed from receiver amount
        // Formula: sender_amount = receiver_amount / (1 - total_fee_percent)
        // Total fee is 1% (0.5% platform + 0.5% commission)
        const TOTAL_FEE_PERCENT = 0.01;  // 1%
        const senderAmount = receiverAmount / (1 - TOTAL_FEE_PERCENT);
        
        console.log('CALCULATION: Receiver=' + receiverAmount + ', Sender to pay=' + senderAmount.toFixed(2));
        console.log('Calling API.getQuote with sender amount:', senderAmount);
        
        // Fetch quote using sender amount
        const quote = await API.getQuote(senderAmount);
        console.log('Quote received - amount_zar (what API got):', quote.amount_zar, 'receiver_gets_zar:', quote.receiver_gets_zar);
        display_quote(quote, receiverAmount);
    } catch (error) {
        // Show validation error inline, not as alert
        let errorMsg = error.message;
        if (error.response?.detail) errorMsg = error.response.detail;
        console.error('Quote error:', error);
        if (quoteDisplay) {
            quoteDisplay.innerHTML = `<p style="color: #d32f2f; font-weight: 500; margin: 1rem 0;">${errorMsg}</p>`;
        }
    }
}

function display_quote(quote, requestedReceiverAmount = null) {
    const quoteDisplay = document.getElementById('quote-display');
    const receiverAmount = requestedReceiverAmount || (parseFloat(document.getElementById('amount-zar').value) || quote.receiver_gets_zar);
    
    console.log('DISPLAY_QUOTE:', 'requested=', requestedReceiverAmount, 'final=', receiverAmount, 'quote.amount_zar=', quote.amount_zar);
    
    quoteDisplay.innerHTML = `
        <div class="quote-card">
            <div class="quote-row" style="background: #e8f5e9; padding: 0.75rem; border-radius: 4px;">
                <label style="font-weight: 600; color: #2e7d32;">RECIPIENT GETS:</label>
                <span style="color: #2e7d32; font-size: 1.1rem; font-weight: 600;">${format_currency(receiverAmount)}</span>
            </div>
            <div class="quote-row">
                <label>Exchange rate:</label>
                <span>1 USD = ${parseFloat(quote.rate_usd_per_zar).toFixed(2)} ZAR</span>
            </div>
            <div class="divider"></div>
            <div class="quote-row">
                <label style="color: #666;">Total fees (1.0%):</label>
                <span style="color: #666;">${format_currency(quote.total_fees_zar)}</span>
            </div>
            <div class="divider"></div>
            <div class="quote-row total" style="background: #1976d2; padding: 1rem; border-radius: 4px; color: white; display: flex; justify-content: space-between; gap: 2rem;">
                <div style="flex: 1;">
                    <label style="font-weight: 600; font-size: 0.9rem; color: white; display: block;">YOU PAY:</label>
                    <span style="font-size: 1.3rem; color: white; font-weight: 600; display: block; margin-top: 0.5rem;">${format_currency(quote.amount_zar)}</span>
                </div>
                <div style="flex: 1;">
                    <label style="font-weight: 600; font-size: 0.9rem; color: white; display: block;">Amount to Send (Sats):</label>
                    <span style="font-size: 1.3rem; color: white; font-weight: 600; display: block; margin-top: 0.5rem;">${format_sats(quote.amount_sats)}</span>
                </div>
            </div>
        </div>
    `;
}

// ===== HOMEPAGE QUOTE CALCULATOR =====

async function update_homepage_quote() {
    const amountInput = document.getElementById('homepage-amount-send');
    const quoteResults = document.getElementById('homepage-quote-results');
    const errorMsg = document.getElementById('homepage-amount-error');
    const errorText = document.getElementById('homepage-amount-error-text');
    const amount = parseFloat(amountInput?.value);

    const MIN_AMOUNT = 100;
    const MAX_AMOUNT = 500;

    // Clear previous error message
    if (errorMsg) {
        errorMsg.style.display = 'none';
    }

    if (!amount || amount <= 0) {
        if (quoteResults) {
            quoteResults.style.display = 'none';
        }
        return;
    }

    // Validate amount is within allowed range
    if (amount < MIN_AMOUNT) {
        if (errorMsg && errorText) {
            errorText.textContent = `Amount too low. Please enter at least ZAR ${MIN_AMOUNT}`;
            errorMsg.style.display = 'block';
        }
        if (quoteResults) {
            quoteResults.style.display = 'none';
        }
        return;
    }

    if (amount > MAX_AMOUNT) {
        if (errorMsg && errorText) {
            errorText.textContent = `Amount too high. Maximum allowed is ZAR ${MAX_AMOUNT}`;
            errorMsg.style.display = 'block';
        }
        if (quoteResults) {
            quoteResults.style.display = 'none';
        }
        return;
    }

    try {
        // Fetch quote using sender amount
        const quote = await API.getQuote(amount);
        
        // Display quote results on homepage
        if (quoteResults) {
            const recipientAmount = parseFloat(quote.amount_zar);  // What recipient should get
            const totalFees = parseFloat(quote.total_fees_zar);      // Fee to add on top
            const totalToPay = recipientAmount + totalFees;          // Total sender pays
            const usdPerZar = parseFloat(quote.rate_usd_per_zar);
            const zarPerBtc = parseFloat(quote.rate_zar_per_btc);
            const amountSats = parseInt(quote.amount_sats);

            document.getElementById('homepage-receive-amount').textContent = format_currency(recipientAmount);
            document.getElementById('homepage-exchange-rate').textContent = `1 USD = ${usdPerZar.toFixed(2)} ZAR`;
            document.getElementById('homepage-btc-rate').textContent = `1 BTC = ${format_currency(zarPerBtc)}`;
            document.getElementById('homepage-total-fee').textContent = `${format_currency(totalFees)}`;
            document.getElementById('homepage-total-pay').textContent = `${format_currency(totalToPay)}`;
            document.getElementById('homepage-amount-sats').textContent = format_sats(amountSats);
            
            quoteResults.style.display = 'block';
        }
    } catch (error) {
        console.error('Homepage quote error:', error);
        if (errorMsg && errorText && error.response?.detail) {
            errorText.textContent = error.response.detail;
            errorMsg.style.display = 'block';
        }
        if (quoteResults) {
            quoteResults.style.display = 'none';
        }
    }
}

// ===== CALCULATOR TO FORM TRANSFER =====

function transfer_from_calculator() {
    // Get values from calculator
    const amount = document.getElementById('homepage-amount-send')?.value;
    const location = document.getElementById('homepage-location')?.value;
    
    // Validate calculator has values
    if (!amount || !location) {
        show_alert('Please enter amount and select location first', 'warning');
        return;
    }
    
    // Pre-fill the send form with calculator values
    const amountField = document.getElementById('amount-zar');
    const locationField = document.getElementById('receiver-location');
    
    if (amountField) {
        amountField.value = amount;
    }
    if (locationField) {
        locationField.value = location;
    }
    
    // Navigate to transfer section
    const transferLink = document.querySelector('[href="#transfer"]');
    if (transferLink) {
        transferLink.click();
        
        // After navigation, trigger quote calculation on the form
        setTimeout(async () => {
            await update_quote_display();
        }, 100);
    }
}

async function handle_transfer_submit(event) {
    event.preventDefault();

    const senderPhone = document.getElementById('sender-phone').value.trim();
    const receiverPhone = document.getElementById('receiver-phone').value.trim();
    const receiverName = document.getElementById('receiver-name').value.trim();
    const receiverLocation = document.getElementById('receiver-location').value;
    let amountZAR = parseFloat(document.getElementById('amount-zar').value);

    // Validation
    if (!senderPhone) {
        show_alert('Please enter your phone number', 'error');
        return;
    }
    if (!receiverPhone) {
        show_alert('Please enter recipient phone number', 'error');
        return;
    }
    if (!receiverName) {
        show_alert('Please enter recipient name', 'error');
        return;
    }
    if (!receiverLocation || receiverLocation === '') {
        show_alert('Please select recipient location', 'error');
        return;
    }
    if (!amountZAR || amountZAR <= 0) {
        show_alert('Please enter valid amount', 'error');
        return;
    }

    // Validate phone format (E.164 or local)
    const phoneRegex = /^(\+|0)[0-9\s\-()]{9,}$/;
    if (!phoneRegex.test(senderPhone)) {
        show_alert('Invalid sender phone format. Use format like +27123456789 or 0123456789', 'error');
        return;
    }
    if (!phoneRegex.test(receiverPhone)) {
        show_alert('Invalid recipient phone format. Use format like +263123456789 or 0123456789', 'error');
        return;
    }

    try {
        show_spinner(true);

        // Calculate sender amount from recipient amount
        // Formula: sender_amount = recipient_amount / (1 - total_fee_percent)
        // Total fee is 1% (0.5% platform + 0.5% commission)
        const TOTAL_FEE_PERCENT = 0.01;  // 1%
        const recipientAmount = amountZAR;
        const senderAmount = recipientAmount / (1 - TOTAL_FEE_PERCENT);

        // Ensure amount has exactly 2 decimal places
        amountZAR = Math.round(senderAmount * 100) / 100;

        // Debug: Log payload being sent
        const payload = {
            sender_phone: senderPhone,
            receiver_phone: receiverPhone,
            receiver_name: receiverName,
            receiver_location: receiverLocation,
            amount_zar: amountZAR,
        };
        console.log('Submitting transfer payload (sender pays, recipient gets ' + Math.round(recipientAmount * 100) / 100 + '):', payload);
        console.log('Sender amount to pay: ' + amountZAR + ', Recipient to receive: ' + Math.round(recipientAmount * 100) / 100);

        const response = await API.createTransfer(payload);

        // Store transfer details
        APP_STATE.currentTransfer = response;
        localStorage.setItem('current_transfer', JSON.stringify(response));

        // Navigate to payment page
        navigate_to_page('payment');
        load_payment_page();

    } catch (error) {
        console.error('Transfer submission error:', error);
        
        // Extract detailed error message
        let errorMsg = error.message || 'Unknown error';
        
        if (error.response && error.response.detail) {
            errorMsg = error.response.detail;
        } else if (error.response && error.response.error) {
            errorMsg = error.response.error;
        } else if (error.response && error.response.message) {
            errorMsg = error.response.message;
        }
        
        // Show error with HTTP status if available
        if (error.status) {
            errorMsg = `API Error (${error.status}): ${errorMsg}`;
        }
        
        show_alert(`Transfer failed: ${errorMsg}`, 'error');
    } finally {
        show_spinner(false);
    }
}

// ===== PAYMENT PAGE =====

function load_payment_page() {
    if (!APP_STATE.currentTransfer) {
        APP_STATE.currentTransfer = JSON.parse(localStorage.getItem('current_transfer'));
    }

    if (!APP_STATE.currentTransfer) {
        navigate_to_page('transfer');
        return;
    }

    const transfer = APP_STATE.currentTransfer;

    const paymentContainer = document.getElementById('payment-container');
    paymentContainer.innerHTML = `
        <div class="payment-card">
            <div class="payment-header">
                <h3>Pay Invoice</h3>
                <p class="reference">Reference: ${transfer.reference}</p>
            </div>

            <div class="payment-details">
                <div class="detail-row">
                    <label>Amount to pay:</label>
                    <span class="amount-sats">${format_sats(transfer.amount_sats)}</span>
                </div>
                <div class="detail-row">
                    <label>ZAR equivalent:</label>
                    <span>${format_currency(transfer.amount_zar)}</span>
                </div>
                <div class="detail-row">
                    <label>Recipient:</label>
                    <span>${transfer.agent_name} in ${transfer.agent_location}</span>
                </div>
                <div class="detail-row">
                    <label>Expires at:</label>
                    <span>${format_date(transfer.expires_at)}</span>
                </div>
            </div>

            <div class="invoice-section">
                <h4>Lightning Network Invoice</h4>
                <div class="invoice-qr" id="qr-code"></div>
                <div class="invoice-request">
                    <label>Invoice:</label>
                    <textarea readonly>${transfer.invoice_request}</textarea>
                    <button class="btn btn-secondary" onclick="copy_to_clipboard('${transfer.invoice_request}')">
                        <i class="fas fa-copy"></i> Copy
                    </button>
                </div>
                <div class="invoice-hash">
                    <small>Payment Hash: ${transfer.invoice_hash}</small>
                </div>
            </div>

            <div class="payment-instructions">
                <h4>How to pay:</h4>
                <ol>
                    <li>Open your Lightning wallet app</li>
                    <li>Select "Scan QR Code" or "Paste Invoice"</li>
                    <li>Scan the QR code or paste the invoice above</li>
                    <li>Confirm the amount and complete payment</li>
                    <li>Check your transfer status below</li>
                </ol>
            </div>

            <div class="payment-status">
                <h4>Payment Status</h4>
                <div id="payment-status-display" class="status-checking">
                    <p>Waiting for payment...</p>
                </div>
                <button class="btn btn-primary" onclick="check_payment_status()">
                    <i class="fas fa-sync-alt"></i> Check Status
                </button>
            </div>

            <div class="payment-actions">
                <button class="btn btn-secondary" onclick="navigate_to_page('transfer')">
                    <i class="fas fa-arrow-left"></i> Back to Transfer
                </button>
                <button class="btn btn-primary" onclick="view_transfer_status()">
                    <i class="fas fa-info-circle"></i> View Full Status
                </button>
            </div>
        </div>
    `;

    // Generate QR code
    generate_qr_code(transfer.invoice_request);

    // Auto-check payment status periodically (every 5 seconds)
    check_payment_status();
    
    // Clear any existing interval before setting new one
    if (window.paymentCheckInterval) {
        clearInterval(window.paymentCheckInterval);
    }
    window.paymentCheckInterval = setInterval(check_payment_status, 5000);
}

async function check_payment_status() {
    if (!APP_STATE.currentTransfer) return;

    try {
        const transfer = APP_STATE.currentTransfer;
        
        // Check invoice expiration
        if (new Date(transfer.expires_at) < new Date()) {
            show_alert('Invoice has expired. Please create a new transfer.', 'error');
            clearInterval(window.paymentCheckInterval);
            setTimeout(() => navigate_to_page('transfer'), 2000);
            return;
        }

        // Check if payment has actually been received via LND
        const paymentStatus = await API.checkPaymentReceived(transfer.transfer_id);
        
        // Only update DOM if status changed (prevents flicker)
        if (APP_STATE.lastPaymentState !== JSON.stringify(paymentStatus)) {
            display_payment_status(paymentStatus);
            APP_STATE.lastPaymentState = JSON.stringify(paymentStatus);
        }

        // If payment received, move to status page
        if (paymentStatus.payment_received) {
            show_alert('✓ Payment received! Transfer is being processed.', 'success');
            clearInterval(window.paymentCheckInterval);
            setTimeout(() => {
                navigate_to_page('status');
                load_status_page();
            }, 2000);
        }
    } catch (error) {
        console.error('Error checking payment status:', error);
    }
}

function display_payment_status(status) {
    const statusDisplay = document.getElementById('payment-status-display');
    if (!statusDisplay) return;

    const statusText = status.state.replace(/_/g, ' ').toLowerCase();
    const statusClass = status.state === 'PENDING' ? 'status-pending' : 'status-success';

    statusDisplay.className = statusClass;
    statusDisplay.innerHTML = `
        <div class="status-badge">
            <i class="fas fa-${status.state === 'PENDING' ? 'hourglass-half' : 'check-circle'}"></i>
            <p>${statusText}</p>
        </div>
        ${status.receiver_phone_verified ? '<p class="text-success">✓ Receiver verified</p>' : ''}
    `;
}

function generate_qr_code(invoiceRequest) {
    const qrContainer = document.getElementById('qr-code');
    if (!qrContainer) return;

    // Clear previous QR code if exists
    qrContainer.innerHTML = '';

    // Use qrcode.js library to generate QR code for Lightning invoice
    try {
        const qr = new QRCode(qrContainer, {
            text: invoiceRequest,
            width: 250,
            height: 250,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
        });
    } catch (error) {
        console.error('Failed to generate QR code:', error);
        show_alert('Failed to generate payment QR code', 'error');
    }
}

function view_transfer_status() {
    navigate_to_page('status');
    load_status_page();
}

// ===== STATUS PAGE =====

async function load_status_page() {
    if (!APP_STATE.currentTransfer) {
        APP_STATE.currentTransfer = JSON.parse(localStorage.getItem('current_transfer'));
    }

    if (!APP_STATE.currentTransfer) {
        navigate_to_page('transfer');
        return;
    }

    const transfer = APP_STATE.currentTransfer;

    try {
        show_spinner(true);
        const details = await API.getTransferDetails(transfer.transfer_id);
        display_transfer_status(details);
    } catch (error) {
        show_alert(`Error loading status: ${error.message}`, 'error');
    } finally {
        show_spinner(false);
    }
}

function display_transfer_status(transfer) {
    const statusContainer = document.getElementById('status-container');
    const stateClass = `status-${transfer.state.toLowerCase()}`;

    statusContainer.innerHTML = `
        <div class="status-card">
            <div class="status-header ${stateClass}">
                <h3>${transfer.state.replace(/_/g, ' ')}</h3>
                <p class="reference">${transfer.reference}</p>
            </div>

            <div class="status-timeline">
                ${generate_timeline(transfer)}
            </div>

            <div class="transfer-details">
                <h4>Transfer Details</h4>
                <div class="detail-row">
                    <label>Sender:</label>
                    <span>${transfer.sender_phone}</span>
                </div>
                <div class="detail-row">
                    <label>Receiver:</label>
                    <span>${transfer.receiver_name} (${transfer.receiver_phone})</span>
                </div>
                <div class="detail-row">
                    <label>Amount (ZAR):</label>
                    <span>${format_currency(transfer.amount_zar)}</span>
                </div>
                <div class="detail-row">
                    <label>Amount (satoshis):</label>
                    <span>${format_sats(transfer.amount_sats)}</span>
                </div>
                <div class="detail-row">
                    <label>Rate:</label>
                    <span>${format_currency(transfer.rate_zar_per_btc)} per BTC</span>
                </div>
                <div class="detail-row">
                    <label>Created:</label>
                    <span>${format_date(transfer.created_at)}</span>
                </div>
                ${transfer.payout_at ? `<div class="detail-row">
                    <label>Paid out:</label>
                    <span>${format_date(transfer.payout_at)}</span>
                </div>` : ''}
            </div>

            <div class="status-actions">
                <button class="btn btn-primary" onclick="navigate_to_page('transfer')">
                    <i class="fas fa-arrow-left"></i> Send Another
                </button>
                <button class="btn btn-secondary" onclick="navigate_to_page('history')">
                    <i class="fas fa-history"></i> View History
                </button>
            </div>
        </div>
    `;
}

function generate_timeline(transfer) {
    const steps = [
        { state: 'CREATED', label: 'Transfer Created', time: transfer.created_at },
        { state: 'PENDING', label: 'Awaiting Payment', time: transfer.created_at },
        { state: 'PAID', label: 'Payment Received', time: transfer.invoice_expiry_at },
        { state: 'SETTLED', label: 'Settled', time: transfer.settled_at },
    ];

    return steps.map(step => {
        const isComplete = steps.findIndex(s => s.state === transfer.state) >= steps.indexOf(step);
        const isCurrent = step.state === transfer.state;

        return `
            <div class="timeline-step ${isComplete ? 'complete' : ''} ${isCurrent ? 'current' : ''}">
                <div class="timeline-dot">
                    <i class="fas fa-check"></i>
                </div>
                <div class="timeline-content">
                    <p class="timeline-label">${step.label}</p>
                    ${step.time ? `<small>${format_date(step.time)}</small>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// ===== HISTORY PAGE =====

async function load_history_page() {
    const transfer = APP_STATE.currentTransfer;

    if (transfer) {
        try {
            show_spinner(true);
            const details = await API.getTransferDetails(transfer.transfer_id);
            display_history(details);
        } catch (error) {
            show_alert(`Error loading history: ${error.message}`, 'error');
        } finally {
            show_spinner(false);
        }
    } else {
        const historyContainer = document.getElementById('history-container');
        historyContainer.innerHTML = '<p class="text-muted">No transfer history yet</p>';
    }
}

function display_history(transfer) {
    const historyContainer = document.getElementById('history-container');

    historyContainer.innerHTML = `
        <div class="history-card">
            <div class="history-header">
                <h4>${transfer.receiver_name}</h4>
                <span class="badge badge-${transfer.state.toLowerCase()}">${transfer.state}</span>
            </div>
            <div class="history-details">
                <div class="detail-row">
                    <span>${transfer.receiver_phone}</span>
                    <span class="amount">${format_currency(transfer.amount_zar)}</span>
                </div>
                <small>${format_date(transfer.created_at)}</small>
            </div>
        </div>
    `;
}

// ===== UTILITY FUNCTIONS =====

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function copy_to_clipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        show_alert('Copied to clipboard!', 'success');
    });
}

// ===== FORMATTING FUNCTIONS =====

/**
 * Format ZAR currency amount
 */
function format_currency(amount) {
    const num = parseFloat(amount);
    if (isNaN(num)) return 'R0.00';
    return new Intl.NumberFormat('en-ZA', {
        style: 'currency',
        currency: 'ZAR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

/**
 * Format sats (satoshis) amount
 */
function format_sats(sats) {
    const num = parseInt(sats);
    if (isNaN(num)) return '0 sats';
    return new Intl.NumberFormat('en-US').format(num) + ' sats';
}

/**
 * Format BTC amount
 */
function format_btc(btc) {
    const num = parseFloat(btc);
    if (isNaN(num)) return '0.00000000 BTC';
    return num.toFixed(8) + ' BTC';
}

/**
 * Format date/time
 */
function format_date(dateString) {
    if (!dateString) return 'N/A';
    
    try {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-ZA', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        }).format(date);
    } catch (error) {
        console.error('Date formatting error:', error);
        return dateString;
    }
}

/**
 * Format time remaining (for invoice expiry)
 */
function format_time_remaining(expiresAt) {
    try {
        const now = new Date();
        const expiry = new Date(expiresAt);
        const remaining = expiry - now;

        if (remaining <= 0) {
            return 'Expired';
        }

        const hours = Math.floor(remaining / (1000 * 60 * 60));
        const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((remaining % (1000 * 60)) / 1000);

        if (hours > 0) {
            return `${hours}h ${minutes}m remaining`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds}s remaining`;
        } else {
            return `${seconds}s remaining`;
        }
    } catch (error) {
        console.error('Time formatting error:', error);
        return 'N/A';
    }
}
