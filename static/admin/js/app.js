/**
 * SatsRemit Admin Application
 * Main entry point and event handlers
 */

// ===== INITIALIZATION =====

document.addEventListener('DOMContentLoaded', async function () {
    init_event_listeners();
    await check_authentication();
    navigate_to_section('dashboard');
});

// ===== AUTHENTICATION =====

async function check_authentication() {
    const token = localStorage.getItem('admin_token');

    if (!token) {
        show_login_screen();
        return;
    }

    // Verify token is still valid
    try {
        API.setToken(token);
        await API.getAdminHealth();
        display_admin_info();
    } catch (error) {
        localStorage.removeItem('admin_token');
        show_login_screen();
    }
}

function show_login_screen() {
    const loginHtml = `
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <i class="fas fa-bolt"></i>
                <h1>SatsRemit Admin</h1>
            </div>
            <form id="login-form" class="form">
                <div class="form-group">
                    <label for="login-phone">Admin Phone</label>
                    <input type="tel" id="login-phone" placeholder="+27..." required>
                </div>
                <div class="form-group">
                    <label for="login-password">Password</label>
                    <input type="password" id="login-password" placeholder="Password" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">Login</button>
            </form>
        </div>
    </div>
    `;

    document.querySelector('.container-fluid').innerHTML = loginHtml;

    document.getElementById('login-form').addEventListener('submit', handle_login);

    // Add login styles
    const loginStyles = `
    <style>
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: linear-gradient(135deg, #f7931a 0%, #1a1a1a 100%);
        }

        .login-card {
            background: white;
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
        }

        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .login-header i {
            font-size: 3rem;
            color: #f7931a;
            margin-bottom: 0.5rem;
        }

        .login-header h1 {
            font-size: 1.5rem;
            margin: 0;
        }
    </style>
    `;

    if (!document.querySelector('style[data-login="true"]')) {
        const styleTag = document.createElement('style');
        styleTag.setAttribute('data-login', 'true');
        styleTag.textContent = loginStyles;
        document.head.appendChild(styleTag);
    }
}

async function handle_login(event) {
    event.preventDefault();

    const phone = document.getElementById('login-phone').value;
    const password = document.getElementById('login-password').value;

    try {
        show_spinner(true);
        const response = await API.loginAdmin(phone, password);
        API.setToken(response.token);
        location.reload();
    } catch (error) {
        show_spinner(false);
        show_alert(`Login failed: ${error.message}`, 'error');
    }
}

function display_admin_info() {
    const adminName = localStorage.getItem('admin_name') || 'Admin User';
    document.getElementById('admin-name').textContent = adminName;
}

// ===== EVENT LISTENERS =====

function init_event_listeners() {
    // Navigation
    document.querySelectorAll('.nav-link[data-section]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.getAttribute('data-section');
            navigate_to_section(section);
        });
    });

    // Logout
    document.getElementById('logout-btn')?.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.removeItem('admin_token');
        location.reload();
    });

    // Add Agent Button
    document.getElementById('add-agent-btn')?.addEventListener('click', () => {
        open_modal('add-agent-modal');
    });

    // Add Agent Form
    document.getElementById('add-agent-form')?.addEventListener('submit', handle_add_agent);

    // Send Cash Advance Form
    document.getElementById('send-cash-form')?.addEventListener('submit', handle_send_cash_advance);

    // Modal Close Buttons
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const modal = btn.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });

    // Filter Transfers
    document.getElementById('transfer-filter-state')?.addEventListener('change', () => {
        UI_STATE.currentPage = 1;
        load_transfers_table();
    });

    document.getElementById('transfer-search')?.addEventListener('input', () => {
        UI_STATE.currentPage = 1;
        load_transfers_table();
    });

    // Pagination
    document.getElementById('prev-page')?.addEventListener('click', () => {
        if (UI_STATE.currentPage > 1) {
            UI_STATE.currentPage--;
            load_transfers_table();
        }
    });

    document.getElementById('next-page')?.addEventListener('click', () => {
        UI_STATE.currentPage++;
        load_transfers_table();
    });

    // Auto-refresh dashboard every 30 seconds
    setInterval(() => {
        const activeSection = document.querySelector('.section.active');
        if (activeSection && activeSection.id === 'dashboard') {
            load_dashboard();
        }
    }, 30000);
}

