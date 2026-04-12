/**
 * SatsRemit Admin UI Module
 * Handles all UI interactions and rendering
 * VERSION: 2.1 (agent.agent_id fix) - Deployed 2026-04-11
 */

// ===== VERSION CHECK =====
window.UI_VERSION = "2.1-agent-fix";
console.log(`✓ UI Module Loaded - Version: ${window.UI_VERSION}`);

// ===== GLOBAL UI STATE =====
const UI_STATE = {
    currentPage: 1,
    itemsPerPage: 20,
    currentFilter: {},
};

// ===== ADMIN CHECK =====
function is_current_user_admin() {
    try {
        const token = localStorage.getItem('admin_token');
        if (!token) return false;
        
        // JWT format: header.payload.signature
        const parts = token.split('.');
        if (parts.length !== 3) return false;
        
        // Decode payload
        const payloadStr = atob(parts[1]);
        const payload = JSON.parse(payloadStr);
        
        return payload.is_admin === true;
    } catch (error) {
        console.warn('Failed to check admin status:', error);
        return false;
    }
}

function get_current_admin_agent_id() {
    try {
        const token = localStorage.getItem('admin_token');
        if (!token) return null;
        
        // JWT format: header.payload.signature
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        
        // Decode payload
        const payloadStr = atob(parts[1]);
        const payload = JSON.parse(payloadStr);
        
        return payload.agent_id || null;
    } catch (error) {
        console.warn('Failed to get admin agent ID:', error);
        return null;
    }
}

