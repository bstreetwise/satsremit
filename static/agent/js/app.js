/**
 * SatsRemit Agent Dashboard
 * Main application logic
 */

// Global state
const AGENT_STATE = {
    agent: null,
    currentTransfer: null,
    currentSettlement: null,
};

// ===== INITIALIZATION =====

document.addEventListener('DOMContentLoaded', async function () {
    init_auth();
    init_event_listeners();
});

function init_auth() {
    if (API_AGENT.isAuthenticated()) {
        show_dashboard();
    } else {
        show_login();
    }
}

function init_event_listeners() {
    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handle_login);
    }

    // Navigation links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            navigate_agent_page(page);
        });
    });

    // Logout buttons
    document.getElementById('logout-btn')?.addEventListener('click', handle_logout);
    document.getElementById('logout-btn2')?.addEventListener('click', handle_logout);
}

// ===== AUTHENTICATION =====

async function handle_login(e) {
    e.preventDefault();

    const phone = document.getElementById('phone').value;
    const password = document.getElementById('password').value;

    try {
        const response = await API_AGENT.login(phone, password);
        show_alert(`Welcome, ${response.agent_name}!`, 'success');
        show_dashboard();
        load_dashboard_data();
    } catch (error) {
        show_alert(error.message, 'error');
    }
}

function handle_logout() {
    if (confirm('Are you sure you want to logout?')) {
        API_AGENT.logout();
        show_login();
    }
}

// ===== PAGE DISPLAY =====

function show_login() {
    document.getElementById('login-page').style.display = 'block';
    document.getElementById('dashboard-page').style.display = 'none';
}

function show_dashboard() {
    document.getElementById('login-page').style.display = 'none';
    document.getElementById('dashboard-page').style.display = 'block';

    // Update agent info
    const agent = API_AGENT.getAgentInfo();
    if (agent) {
        document.getElementById('agent-name').textContent = agent.agent_name;
        document.getElementById('agent-phone').textContent = agent.agent_phone;
        document.getElementById('welcome-message').textContent = `Welcome, ${agent.agent_name}`;
    }
}

function navigate_agent_page(page) {
    // Hide all views
    document.querySelectorAll('.view').forEach(v => v.style.display = 'none');

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-page="${page}"]`).classList.add('active');

    // Show requested view
    const viewId = `view-${page}`;
    const viewElement = document.getElementById(viewId);
    if (viewElement) {
        viewElement.style.display = 'block';

        // Load page-specific content
        if (page === 'dashboard') {
            load_dashboard_data();
        } else if (page === 'transfers') {
            load_transfers_data();
        } else if (page === 'history') {
            load_history_data();
        } else if (page === 'settlements') {
            load_settlements_data();
        }
    }
}

// ===== DASHBOARD VIEW =====

async function load_dashboard_data() {
    try {
        // Get agent balance
        const balance = await API_AGENT.getBalance();
        document.getElementById('stat-balance').textContent = format_currency(balance.cash_balance_zar);

        // Get pending transfers
        const transfers = await API_AGENT.getPendingTransfers();
        const pendingCount = transfers.filter(t => t.state === 'INITIATED' || t.state === 'INVOICE_GENERATED').length;
        const completedCount = transfers.filter(t => t.state === 'SETTLED').length;

        document.getElementById('stat-pending').textContent = pendingCount;
        document.getElementById('stat-completed').textContent = completedCount;

        // Calculate earnings (commission on completed transfers in last 24h)
        const last24hTransfers = transfers.filter(t => {
            const createdAt = new Date(t.created_at);
            return (Date.now() - createdAt.getTime()) < 24 * 60 * 60 * 1000 && t.state === 'SETTLED';
        });

        const earnings = last24hTransfers.reduce((sum, t) => 
            sum + parseFloat(t.agent_commission_zar || 0), 0);
        document.getElementById('stat-earnings').textContent = format_currency(earnings);

        // Show first pending transfer
        const nextTransfer = transfers.find(t => 
            t.state === 'INVOICE_GENERATED' || t.state === 'PAYMENT_RECEIVED');

        if (nextTransfer) {
            render_quick_transfer(nextTransfer);
        } else {
            document.getElementById('quick-transfer-content').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No pending transfers</p>
                </div>
            `;
        }
    } catch (error) {
        show_alert(`Failed to load dashboard: ${error.message}`, 'error');
    }
}