// ===== GLOBAL FUNCTIONS =====

function open_modal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function close_modal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

function show_alert(message, type = 'success') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    container.appendChild(alert);

    setTimeout(() => alert.remove(), 5000);
}

function show_spinner(show = true) {
    const spinner = document.getElementById('loading-spinner');
    if (show) {
        spinner.classList.remove('hidden');
    } else {
        spinner.classList.add('hidden');
    }
}

function navigate_to_section(section) {
    UI.navigate_to_section(section);
}

function format_currency(value, currency = 'ZAR') {
    return UI.format_currency(value, currency);
}

function format_sats(value) {
    return UI.format_sats(value);
}

function format_date(date) {
    return UI.format_date(date);
}

function get_status_badge(state) {
    return UI.get_status_badge(state);
}

function handle_add_agent(event) {
    UI.handle_add_agent(event);
}

function show_agent_details(agentId) {
    UI.show_agent_details(agentId);
}

function show_transfer_details(transferId) {
    UI.show_transfer_details(transferId);
}

function confirm_settlement(settlementId) {
    UI.confirm_settlement(settlementId);
}

function open_send_cash_modal(agentId, agentName, currentBalance) {
    UI.open_send_cash_modal(agentId, agentName, currentBalance);
}

function handle_send_cash_advance(event) {
    UI.handle_send_cash_advance(event);
}

function load_dashboard() {
    const dashboardSection = document.getElementById('dashboard');
    if (dashboardSection && dashboardSection.classList.contains('active')) {
        return load_dashboard_internal();
    }
}

async function load_dashboard_internal() {
    try {
        const volume = await API.getVolumeAnalytics();
        const health = await API.getAdminHealth();

        // Update volume metrics
        document.getElementById('daily-volume').textContent = format_currency(volume.daily_volume_zar);
        document.querySelector('.metric-card:nth-child(1) .metric-transfers').textContent = `${volume.daily_transfers} transfers today`;

        document.getElementById('weekly-volume').textContent = format_currency(volume.weekly_volume_zar);
        document.querySelector('.metric-card:nth-child(2) .metric-transfers').textContent = `${volume.weekly_transfers} transfers this week`;

        document.getElementById('monthly-volume').textContent = format_currency(volume.monthly_volume_zar);
        document.querySelector('.metric-card:nth-child(3) .metric-transfers').textContent = `${volume.monthly_transfers} transfers this month`;

        document.getElementById('fees-collected').textContent = format_sats(volume.total_fees_collected_sats);

        // Update stats
        document.getElementById('active-agents').textContent = health.active_agents || 0;
        document.getElementById('pending-settlements').textContent = health.pending_settlements || 0;
        document.getElementById('platform-earnings').textContent = format_sats(volume.platform_earn_sats);
        document.getElementById('agent-earnings').textContent = format_sats(volume.agent_earn_sats);

    } catch (error) {
        show_alert(`Failed to load dashboard: ${error.message}`, 'error');
    }
}

function load_agents_table() {
    return UI.load_agents_table ? UI.load_agents_table() : load_agents_table_internal();
}

async function load_agents_table_internal() {
    try {
        const response = await API.listAgents(UI_STATE.itemsPerPage, (UI_STATE.currentPage - 1) * UI_STATE.itemsPerPage);
        const tbody = document.getElementById('agents-tbody');
        tbody.innerHTML = '';

        if (!response || response.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7">No agents found</td></tr>';
            return;
        }

        for (const agent of response) {
            const balance = await API.getAgentBalance(agent.id);

            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${agent.name}</strong></td>
                <td>${agent.phone}</td>
                <td>${agent.location_name || agent.location_code}</td>
                <td>${format_currency(balance.cash_owed_zar)}</td>
                <td>${format_sats(balance.sats_earned)}</td>
                <td>${get_status_badge(agent.status)}</td>
                <td>
                    <button class="btn btn-sm btn-info" onclick="show_agent_details('${agent.id}')">
                        <i class="fas fa-eye"></i> View
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        }
    } catch (error) {
        show_alert(`Failed to load agents: ${error.message}`, 'error');
    }
}

