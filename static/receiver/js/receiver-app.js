/**
 * SatsRemit Receiver Verification App
 * Allows receivers to verify they received transfers via PIN
 */

const API_BASE = '/api';
let currentTransfer = null;

// ===== PAGE NAVIGATION =====

function show_page(page_id) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    // Show target page
    document.getElementById(page_id).classList.add('active');
}

function go_back() {
    if (currentTransfer) {
        show_page('verify-page');
    } else {
        show_page('lookup-page');
    }
}

function continue_to_verify() {
    show_page('verify-page');
    // Focus PIN input
    setTimeout(() => {
        document.getElementById('pin').focus();
    }, 100);
}

function start_over() {
    currentTransfer = null;
    document.getElementById('lookup-form').reset();
    document.getElementById('verify-form').reset();
    show_page('lookup-page');
}

// ===== LOOKUP TRANSFER =====

async function handle_lookup(event) {
    event.preventDefault();

    const reference = document.getElementById('lookup-reference').value.toUpperCase();
    const phone = document.getElementById('lookup-phone').value;

    if (!reference || !phone) {
        show_alert('Please enter both reference and phone', 'error');
        return;
    }

    try {
        show_spinner(true);

        const response = await fetch(
            `${API_BASE}/receivers/transfers/${reference}/status?phone=${encodeURIComponent(phone)}`
        );

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Transfer not found');
        }

        const transfer = await response.json();
        currentTransfer = transfer;

        // Display transfer status
        display_transfer_status(transfer);
        show_page('status-page');
    } catch (error) {
        show_alert(error.message, 'error');
    } finally {
        show_spinner(false);
    }
}

function display_transfer_status(transfer) {
    const statusContent = document.getElementById('status-content');
    const verifiedBadge = transfer.receiver_phone_verified 
        ? '<span class="status-badge verified">✓ Your Phone Verified</span>'
        : '<span class="status-badge pending">Awaiting Your PIN</span>';

    const agentBadge = transfer.agent_verified
        ? '<span class="status-badge verified">✓ Agent Verified</span>'
        : '<span class="status-badge pending">Awaiting Agent</span>';

    const stateText = {
        'INITIATED': 'Transfer initiated',
        'INVOICE_GENERATED': 'Invoice generated',
        'PAYMENT_LOCKED': 'Payment received',
        'RECEIVER_VERIFIED': 'Receiver verified',
        'PAYOUT_EXECUTED': 'Payment processing',
        'SETTLED': 'Complete',
    };

    statusContent.innerHTML = `
        <div class="transfer-details">
            <div class="detail-row">
                <span class="detail-label">Reference:</span>
                <span class="detail-value">${transfer.reference}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Receiver:</span>
                <span class="detail-value">${transfer.receiver_name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Amount:</span>
                <span class="detail-value">ZAR ${parseFloat(transfer.amount_zar).toFixed(2)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span>${stateText[transfer.state] || transfer.state}</span>
            </div>
        </div>

        <div style="margin: 20px 0;">
            <div style="margin-bottom: 10px;">
                ${verifiedBadge}
            </div>
            <div>
                ${agentBadge}
            </div>
        </div>
    `;

    // Update continue button
    const continueBtn = document.getElementById('continue-btn');
    if (transfer.receiver_phone_verified) {
        continueBtn.disabled = true;
        continueBtn.textContent = 'Already Verified ✓';
    }
}

// ===== VERIFY PIN =====

async function handle_verify(event) {
    event.preventDefault();

    if (!currentTransfer) {
        show_alert('Transfer not found', 'error');
        return;
    }

    const pin = document.getElementById('pin').value;
    if (pin.length !== 4) {
        show_alert('Please enter a 4-digit PIN', 'error');
        return;
    }

    try {
        show_spinner(true);
        const verifyBtn = document.getElementById('verify-btn');
        verifyBtn.disabled = true;
        verifyBtn.innerHTML = '<span class="spinner"></span>Verifying...';

        const response = await fetch(`${API_BASE}/receivers/verify-pin`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                reference: currentTransfer.reference,
                phone: currentTransfer.receiver_phone || document.getElementById('lookup-phone').value,
                pin: pin,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Verification failed');
        }

        const result = await response.json();

        if (result.verified) {
            display_success(result);
            show_page('success-page');
        } else {
            show_alert(result.message, 'error');
        }
    } catch (error) {
        show_alert(error.message, 'error');
    } finally {
        show_spinner(false);
        const verifyBtn = document.getElementById('verify-btn');
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = 'Verify';
    }
}

function display_success(result) {
    const successContent = document.getElementById('success-content');
    successContent.innerHTML = `
        <div class="detail-row">
            <span class="detail-label">Reference:</span>
            <span class="detail-value">${result.transfer_id}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Receiver:</span>
            <span class="detail-value">${result.receiver_name}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Amount:</span>
            <span class="detail-value">ZAR ${parseFloat(result.amount_zar).toFixed(2)}</span>
        </div>
    `;
}

// ===== PIN RESEND =====

async function request_resend(event) {
    event.preventDefault();

    if (!currentTransfer) {
        show_alert('Transfer not found', 'error');
        return;
    }

    try {
        show_spinner(true);

        const response = await fetch(`${API_BASE}/receivers/resend-pin`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                reference: currentTransfer.reference,
                phone: document.getElementById('lookup-phone').value,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to resend PIN');
        }

        const result = await response.json();
        show_alert('PIN resent! Check your WhatsApp messages', 'success');
        
        // Clear PIN input
        document.getElementById('pin').value = '';
        document.getElementById('pin').focus();
    } catch (error) {
        show_alert(error.message, 'error');
    } finally {
        show_spinner(false);
    }
}

// ===== UTILITIES =====

function show_alert(message, type = 'info') {
    const alert = document.getElementById('alert');
    
    const colors = {
        'success': '#27ae60',
        'error': '#e74c3c',
        'info': '#3498db',
        'warning': '#f39c12',
    };

    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'info': 'fa-info-circle',
        'warning': 'fa-warning',
    };

    alert.innerHTML = `
        <div style="
            background: white;
            padding: 16px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-left: 4px solid ${colors[type]};
            display: flex;
            align-items: center;
            gap: 12px;
            max-width: 400px;
            animation: slideInRight 0.3s ease-out;
        ">
            <i class="fas ${icons[type]}" style="color: ${colors[type]}; font-size: 18px;"></i>
            <span style="color: #333;">${message}</span>
        </div>
    `;

    alert.style.display = 'block';

    // Auto-hide after 5 seconds
    setTimeout(() => {
        alert.style.display = 'none';
    }, 5000);
}

function show_spinner(show) {
    // Could be implemented if there's a global spinner
}

// Auto-format PIN input
document.addEventListener('DOMContentLoaded', function() {
    const pinInput = document.getElementById('pin');
    if (pinInput) {
        pinInput.addEventListener('input', function(e) {
            // Only allow digits
            this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        });

        pinInput.addEventListener('keypress', function(e) {
            // Allow enter to submit
            if (e.key === 'Enter' && this.value.length === 4) {
                document.getElementById('verify-form').dispatchEvent(new Event('submit'));
            }
        });
    }
});

// Auto-uppercase reference input
document.addEventListener('DOMContentLoaded', function() {
    const referenceInput = document.getElementById('lookup-reference');
    if (referenceInput) {
        referenceInput.addEventListener('input', function(e) {
            this.value = this.value.toUpperCase();
        });
    }
});