function render_quick_transfer(transfer) {
    document.getElementById('quick-transfer-content').innerHTML = `
        <div class="transfer-item">
            <div class="transfer-info">
                <div class="transfer-ref">${transfer.reference}</div>
                <div class="transfer-detail">
                    <strong>${transfer.receiver_name}</strong> (${transfer.receiver_phone})
                </div>
                <div class="transfer-detail">
                    Amount: ${format_currency(transfer.amount_zar)} (${transfer.amount_sats} sat)
                </div>
                <div class="transfer-detail">
                    Status: <span class="status-badge status-${transfer.state.toLowerCase()}">
                        ${transfer.state}
                    </span>
                </div>
            </div>
            <div class="action-buttons">
                <button class="btn-small btn-verify" onclick="open_verify_modal('${transfer.id}', '${transfer.receiver_phone}')">
                    Verify
                </button>
            </div>
        </div>
    `;
}

// ===== TRANSFERS VIEW =====

async function load_transfers_data() {
    try {
        const transfers = await API_AGENT.getPendingTransfers();

        // Filter for non-settled transfers
        const pending = transfers.filter(t => t.state !== 'SETTLED');

        document.getElementById('transfer-count').textContent = 
            `${pending.length} transfer${pending.length !== 1 ? 's' : ''}`;

        if (pending.length === 0) {
            document.getElementById('transfers-list').innerHTML = `
                <li class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No pending transfers</p>
                </li>
            `;
            return;
        }

        const html = pending.map(t => `
            <li class="transfer-item">
                <div class="transfer-info">
                    <div class="transfer-ref">${t.reference}</div>
                    <div class="transfer-detail">
                        <strong>${t.receiver_name}</strong> (${t.receiver_phone})
                    </div>
                    <div class="transfer-detail">
                        Amount: ${format_currency(t.amount_zar)} (${t.amount_sats} sat)
                    </div>
                    <div class="transfer-detail">
                        Created: ${format_date(t.created_at)}
                    </div>
                    <div class="transfer-detail">
                        Status: <span class="status-badge status-${t.state.toLowerCase()}">
                            ${t.state}
                        </span>
                    </div>
                </div>
                <div class="action-buttons">
                    <button class="btn-small btn-verify" onclick="open_verify_modal('${t.id}', '${t.receiver_phone}')">
                        Verify Receiver
                    </button>
                    ${t.receiver_phone_verified ? `
                        <button class="btn-small btn-payout" onclick="open_payout_modal('${t.id}', '${t.receiver_name}', '${t.receiver_phone}', '${t.amount_zar}', '${t.reference}')">
                            Process Payout
                        </button>
                    ` : ''}
                </div>
            </li>
        `).join('');

        document.getElementById('transfers-list').innerHTML = html;
    } catch (error) {
        show_alert(`Failed to load transfers: ${error.message}`, 'error');
    }
}

// ===== HISTORY VIEW =====

async function load_history_data() {
    try {
        const transfers = await API_AGENT.getPendingTransfers();

        // Filter for settled transfers
        const history = transfers.filter(t => t.state === 'SETTLED');

        if (history.length === 0) {
            document.getElementById('history-list').innerHTML = `
                <li class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No completed transfers</p>
                </li>
            `;
            return;
        }

        const html = history.map(t => `
            <li class="transfer-item">
                <div class="transfer-info">
                    <div class="transfer-ref">${t.reference}</div>
                    <div class="transfer-detail">
                        <strong>${t.receiver_name}</strong> (${t.receiver_phone})
                    </div>
                    <div class="transfer-detail">
                        Amount: ${format_currency(t.amount_zar)}
                    </div>
                    <div class="transfer-detail">
                        Your earnings: ${format_currency(t.agent_commission_zar)}
                    </div>
                    <div class="transfer-detail">
                        Completed: ${format_date(t.settled_at || t.payout_at || t.created_at)}
                    </div>
                </div>
                <div>
                    <span class="status-badge status-completed">
                        <i class="fas fa-check"></i> Completed
                    </span>
                </div>
            </li>
        `).join('');

        document.getElementById('history-list').innerHTML = html;
    } catch (error) {
        show_alert(`Failed to load history: ${error.message}`, 'error');
    }
}