function load_transfers_table() {
    try {
        const state = document.getElementById('transfer-filter-state')?.value;
        const options = {
            state: state || undefined,
            limit: UI_STATE.itemsPerPage,
            offset: (UI_STATE.currentPage - 1) * UI_STATE.itemsPerPage,
        };

        return API.listTransfers(options).then(transfers => {
            const tbody = document.getElementById('transfers-tbody');
            tbody.innerHTML = '';

            if (!transfers || transfers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7">No transfers found</td></tr>';
                return;
            }

            transfers.forEach(transfer => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${transfer.reference}</strong></td>
                    <td>${format_currency(transfer.amount_zar)}</td>
                    <td>${format_sats(transfer.amount_sats)}</td>
                    <td>${transfer.agent_name || 'Unknown'}</td>
                    <td>${get_status_badge(transfer.state)}</td>
                    <td>${format_date(transfer.created_at)}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="show_transfer_details('${transfer.transfer_id}')">
                            <i class="fas fa-eye"></i> Details
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });

            document.getElementById('page-info').textContent = `Page ${UI_STATE.currentPage}`;
        }).catch(error => {
            show_alert(`Failed to load transfers: ${error.message}`, 'error');
        });
    } catch (error) {
        show_alert(`Failed to load transfers: ${error.message}`, 'error');
    }
}

function load_settlements_table() {
    return API.listSettlements().then(settlements => {
        const tbody = document.getElementById('settlements-tbody');
        tbody.innerHTML = '';

        if (!settlements || settlements.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7">No settlements found</td></tr>';
            return;
        }

        settlements.forEach(settlement => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${settlement.settlement_id}</strong></td>
                <td>${settlement.agent_name}</td>
                <td>${settlement.period}</td>
                <td>${format_currency(settlement.amount_zar)}</td>
                <td>${get_status_badge(settlement.status)}</td>
                <td>${format_date(settlement.due_date)}</td>
                <td>
                    <button class="btn btn-sm btn-success" onclick="confirm_settlement('${settlement.settlement_id}')">
                        <i class="fas fa-check"></i> Confirm
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }).catch(error => {
        show_alert(`Failed to load settlements: ${error.message}`, 'error');
    });
}

function load_analytics() {
    return API.getVolumeAnalytics().then(volume => {
        // Calculate metrics
        const totalTransfers = volume.daily_transfers + volume.weekly_transfers + volume.monthly_transfers;
        const totalVolume = volume.daily_volume_zar + volume.weekly_volume_zar + volume.monthly_volume_zar;
        const avgTransfer = totalTransfers > 0 ? totalVolume / totalTransfers : 0;
        const successRate = '98%';

        document.getElementById('total-transfers').textContent = totalTransfers;
        document.getElementById('total-volume-value').textContent = format_currency(totalVolume);
        document.getElementById('avg-transfer').textContent = format_currency(avgTransfer);
        document.getElementById('success-rate').textContent = successRate;

        // Load top agents
        return API.listAgents(10, 0).then(agents => {
            const tbody = document.getElementById('top-agents-tbody');
            tbody.innerHTML = '';

            agents.slice(0, 5).forEach((agent, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${agent.name}</td>
                    <td>${agent.total_transfers || 0}</td>
                    <td>${format_currency(0)}</td>
                    <td>${format_sats(agent.commission_balance_sats || 0)}</td>
                `;
                tbody.appendChild(row);
            });
        });
    }).catch(error => {
        show_alert(`Failed to load analytics: ${error.message}`, 'error');
    });
}
