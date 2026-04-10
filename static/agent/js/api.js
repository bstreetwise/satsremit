/**
 * SatsRemit Agent API Module
 * Handles all API communication for agent operations
 */

const API_AGENT = {
    BASE_URL: '/api/agent',
    TOKEN_KEY: 'agent_token',
    AGENT_KEY: 'agent_info',

    /**
     * Generic API request handler
     */
    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const method = options.method || 'GET';
        const headers = {
            'Content-Type': 'application/json',
        };

        // Add auth token if available
        const token = localStorage.getItem(this.TOKEN_KEY);
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

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

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!localStorage.getItem(this.TOKEN_KEY);
    },

    /**
     * Get stored agent info
     */
    getAgentInfo() {
        const info = localStorage.getItem(this.AGENT_KEY);
        return info ? JSON.parse(info) : null;
    },

    // ===== AUTHENTICATION =====

    /**
     * Agent login
     */
    async login(phone, password) {
        const response = await this.request('/auth/login', {
            method: 'POST',
            body: { phone, password },
        });

        // Store token and agent info
        localStorage.setItem(this.TOKEN_KEY, response.token);
        localStorage.setItem(this.AGENT_KEY, JSON.stringify({
            agent_id: response.agent_id,
            agent_name: response.agent_name,
            agent_phone: response.agent_phone,
            location_code: response.location_code,
            location_name: response.location_name,
        }));

        return response;
    },

    /**
     * Agent logout
     */
    logout() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.AGENT_KEY);
    },

    // ===== BALANCE & STATS =====

    /**
     * Get agent balance
     */
    async getBalance() {
        return this.request('/balance');
    },

    // ===== TRANSFERS =====

    /**
     * Get pending transfers for agent
     */
    async getPendingTransfers() {
        return this.request('/transfers');
    },

    /**
     * Verify transfer (receiver phone check)
     */
    async verifyTransfer(transferId, receiverPhone, otp) {
        return this.request(`/transfers/${transferId}/verify`, {
            method: 'POST',
            body: { 
                receiver_phone: receiverPhone,
                otp_code: otp 
            },
        });
    },

    /**
     * Confirm payout for a transfer
     */
    async confirmPayout(transferId, pin) {
        return this.request(`/transfers/${transferId}/confirm-payout`, {
            method: 'POST',
            body: { pin },
        });
    },

    // ===== SETTLEMENTS =====

    /**
     * Get all settlements
     */
    async getSettlements() {
        return this.request('/settlements');
    },

    /**
     * Confirm settlement
     */
    async confirmSettlement(settlementId, pin) {
        return this.request(`/settlements/${settlementId}/confirm`, {
            method: 'POST',
            body: { pin },
        });
    },
};

// ===== UI HELPERS =====

function show_spinner(show = true) {
    const spinner = document.getElementById('spinner');
    if (spinner) {
        spinner.classList.toggle('active', show);
    }
}

function show_alert(message, type = 'info') {
    const alertContainer = document.getElementById('alerts');
    if (!alertContainer) return;

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()" style="background: none; border: none; cursor: pointer; color: inherit;">
            <i class="fas fa-times"></i>
        </button>
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

function format_date(dateString) {
    return new Intl.DateTimeFormat('en-ZA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(dateString));
}