function can_send_cash_to_agent(agentId) {
    // Only show for admin users sending to OTHER agents (not themselves)
    return is_current_user_admin() && agentId !== get_current_admin_agent_id();
}

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
        'audit-trail': 'Cash Advances Audit Trail',
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
        case 'audit-trail':
            load_audit_trail();
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
    console.log("DEBUG: Starting load_agents_table...");
    try {
        console.log("DEBUG: Calling API.listAgents...");
        const response = await API.listAgents(UI_STATE.itemsPerPage, (UI_STATE.currentPage - 1) * UI_STATE.itemsPerPage);
        
        console.log("DEBUG: Got response:", response);
        console.log("DEBUG: Response type:", typeof response);
        console.log("DEBUG: Response length:", response?.length);
        
        const tbody = document.getElementById('agents-tbody');
        tbody.innerHTML = '';

        if (!response || response.length === 0) {
            console.log("DEBUG: No agents found");
            tbody.innerHTML = '<tr><td colspan="7">No agents found</td></tr>';
            return;
        }

        console.log(`DEBUG: Processing ${response.length} agents`);
        
        for (const agent of response) {
            console.log(`DEBUG: Processing agent: ${agent.phone}, agent_id: ${agent.agent_id}`);
            try {
                // Fetch balance with error handling per agent
                let balance = null;
                try {
                    console.log(`DEBUG: Fetching balance for agent_id: ${agent.agent_id}`);
                    balance = await API.getAgentBalance(agent.agent_id);
                    console.log(`DEBUG: Got balance:`, balance);
                } catch (balanceError) {
                    console.error(`Balance fetch failed for ${agent.phone}:`, balanceError);
                    balance = {
                        cash_owed_zar: agent.cash_balance_zar || '0.00',
                        sats_earned: 0,
                        commission_zar: '0'
                    };
                }

                const row = document.createElement('tr');
                const sendCashButton = can_send_cash_to_agent(agent.agent_id) ? `
                        <button class="btn btn-sm btn-success" onclick="open_send_cash_modal('${agent.agent_id}', '${agent.name}', '${balance.cash_owed_zar || agent.cash_balance_zar || 0}')">
                            <i class="fas fa-money-bill"></i> Send Cash
                        </button>
                    ` : '';
                
                row.innerHTML = `
                    <td><strong>${agent.name}</strong></td>
                    <td>${agent.phone}</td>
                    <td>${agent.location_code || 'N/A'}</td>
                    <td>${format_currency(balance.cash_owed_zar || agent.cash_balance_zar || '0.00')}</td>
                    <td>${format_sats(balance.sats_earned || 0)}</td>
                    <td>${get_status_badge(agent.status)}</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="show_agent_details('${agent.agent_id}')">
                            <i class="fas fa-eye"></i> View
                        </button>
                        ${sendCashButton}
                    </td>
                `;
                tbody.appendChild(row);
                console.log(`DEBUG: Added row for ${agent.phone}`);
            } catch (agentError) {
                console.error(`Failed to process agent:`, agentError);
            }
        }
        console.log("DEBUG: load_agents_table completed successfully");
    } catch (error) {
        console.error("DEBUG: ERROR in load_agents_table:", error);
        console.error("DEBUG: Error message:", error.message);
        console.error("DEBUG: Error stack:", error.stack);
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

// ===== AUDIT TRAIL =====

async function load_audit_trail() {
    try {
        const advances = await API.getCashAdvancesAuditTrail(1000, 0);
        const tbody = document.getElementById('audit-trail-tbody');
        tbody.innerHTML = '';

        if (!advances || advances.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8">No cash advances recorded</td></tr>';
            return;
        }

        for (const advance of advances) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code style="font-size: 11px; background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px;">${advance.transaction_id}</code></td>
                <td><strong>${advance.admin_agent_name}</strong><br><small>${advance.admin_agent_phone}</small></td>
                <td><strong>${advance.recipient_agent_name}</strong><br><small>${advance.recipient_agent_phone}</small></td>
                <td>${format_currency(advance.amount_zar)}</td>
                <td><small>${format_currency(advance.admin_balance_before)} → ${format_currency(advance.admin_balance_after)}</small></td>
                <td><small>${format_currency(advance.recipient_balance_before)} → ${format_currency(advance.recipient_balance_after)}</small></td>
                <td>${advance.note || '—'}</td>
                <td>${format_date(advance.created_at)}</td>
            `;
            tbody.appendChild(row);
        }
    } catch (error) {
        show_alert(`Failed to load audit trail: ${error.message}`, 'error');
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

    // Validate on client side first
    if (!phone || phone.length < 10) {
        show_alert('Phone number must be at least 10 characters (e.g., +263712345678)', 'error');
        return;
    }
    if (!name || name.length < 2) {
        show_alert('Agent name must be at least 2 characters', 'error');
        return;
    }
    if (!location) {
        show_alert('Please select a location', 'error');
        return;
    }
    if (isNaN(initialCash) || initialCash < 100) {
        show_alert('Initial cash must be at least 100 ZAR', 'error');
        return;
    }

    try {
        const response = await API.createAgent(phone, name, location, initialCash);
        show_alert('Agent created successfully!', 'success');
        close_modal('add-agent-modal');
        document.getElementById('add-agent-form').reset();
        load_agents_table();
    } catch (error) {
        // Show detailed error message from server
        const errorMsg = error.message || 'Unknown error';
        console.error('Agent creation failed:', errorMsg);
        show_alert(`Failed to create agent: ${errorMsg}`, 'error');
    }
}

// ===== CASH ADVANCE HANDLERS =====

// Store current agent ID for form submission
let current_advance_agent_id = null;
let current_admin_balance = 0;

async function open_send_cash_modal(agentId, agentName, currentBalance) {
    // Admin-only check
    if (!is_current_user_admin()) {
        show_alert('Only admin users can send cash advances to agents', 'error');
        return;
    }
    
    // Prevent admin from sending cash to themselves
    const currentAdminId = get_current_admin_agent_id();
    if (agentId === currentAdminId) {
        show_alert('Cannot send cash to your own admin account', 'error');
        return;
    }
    
    current_advance_agent_id = agentId;
    
    // Safely set form fields with null checks
    const agentForAdvance = document.getElementById('agent-for-advance');
    const currentBalanceField = document.getElementById('current-balance');
    const advanceAmount = document.getElementById('advance-amount');
    const advanceNote = document.getElementById('advance-note');
    
    if (agentForAdvance) agentForAdvance.value = agentName;
    if (currentBalanceField) currentBalanceField.value = `ZAR ${parseFloat(currentBalance).toFixed(2)}`;
    if (advanceAmount) advanceAmount.value = '';
    if (advanceNote) advanceNote.value = '';
    
    // Fetch admin's balance and show it
    const adminBalanceElement = document.getElementById('admin-balance');
    if (adminBalanceElement) {
        try {
            adminBalanceElement.textContent = 'Loading...';
            // Fetch the current admin's balance
            const currentAdminBalance = await API.getAgentBalance(currentAdminId);
            if (currentAdminBalance && currentAdminBalance.cash_owed_zar) {
                adminBalanceElement.textContent = `ZAR ${parseFloat(currentAdminBalance.cash_owed_zar).toFixed(2)}`;
            } else {
                adminBalanceElement.textContent = 'ZAR 0.00';
            }
        } catch (error) {
            console.warn('Could not load admin balance:', error);
            adminBalanceElement.textContent = 'ZAR 0.00';
        }
    }
    
    open_modal('send-cash-modal');
}

async function handle_send_cash_advance(event) {
    event.preventDefault();

    // Admin-only check
    if (!is_current_user_admin()) {
        show_alert('Only admin users can send cash advances', 'error');
        return;
    }

    // Prevent admin from sending cash to themselves
    const currentAdminId = get_current_admin_agent_id();
    if (current_advance_agent_id === currentAdminId) {
        show_alert('Cannot send cash to your own admin account', 'error');
        return;
    }

    const amount = parseFloat(document.getElementById('advance-amount').value);
    const note = document.getElementById('advance-note').value || 'Cash advance from admin';

    // Validate
    if (isNaN(amount) || amount < 10) {
        show_alert('Advance amount must be at least 10 ZAR', 'error');
        return;
    }

    if (!current_advance_agent_id) {
        show_alert('No agent selected', 'error');
        return;
    }

    try {
        show_spinner(true);
        const response = await API.recordAgentAdvance(
            current_advance_agent_id,
            amount,
            note
        );
        show_spinner(false);
        show_alert(`✓ Cash advance of ZAR ${amount.toFixed(2)} sent successfully! New balance: ZAR ${parseFloat(response.new_balance_zar).toFixed(2)}`, 'success');
        close_modal('send-cash-modal');
        // Refresh agents table
        load_agents_table();
    } catch (error) {
        show_spinner(false);
        console.error('Cash advance failed:', error);
        
        // Provide better error messages for common cases
        let errorMsg = error.message;
        if (errorMsg.includes('Insufficient balance')) {
            errorMsg = `❌ ${errorMsg}. Please check your (admin) cash balance.`;
        } else if (errorMsg.includes('not found')) {
            errorMsg = 'Agent not found. Agent may have been deleted.';
        }
        
        show_alert(`Failed to send advance: ${errorMsg}`, 'error');
    }
}

// Export functions
window.UI = {
    navigate_to_section,
    load_section_data,
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
    load_dashboard,
    load_agents_table,
    load_transfers_table,
    load_settlements_table,
    load_analytics,
    load_top_agents,
    load_audit_trail,
    open_send_cash_modal,
    handle_send_cash_advance,
};