// ===== SETTLEMENTS VIEW =====

async function load_settlements_data() {
    try {
        const settlements = await API_AGENT.getSettlements();

        if (settlements.length === 0) {
            document.getElementById('settlements-list').innerHTML = `
                <li class="empty-state">
                    <i class="fas fa-file-invoice-dollar"></i>
                    <p>No settlements</p>
                </li>
            `;
            return;
        }

        const html = settlements.map(s => `
            <li class="transfer-item">
                <div class="transfer-info">
                    <div class="transfer-ref">${s.settlement_id}</div>
                    <div class="transfer-detail">
                        Amount: ${format_currency(s.amount_zar)}
                    </div>
                    <div class="transfer-detail">
                        Transfers: ${s.transfer_count || 0}
                    </div>
                    <div class="transfer-detail">
                        Status: <span class="status-badge status-${s.status}">
                            ${s.status}
                        </span>
                    </div>
                </div>
                ${s.status === 'pending' ? `
                    <button class="btn-small btn-payout" onclick="confirm_settlement('${s.settlement_id}')">
                        Confirm Settlement
                    </button>
                ` : ''}
            </li>
        `).join('');

        document.getElementById('settlements-list').innerHTML = html;
    } catch (error) {
        show_alert(`Failed to load settlements: ${error.message}`, 'error');
    }
}

// ===== MODALS =====

function open_modal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function close_modal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function open_verify_modal(transferId, receiverPhone) {
    AGENT_STATE.currentTransfer = transferId;
    document.getElementById('verify-phone').value = receiverPhone;
    document.getElementById('verify-otp').value = '';
    open_modal('verify-modal');
}

async function submit_verify() {
    const transferId = AGENT_STATE.currentTransfer;
    const phone = document.getElementById('verify-phone').value;
    const otp = document.getElementById('verify-otp').value;

    if (!otp) {
        show_alert('Please enter OTP', 'error');
        return;
    }

    try {
        await API_AGENT.verifyTransfer(transferId, phone, otp);
        show_alert('Receiver verified! Ready for payout.', 'success');
        close_modal('verify-modal');
        load_transfers_data();
    } catch (error) {
        show_alert(`Verification failed: ${error.message}`, 'error');
    }
}

function open_payout_modal(transferId, name, phone, amount, reference) {
    AGENT_STATE.currentTransfer = transferId;
    document.getElementById('payout-name').value = name;
    document.getElementById('payout-phone').value = phone;
    document.getElementById('payout-amount').textContent = format_currency(amount);
    document.getElementById('payout-reference').value = reference;
    open_modal('payout-modal');
}

async function submit_payout() {
    const transferId = AGENT_STATE.currentTransfer;

    if (!confirm('Confirm that you have completed the cash payout to the recipient?')) {
        return;
    }

    try {
        // On testnet, PIN is optional
        await API_AGENT.confirmPayout(transferId, '0000');
        show_alert('Payout confirmed! Transfer complete.', 'success');
        close_modal('payout-modal');
        load_transfers_data();
        load_dashboard_data();
    } catch (error) {
        show_alert(`Payout confirmation failed: ${error.message}`, 'error');
    }
}

async function confirm_settlement(settlementId) {
    if (!confirm('Confirm this settlement?')) {
        return;
    }

    try {
        await API_AGENT.confirmSettlement(settlementId, '0000');
        show_alert('Settlement confirmed!', 'success');
        load_settlements_data();
    } catch (error) {
        show_alert(`Settlement confirmation failed: ${error.message}`, 'error');
    }
}
