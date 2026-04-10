/**
 * SatsRemit Admin UI Module
 * Handles all UI interactions and rendering
 */

// ===== GLOBAL UI STATE =====
const UI_STATE = {
    currentPage: 1,
    itemsPerPage: 20,
    currentFilter: {},
};

// ===== DOM UTILITIES =====

function show_spinner(show = true) {
    const spinner = document.getElementById('loading-spinner');
    if (show) {
        spinner.classList.remove('hidden');
    } else {
        spinner.classList.add('hidden');
    }
}

function show_alert(message, type = 'success') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        <span>${message}</span>
    `;
    container.appendChild(alert);

    setTimeout(() => alert.remove(), 5000);
}

function format_currency(value, currency = 'ZAR') {
    const num = parseFloat(value);
    return new Intl.NumberFormat('en-ZA', {
        style: 'currency',
        currency: currency,
    }).format(num);
}

function format_sats(value) {
    return `${parseInt(value).toLocaleString()} sats`;
}

function format_date(date) {
    return new Date(date).toLocaleDateString('en-ZA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function get_status_badge(state) {
    const badges = {
        'INITIATED': 'info',
        'PAID': 'info',
        'SETTLED': 'success',
        'RECEIVER_VERIFIED': 'success',
        'PAYOUT_EXECUTED': 'success',
        'PENDING': 'pending',
        'COMPLETED': 'success',
        'FAILED': 'error',
        'ACTIVE': 'success',
        'INACTIVE': 'error',
    };
    const type = badges[state] || 'info';
    return `<span class="badge badge-${type}">${state}</span>`;
}

// ===== SECTION NAVIGATION =====

function navigate_to_section(section) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));

    // Show selected section
    const sectionElement = document.getElementById(section);
    if (sectionElement) {
        sectionElement.classList.add('active');
    }

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-section="${section}"]`)?.classList.add('active');

    // Update page title
    const titles = {
        dashboard: 'Dashboard',
        agents: 'Agent Management',
        transfers: 'Transfer History',
        settlements: 'Settlement Records',
        analytics: 'Analytics & Insights',
    };
    document.getElementById('page-title').textContent = titles[section] || section;

    // Load section data
    load_section_data(section);
}

function load_section_data(section) {
    switch (section) {
        case 'dashboard':
            load_dashboard();
            break;
        case 'agents':
            load_agents_table();
            break;
        case 'transfers':
            load_transfers_table();
            break;
        case 'settlements':
            load_settlements_table();
            break;
        case 'analytics':
            load_analytics();
            break;
    }
}

// ===== DASHBOARD =====

async function load_dashboard() {
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

// ===== AGENTS TABLE =====

async function load_agents_table() {
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

async function show_agent_details(agentId) {
    try {
        const balance = await API.getAgentBalance(agentId);
        alert(`Agent: ${balance.agent_name}\nCash Owed: ${format_currency(balance.cash_owed_zar)}\nCommission: ${format_sats(balance.sats_earned)}\nSettlements Pending: ${balance.settlements_pending}`);
    } catch (error) {
        show_alert(`Failed to load agent details: ${error.message}`, 'error');
    }
}

// ===== TRANSFERS TABLE =====

async function load_transfers_table() {
    try {
        const state = document.getElementById('transfer-filter-state')?.value;
        const options = {
            state: state || undefined,
            limit: UI_STATE.itemsPerPage,
            offset: (UI_STATE.currentPage - 1) * UI_STATE.itemsPerPage,
        };

        const transfers = await API.listTransfers(options);
        const tbody = document.getElementById('transfers-tbody');
        tbody.innerHTML = '';

        if (!transfers || transfers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7">No transfers found</td></tr>';
            return;
        }

        for (const transfer of transfers) {
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
        }
    } catch (error) {
        show_alert(`Failed to load transfers: ${error.message}`, 'error');
    }
}

async function show_transfer_details(transferId) {
    try {
        const transfer = await API.getTransfer(transferId);
        const details = `
Transfer: ${transfer.reference}
Amount: ${format_currency(transfer.amount_zar)}
State: ${transfer.state}
Created: ${format_date(transfer.created_at)}
        `;
        alert(details);
    } catch (error) {
        show_alert(`Failed to load transfer details: ${error.message}`, 'error');
    }
}

// ===== SETTLEMENTS TABLE =====

async function load_settlements_table() {
    try {
        const settlements = await API.listSettlements();
        const tbody = document.getElementById('settlements-tbody');
        tbody.innerHTML = '';

        if (!settlements || settlements.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7">No settlements found</td></tr>';
            return;
        }

        for (const settlement of settlements) {
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
        }
    } catch (error) {
        show_alert(`Failed to load settlements: ${error.message}`, 'error');
    }
}

async function confirm_settlement(settlementId) {
    try {
        const response = await API.request(`/admin/settlements/${settlementId}/confirm`, {
            method: 'POST',
            body: {},
        });
        show_alert('Settlement confirmed successfully', 'success');
        load_settlements_table();
    } catch (error) {
        show_alert(`Failed to confirm settlement: ${error.message}`, 'error');
    }
}

// ===== ANALYTICS =====

async function load_analytics() {
    try {
        const volume = await API.getVolumeAnalytics();

        // Calculate metrics
        const totalTransfers = volume.daily_transfers + volume.weekly_transfers + volume.monthly_transfers;
        const totalVolume = volume.daily_volume_zar + volume.weekly_volume_zar + volume.monthly_volume_zar;
        const avgTransfer = totalTransfers > 0 ? totalVolume / totalTransfers : 0;
        const successRate = '98%'; // Placeholder

        document.getElementById('total-transfers').textContent = totalTransfers;
        document.getElementById('total-volume-value').textContent = format_currency(totalVolume);
        document.getElementById('avg-transfer').textContent = format_currency(avgTransfer);
        document.getElementById('success-rate').textContent = successRate;

        // Load top agents (simulated)
        load_top_agents();

    } catch (error) {
        show_alert(`Failed to load analytics: ${error.message}`, 'error');
    }
}

async function load_top_agents() {
    try {
        const agents = await API.listAgents(10, 0);
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
    } catch (error) {
        show_alert(`Failed to load top agents: ${error.message}`, 'error');
    }
}

// ===== MODALS =====

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

// ===== FORM HANDLERS =====

async function handle_add_agent(event) {
    event.preventDefault();

    const phone = document.getElementById('agent-phone').value;
    const name = document.getElementById('agent-name').value;
    const location = document.getElementById('agent-location').value;
    const initialCash = parseFloat(document.getElementById('initial-cash').value);

    try {
        await API.createAgent(phone, name, location, initialCash);
        show_alert('Agent created successfully', 'success');
        close_modal('add-agent-modal');
        document.getElementById('add-agent-form').reset();
        load_agents_table();
    } catch (error) {
        show_alert(`Failed to create agent: ${error.message}`, 'error');
    }
}

// Export functions
window.UI = {
    navigate_to_section,
    show_alert,
    show_spinner,
    format_currency,
    format_sats,
    format_date,
    get_status_badge,
    open_modal,
    close_modal,
    handle_add_agent,
    show_agent_details,
    show_transfer_details,
    confirm_settlement,
};
