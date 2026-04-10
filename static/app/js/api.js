/**
 * SatsRemit User API Module
 * Handles all API communication with the backend
 */

const API = {
    BASE_URL: '/api',

    /**
     * Generic API request handler
     */
    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const method = options.method || 'GET';
        const headers = {
            'Content-Type': 'application/json',
        };

        try {
            show_spinner(true);

            const response = await fetch(url, {
                method,
                headers,
                body: options.body ? JSON.stringify(options.body) : undefined,
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.error || 'API Error');
            }

            const data = await response.json();
            show_spinner(false);
            return data;
        } catch (error) {
            show_spinner(false);
            throw error;
        }
    },

    // ===== TRANSFERS =====

    /**
     * Get transfer quote
     */
    async getQuote(amountZAR) {
        return this.request('/transfers/quote', {
            method: 'POST',
            body: { amount_zar: amountZAR },
        });
    },

    /**
     * Initiate a new transfer
     */
    async createTransfer(transferData) {
        return this.request('/transfers', {
            method: 'POST',
            body: transferData,
        });
    },

    /**
     * Get transfer status
     */
    async getTransferStatus(transferId) {
        return this.request(`/transfers/${transferId}/status`);
    },

    /**
     * Check if payment has been received
     */
    async checkPaymentReceived(transferId) {
        return this.request(`/transfers/${transferId}/check-payment`, {
            method: 'POST',
        });
    },

    /**
     * Get transfer details
     */
    async getTransferDetails(transferId) {
        return this.request(`/transfers/${transferId}`);
    },

    /**
     * Verify receiver phone
     */
    async verifyReceiverPhone(transferId, phone, verificationCode) {
        return this.request(`/transfers/${transferId}/verify-receiver`, {
            method: 'POST',
            body: { phone, verification_code: verificationCode },
        });
    },

    /**
     * Confirm payment/settlement
     */
    async confirmPayment(transferId, paymentHash) {
        return this.request(`/transfers/${transferId}/confirm-payment`, {
            method: 'POST',
            body: { payment_hash: paymentHash },
        });
    },

    // ===== HEALTH CHECK =====

    /**
     * Check if service is healthy
     */
    async getHealth() {
        return this.request('/health');
    },
};

// UI Helper Functions

function show_spinner(show = true) {
    const spinner = document.getElementById('spinner');
    if (spinner) {
        spinner.style.display = show ? 'flex' : 'none';
    }
}

function show_alert(message, type = 'info') {
    const alertContainer = document.getElementById('alerts');
    if (!alertContainer) return;

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <div class="alert-content">
            <span>${message}</span>
            <button class="alert-close" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

    alertContainer.appendChild(alertDiv);

    // Auto-dismiss after 5 seconds if success
    if (type === 'success') {
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
}

function format_currency(value) {
    return new Intl.NumberFormat('en-ZA', {
        style: 'currency',
        currency: 'ZAR',
        minimumFractionDigits: 2,
    }).format(value);
}

function format_sats(value) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value) + ' sat';
}

function format_date(dateString) {
    return new Intl.DateTimeFormat('en-ZA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(dateString));
}
