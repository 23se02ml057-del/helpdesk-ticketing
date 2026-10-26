(function () {
    const DEBOUNCE_MS = 300;

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    const translateText = function (key, fallback) {
        if (window.i18n && typeof window.i18n.t === 'function') {
            var val = window.i18n.t(key);
            if (val && val !== key) return val;
        }
        return fallback || key;
    };

    function renderTickets(rows) {
        if (!rows.length) {
            return '<tr><td colspan="11" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_tickets', 'No matching tickets') + '</td></tr>';
        }
        return rows.map(function (ticket) {
            var statusClass = 'bg-secondary';
            if (ticket.status_name === 'Open') statusClass = 'bg-danger';
            else if (ticket.status_name === 'In Progress') statusClass = 'bg-warning text-dark';
            else if (ticket.status_name === 'Resolved') statusClass = 'bg-success';
            else if (ticket.status_name === 'Closed') statusClass = 'bg-secondary';
            else if (ticket.status_name === 'On Hold') statusClass = 'bg-info';
            else if (ticket.status_name === 'New') statusClass = 'bg-primary';

            var priorityClass = 'bg-secondary';
            if (ticket.priority_name === 'Critical' || ticket.priority_name === 'High') priorityClass = 'bg-danger';
            else if (ticket.priority_name === 'Medium') priorityClass = 'bg-warning text-dark';
            else if (ticket.priority_name === 'Low') priorityClass = 'bg-success';

            var mlHtml = '<span class="text-muted">-</span>';
            if (ticket.ml_minutes) {
                var hours = Math.floor(ticket.ml_minutes / 60);
                var mins = Math.round(ticket.ml_minutes % 60);
                mlHtml = hours + 'h ' + mins + 'm';
                if (ticket.ml_model) {
                    mlHtml += '<small class="text-muted d-block">v' + escapeHtml(ticket.ml_model) + '</small>';
                }
            }

            var requesterName = [ticket.requester_first, ticket.requester_last].filter(Boolean).join(' ') || '-';
            var agentName = [ticket.agent_first, ticket.agent_last].filter(Boolean).join(' ') || '-';

            return '<tr>' +
                '<td class="ps-4 fw-bold">' + escapeHtml(ticket.ticket_number || '') + '</td>' +
                '<td>' + escapeHtml(ticket.title || '') + '</td>' +
                '<td><span class="badge ' + statusClass + '">' + escapeHtml(ticket.status_name || '-') + '</span></td>' +
                '<td><span class="badge ' + priorityClass + '">' + escapeHtml(ticket.priority_name || '-') + '</span></td>' +
                '<td>' + escapeHtml(ticket.category_name || '-') + '</td>' +
                '<td>' + (ticket.issue_name ? '<span class="badge bg-info">' + escapeHtml(ticket.issue_name) + '</span>' : '<span class="text-muted">-</span>') + '</td>' +
                '<td>' + escapeHtml(requesterName) + '</td>' +
                '<td>' + escapeHtml(agentName) + '</td>' +
                '<td><small class="text-muted">' + escapeHtml(ticket.created_at || 'N/A') + '</small></td>' +
                '<td>' + mlHtml + '</td>' +
                '<td class="pe-4"><a href="/admin/ticket/' + ticket.ticket_id + '" class="btn btn-sm btn-outline-primary"><i class="fa fa-eye"></i> <span class="btn-text">' + translateText('view', 'View') + '</span></a></td>' +
                '</tr>';
        }).join('');
    }

    function renderCustomers(rows) {
        if (!rows.length) {
            return '<tr><td colspan="7" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_customers', 'No matching customers') + '</td></tr>';
        }
        return rows.map(function (c) {
            var statusBadge = c.status === 'Active' ? '<span class="badge bg-success">' + escapeHtml(c.status) + '</span>' : '<span class="badge bg-danger">' + escapeHtml(c.status) + '</span>';
            return '<tr>' +
                '<td class="ps-4"><div class="d-flex align-items-center"><div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user"></i></div><div><div class="fw-semibold">' + escapeHtml(c.first_name) + ' ' + escapeHtml(c.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(c.email) + '</td>' +
                '<td>' + escapeHtml(c.mobile || translateText('not_available', 'N/A')) + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><span class="badge bg-primary rounded-pill px-3 py-2">' + (c.total_tickets || 0) + '</span></td>' +
                '<td>' + (c.created_at ? escapeHtml(c.created_at) : translateText('not_available', 'N/A')) + '</td>' +
                '<td><a href="/admin/customers/edit/' + c.user_id + '" class="btn btn-sm btn-primary mb-1"><i class="fa fa-edit"></i> ' + translateText('edit', 'Edit') + '</a></td>' +
                '</tr>';
        }).join('');
    }

    function renderAgents(rows) {
        if (!rows.length) {
            return '<tr><td colspan="9" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_agents', 'No matching agents') + '</td></tr>';
        }
        return rows.map(function (a) {
            var statusBadge = a.status === 'Active' ? '<span class="badge bg-success">' + escapeHtml(a.status) + '</span>' : '<span class="badge bg-danger">' + escapeHtml(a.status) + '</span>';
            return '<tr>' +
                '<td class="ps-4"><div class="d-flex align-items-center"><div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user-tie"></i></div><div><div class="fw-semibold">' + escapeHtml(a.first_name) + ' ' + escapeHtml(a.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(a.email) + '</td>' +
                '<td>' + escapeHtml(a.mobile || translateText('not_available', 'N/A')) + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><span class="badge bg-primary rounded-pill px-3 py-2">' + (a.total_tickets || 0) + '</span></td>' +
                '<td><span class="badge bg-success rounded-pill px-3 py-2">' + (a.resolved_tickets || 0) + '</span></td>' +
                '<td><span class="badge bg-warning text-dark rounded-pill px-3 py-2">' + (a.pending_tickets || 0) + '</span></td>' +
                '<td>' + (a.created_at ? escapeHtml(a.created_at) : translateText('not_available', 'N/A')) + '</td>' +
                '<td><button type="button" class="btn btn-sm btn-primary mb-1" ' +
                'data-bs-toggle="modal" data-bs-target="#editAgentModal" ' +
                'data-id="' + a.user_id + '" ' +
                'data-firstname="' + escapeHtml(a.first_name) + '" ' +
                'data-lastname="' + escapeHtml(a.last_name) + '" ' +
                'data-email="' + escapeHtml(a.email) + '" ' +
                'data-mobile="' + escapeHtml(a.mobile || '') + '" ' +
                'data-department="' + escapeHtml(a.department_id || '') + '" ' +
                'data-status="' + escapeHtml(a.status) + '" ' +
                'data-skills="' + escapeHtml(a.skill_ids || '') + '">' +
                '<i class="fa fa-edit"></i> ' + translateText('edit', 'Edit') +
                '</button>' +
                '<form method="POST" action="/admin/agents/delete/' + a.user_id + '" class="d-inline" onsubmit="return confirm(window.i18n ? i18n.t(\'delete_agent_confirmation\') : \'Delete this agent?\')"><button type="submit" class="btn btn-sm btn-danger mb-1"><i class="fa fa-trash"></i></button></form></td>' +
                '</tr>';
        }).join('');
    }

    function renderSkills(rows) {
        if (!rows.length) {
            return '<tr><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_skills', 'No matching skills') + '</td></tr>';
        }
        return rows.map(function (s, i) {
            var statusBadge = s.status === 'Active' ? '<span class="badge bg-success px-3 py-2">' + translateText('status_active', 'Active') + '</span>' : '<span class="badge bg-secondary px-3 py-2">' + translateText('status_inactive', 'Inactive') + '</span>';
            return '<tr>' +
                '<td>' + (i + 1) + '</td>' +
                '<td><i class="fa-solid fa-brain text-primary"></i> ' + escapeHtml(s.skill_name) + '</td>' +
                '<td>' + escapeHtml(s.department_name || '-') + '</td>' +
                '<td>' + escapeHtml(s.category_display || s.category || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td class="text-center"><a href="/admin/skills/edit/' + s.skill_id + '" class="btn btn-warning btn-sm h-auto me-1"><i class="fa-solid fa-pen"></i> ' + translateText('edit', 'Edit') + '</a>' +
                '<button class="btn btn-danger btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#deleteSkillModal" data-id="' + s.skill_id + '" data-name="' + escapeHtml(s.skill_name) + '"><i class="fa-solid fa-trash"></i> ' + translateText('delete', 'Delete') + '</button></td>' +
                '</tr>';
        }).join('');
    }

    function renderIssueTypes(rows) {
        if (!rows.length) {
            return '<tr><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_issue_types', 'No matching issue types') + '</td></tr>';
        }
        return rows.map(function (it) {
            var statusBadge = it.status === 'Active' ? '<span class="badge bg-success">' + translateText('status_active', 'Active') + '</span>' : '<span class="badge bg-secondary">' + translateText('status_inactive', 'Inactive') + '</span>';
            return '<tr>' +
                '<td>' + (it.issue_type_id) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(it.issue_name) + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(it.category_display || it.category_name || '-') + '</span></td>' +
                '<td>' + escapeHtml(it.description || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><button class="btn btn-warning btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#editIssueTypeModal' + it.issue_type_id + '"><i class="fa-solid fa-pen"></i> ' + translateText('edit', 'Edit') + '</button></td>' +
                '</tr>';
        }).join('');
    }

    function renderNotifications(rows) {
        if (!rows.length) {
            return '<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fa-regular fa-bell-slash d-block fs-3 mb-2 opacity-50"></i>' + translateText('no_matching_notifications', 'No matching notifications') + '</td></tr>';
        }
        return rows.map(function (n) {
            var statusBadge = n.is_read ? '<span class="badge bg-success">' + translateText('status_read', 'Read') + '</span>' : '<span class="badge bg-danger">' + translateText('status_unread', 'Unread') + '</span>';
            return '<tr data-notification-id="' + n.notification_id + '">' +
                '<td class="ps-4"><strong>' + escapeHtml(n.title) + '</strong></td>' +
                '<td class="text-muted" style="max-width: 300px;">' + escapeHtml(n.message ? n.message.substring(0, 80) : '') + (n.message && n.message.length > 80 ? '...' : '') + '</td>' +
                '<td class="text-center">' + statusBadge + '</td>' +
                '<td><small class="text-muted">' + (n.created_at ? escapeHtml(n.created_at) : translateText('not_available', 'N/A')) + '</small></td>' +
                '<td class="text-center">' +
                (n.is_read ? '' : '<a href="/admin/notifications/mark-read/' + n.notification_id + '" class="btn btn-sm btn-primary"><i class="fa-solid fa-check"></i></a>') +
                '<form method="POST" action="/admin/notifications/' + n.notification_id + '/delete" class="d-inline" onsubmit="return confirm(window.i18n ? i18n.t(\'delete_notification_confirmation\') : \'Delete this notification?\')"><button type="submit" class="btn btn-sm btn-danger"><i class="fa-solid fa-trash"></i></button></form>' +
                '</td>' +
                '</tr>';
        }).join('');
    }

    function renderMLPredictions(rows) {
        if (!rows.length) {
            return '<tr><td colspan="11" class="text-center py-5 text-muted"><i class="fa fa-inbox fa-3x text-muted mb-3"></i><p class="mb-0">' + translateText('no_matching_predictions', 'No matching predictions') + '</p></td></tr>';
        }
        return rows.map(function (p) {
            var slaHtml = p.sla_hours ? escapeHtml(p.sla_hours) + 'h' : '<span class="text-muted">' + translateText('not_available', 'N/A') + '</span>';
            var predictedHtml = p.predicted_minutes ? Math.floor(p.predicted_minutes / 60) + 'h ' + Math.round(p.predicted_minutes % 60) + 'm' : '<span class="text-muted">' + translateText('not_available', 'N/A') + '</span>';
            var actualHtml = p.actual_minutes ? Math.floor(p.actual_minutes / 60) + 'h ' + Math.round(p.actual_minutes % 60) + 'm' : '<span class="text-muted">' + translateText('awaiting', 'Awaiting') + '</span>';
            var errorHtml = p.error_minutes ? Math.floor(p.error_minutes / 60) + 'h ' + Math.round(p.error_minutes % 60) + 'm' : '<span class="text-muted">—</span>';
            return '<tr>' +
                '<td><a href="/support_manager/ticket/' + p.ticket_id + '" class="text-decoration-none fw-semibold">' + escapeHtml(p.ticket_number) + '</a></td>' +
                '<td>' + escapeHtml((p.title || '').substring(0, 50)) + (p.title && p.title.length > 50 ? '...' : '') + '</td>' +
                '<td>' + escapeHtml(p.priority_name || translateText('not_available', 'N/A')) + '</td>' +
                '<td>' + escapeHtml(p.status_name || translateText('not_available', 'N/A')) + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(p.model_version || translateText('not_available', 'N/A')) + '</span></td>' +
                '<td>' + predictedHtml + '</td>' +
                '<td>' + actualHtml + '</td>' +
                '<td>' + errorHtml + '</td>' +
                '<td>' + slaHtml + '</td>' +
                '<td><small class="text-muted">' + (p.prediction_created_at ? escapeHtml(p.prediction_created_at) : translateText('not_available', 'N/A')) + '</small></td>' +
                '<td><a href="/support_manager/ticket/' + p.ticket_id + '" class="btn btn-sm btn-outline-primary"><i class="fa fa-eye"></i> ' + translateText('view', 'View') + '</a></td>' +
                '</tr>';
        }).join('');
    }

    var renderers = {
        'tickets': renderTickets,
        'customers': renderCustomers,
        'agents': renderAgents,
        'skills': renderSkills,
        'issue-types': renderIssueTypes,
        'notifications': renderNotifications,
        'ml-predictions': renderMLPredictions
    };

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-ajax-search]').forEach(function (form) {
            var searchUrl = form.dataset.searchUrl;
            var tableBodySelector = form.dataset.tableTarget;
            var pageType = form.dataset.pageType;
            var tbody = document.querySelector(tableBodySelector);
            if (!searchUrl || !tbody || !pageType) return;

            var renderFn = renderers[pageType] || function (rows) { return ''; };
            var input = form.querySelector('input[name="search"]');
            var timer;

            function setLoading(loading) {
                if (loading) {
                    tbody.innerHTML = '<tr><td colspan="100" class="text-center py-4"><span class="spinner-border spinner-border-sm me-2"></span>' + translateText('searching', 'Searching...') + '</td></tr>';
                }
            }

            function doSearch() {
                var q = input ? input.value.trim() : '';
                var url = searchUrl;
                if (q) {
                    url += (url.includes('?') ? '&' : '?') + 'q=' + encodeURIComponent(q);
                }

                // Hide static pagination during search, restore when query is empty
                var paginationNav = document.getElementById('adminTicketsPagination') || document.querySelector('nav[aria-label="Ticket pagination"]');
                if (paginationNav) {
                    paginationNav.style.display = q ? 'none' : '';
                }

                setLoading(true);
                fetch(url)
                    .then(function (res) {
                        if (!res.ok) throw new Error('Network response was not ok (status ' + res.status + ')');
                        return res.json();
                    })
                    .then(function (data) {
                        var html = renderFn(data.rows || []);
                        tbody.innerHTML = html;
                        var countEl = document.getElementById(form.dataset.countTarget || '');
                        if (countEl && data.count !== undefined) {
                            countEl.textContent = data.count + ' ' + translateText('total', 'Total');
                        }
                    })
                    .catch(function (err) {
                        console.error('Search error:', err);
                        tbody.innerHTML = '<tr><td colspan="100" class="text-center py-4 text-danger">' + translateText('error_loading_results', 'Error loading results') + '</td></tr>';
                    });
            }

            if (input) {
                input.addEventListener('input', function () {
                    clearTimeout(timer);
                    timer = setTimeout(doSearch, DEBOUNCE_MS);
                });
            }

            form.addEventListener('submit', function (e) {
                e.preventDefault();
                clearTimeout(timer);
                doSearch();
            });
        });
    });
})();
