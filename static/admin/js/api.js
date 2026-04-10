/**
 * SatsRemit Admin API Module
 * Handles all API communication with the backend
 */

const API = {
    BASE_URL: '/api',
    token: localStorage.getItem('admin_token') || null,

    /**
     * Set authentication token
     */
    setToken(token) {
        this.token = token;
        localStorage.setItem('admin_token', token);
    },

    /**
     * Get authorization headers
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
    },

    /**
     * Generic API request handler
     */
    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const method = options.method || 'GET';
        const headers = this.getHeaders();

        try {
            show_spinner(true);

            const response = await fetch(url, {
                method,
                headers,
                body: options.body ? JSON.stringify(options.body) : undefined,
            });

            if (response.status === 401) {
                throw new Error('Unauthorized - Please login again');
            }

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

    // ===== ADMIN AUTHENTICATION =====

    async loginAdmin(phone, password) {
        return this.request('/admin/auth/login', {
            method: 'POST',
            body: { phone, password },
        });
    },

    // ===== AGENTS =====

    /**
     * Create new agent
     */
    async createAgent(phone, name, location_code, initial_cash_zar) {
        return this.request('/admin/agents', {
            method: 'POST',
            body: {
                phone,
                name,
                location_code,
                initial_cash_zar,
            },
        });
    },

    /**
     * Get all agents with pagination
     */
    async listAgents(limit = 100, offset = 0) {
        return this.request(`/admin/agents?limit=${limit}&offset=${offset}`);
    },

    /**
     * Get agent financial status
     */
    async getAgentBalance(agentId) {
        return this.request(`/admin/agents/${agentId}/balance`);
    },

    /**
     * Record cash advance for agent
     */
    async recordAgentAdvance(agentId, zar_amount, note) {
        return this.request(`/admin/agents/${agentId}/advance`, {
            method: 'POST',
            body: { zar_amount, note },
        });
    },

    // ===== TRANSFERS =====

    /**
     * List transfers with filtering
     */
    async listTransfers(options = {}) {
        const params = new URLSearchParams();
        if (options.state) params.append('state', options.state);
        if (options.agent_id) params.append('agent_id', options.agent_id);
        if (options.limit) params.append('limit', options.limit);
        if (options.offset) params.append('offset', options.offset);

        const query = params.toString();
        return this.request(`/admin/transfers${query ? '?' + query : ''}`);
    },

    /**
     * Get transfer details
     */
    async getTransfer(transferId) {
        return this.request(`/admin/transfers/${transferId}`);
    },

    // ===== SETTLEMENTS =====

    /**
     * List agent settlements
     */
    async listSettlements(options = {}) {
        const params = new URLSearchParams();
        if (options.agent_id) params.append('agent_id', options.agent_id);
        if (options.status) params.append('status', options.status);

        const query = params.toString();
        return this.request(`/admin/settlements${query ? '?' + query : ''}`);
    },

    /**
     * Get settlement details
     */
    async getSettlement(settlementId) {
        return this.request(`/admin/settlements/${settlementId}`);
    },

    // ===== ANALYTICS =====

    /**
     * Get platform volume analytics
     */
    async getVolumeAnalytics() {
        return this.request('/admin/volume');
    },

    /**
     * Get transfer analytics
     */
    async getTransferAnalytics() {
        return this.request('/admin/analytics/transfers');
    },

    /**
     * Get agent analytics
     */
    async getAgentAnalytics() {
        return this.request('/admin/analytics/agents');
    },

    // ===== SYSTEM STATUS =====

    /**
     * Get admin health status
     */
    async getAdminHealth() {
        return this.request('/admin/health');
    },

    /**
     * Get platform health
     */
    async getHealth() {
        return this.request('/health');
    },
};

// Export for use in other modules
window.API = API;
