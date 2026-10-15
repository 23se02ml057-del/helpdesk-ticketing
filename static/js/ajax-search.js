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

    const t = window.i18n ? function (key) { return i18n.t(key); } : function (key) { return key; };

    function renderTickets(rows) {
        if (!rows.length) {
            return '<tr><td colspan="11" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_tickets') + '</td></tr>';
        }
        return rows.map(function (t) {
            var statusClass = 'bg-secondary';
            if (t.status_name === 'Open') statusClass = 'bg-danger';
            else if (t.status_name === 'In Progress') statusClass = 'bg-warning text-dark';
            else if (t.status_name === 'Resolved') statusClass = 'bg-success';
            else if (t.status_name === 'Closed') statusClass = 'bg-secondary';
            else if (t.status_name === 'On Hold') statusClass = 'bg-info';
            else if (t.status_name === 'New') statusClass = 'bg-primary';

            var priorityClass = 'bg-secondary';
            if (t.priority_name === 'Critical' || t.priority_name === 'High') priorityClass = 'bg-danger';
            else if (t.priority_name === 'Medium') priorityClass = 'bg-warning text-dark';
            else if (t.priority_name === 'Low') priorityClass = 'bg-success';

            var mlHtml = '<span class="text-muted">-</span>';
            if (t.ml_minutes) {
                var hours = Math.floor(t.ml_minutes / 60);
                var mins = Math.round(t.ml_minutes % 60);
                mlHtml = hours + t('hours') + ' ' + mins + t('minutes');
                if (t.ml_model) {
                    mlHtml += '<small class="text-muted d-block">v' + escapeHtml(t.ml_model) + '</small>';
                }
            }

            return '<tr>' +
                '<td class="ps-4 fw-bold">' + escapeHtml(t.ticket_number) + '</td>' +
                '<td>' + escapeHtml(t.title) + '</td>' +
                '<td><span class="badge ' + statusClass + '">' + escapeHtml(t.status_name || '-') + '</span></td>' +
                '<td><span class="badge ' + priorityClass + '">' + escapeHtml(t.priority_name || '-') + '</span></td>' +
                '<td>' + escapeHtml(t.category_name || '-') + '</td>' +
                '<td>' + (t.issue_name ? '<span class="badge bg-info">' + escapeHtml(t.issue_name) + '</span>' : '<span class="text-muted">-</span>') + '</td>' +
                '<td>' + escapeHtml((t.requester_first || '') + ' ' + (t.requester_last || '')) + '</td>' +
                '<td>' + escapeHtml((t.agent_first || '') + ' ' + (t.agent_last || '')) + '</td>' +
                '<td><small class="text-muted">' + (t.created_at ? escapeHtml(t.created_at) : t('not_available')) + '</small></td>' +
                '<td>' + mlHtml + '</td>' +
                '<td class="pe-4"><a href="/super-admin/tickets/' + t.ticket_id + '" class="btn btn-sm btn-outline-primary"><i class="fa fa-eye"></i> <span class="btn-text">' + t('view') + '</span></a></td>' +
                '</tr>';
        }).join('');
    }

    function renderCustomers(rows) {
        if (!rows.length) {
            return '<tr><td colspan="7" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_customers') + '</td></tr>';
        }
        return rows.map(function (c) {
            var statusBadge = c.status === 'Active' ? '<span class="badge bg-success">' + escapeHtml(c.status) + '</span>' : '<span class="badge bg-danger">' + escapeHtml(c.status) + '</span>';
            return '<tr>' +
                '<td class="ps-4"><div class="d-flex align-items-center"><div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user"></i></div><div><div class="fw-semibold">' + escapeHtml(c.first_name) + ' ' + escapeHtml(c.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(c.email) + '</td>' +
                '<td>' + escapeHtml(c.mobile || t('not_available')) + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><span class="badge bg-primary rounded-pill px-3 py-2">' + (c.total_tickets || 0) + '</span></td>' +
                '<td>' + (c.created_at ? escapeHtml(c.created_at) : t('not_available')) + '</td>' +
                '<td><a href="/admin/customers/edit/' + c.user_id + '" class="btn btn-sm btn-primary mb-1"><i class="fa fa-edit"></i> ' + t('edit') + '</a></td>' +
                '</tr>';
        }).join('');
    }

    function renderAgents(rows) {
        if (!rows.length) {
            return '<tr><td colspan="9" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_agents') + '</td></tr>';
        }
        return rows.map(function (a) {
            var statusBadge = a.status === 'Active' ? '<span class="badge bg-success">' + escapeHtml(a.status) + '</span>' : '<span class="badge bg-danger">' + escapeHtml(a.status) + '</span>';
            return '<tr>' +
                '<td class="ps-4"><div class="d-flex align-items-center"><div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user-tie"></i></div><div><div class="fw-semibold">' + escapeHtml(a.first_name) + ' ' + escapeHtml(a.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(a.email) + '</td>' +
                '<td>' + escapeHtml(a.mobile || t('not_available')) + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><span class="badge bg-primary rounded-pill px-3 py-2">' + (a.total_tickets || 0) + '</span></td>' +
                '<td><span class="badge bg-success rounded-pill px-3 py-2">' + (a.resolved_tickets || 0) + '</span></td>' +
                '<td><span class="badge bg-warning text-dark rounded-pill px-3 py-2">' + (a.pending_tickets || 0) + '</span></td>' +
                '<td>' + (a.created_at ? escapeHtml(a.created_at) : t('not_available')) + '</td>' +
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
                '<i class="fa fa-edit"></i> ' + t('edit') +
                '</button>' +
                '<form method="POST" action="/admin/agents/delete/' + a.user_id + '" class="d-inline" onsubmit="return confirm(window.i18n ? i18n.t(\'delete_agent_confirmation\') : \'Delete this agent?\')"><button type="submit" class="btn btn-sm btn-danger mb-1"><i class="fa fa-trash"></i></button></form></td>' +
                '</tr>';
        }).join('');
    }

    function renderSkills(rows) {
        if (!rows.length) {
            return '<tr><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_skills') + '</td></tr>';
        }
        return rows.map(function (s, i) {
            var statusBadge = s.status === 'Active' ? '<span class="badge bg-success px-3 py-2">' + t('status_active') + '</span>' : '<span class="badge bg-secondary px-3 py-2">' + t('status_inactive') + '</span>';
            return '<tr>' +
                '<td>' + (i + 1) + '</td>' +
                '<td><i class="fa-solid fa-brain text-primary"></i> ' + escapeHtml(s.skill_name) + '</td>' +
                '<td>' + escapeHtml(s.department_name || '-') + '</td>' +
                '<td>' + escapeHtml(s.category_display || s.category || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td class="text-center"><a href="/admin/skills/edit/' + s.skill_id + '" class="btn btn-warning btn-sm h-auto me-1"><i class="fa-solid fa-pen"></i> ' + t('edit') + '</a>' +
                '<button class="btn btn-danger btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#deleteSkillModal" data-id="' + s.skill_id + '" data-name="' + escapeHtml(s.skill_name) + '"><i class="fa-solid fa-trash"></i> ' + t('delete') + '</button></td>' +
                '</tr>';
        }).join('');
    }

    function renderIssueTypes(rows) {
        if (!rows.length) {
            return '<tr><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_issue_types') + '</td></tr>';
        }
        return rows.map(function (it) {
            var statusBadge = it.status === 'Active' ? '<span class="badge bg-success">' + t('status_active') + '</span>' : '<span class="badge bg-secondary">' + t('status_inactive') + '</span>';
            return '<tr>' +
                '<td>' + (it.issue_type_id) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(it.issue_name) + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(it.category_display || it.category_name || '-') + '</span></td>' +
                '<td>' + escapeHtml(it.description || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td><button class="btn btn-warning btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#editIssueTypeModal' + it.issue_type_id + '"><i class="fa-solid fa-pen"></i> ' + t('edit') + '</button></td>' +
                '</tr>';
        }).join('');
    }

    function renderNotifications(rows) {
        if (!rows.length) {
            return '<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fa-regular fa-bell-slash d-block fs-3 mb-2 opacity-50"></i>' + t('no_matching_notifications') + '</td></tr>';
        }
        return rows.map(function (n) {
            var statusBadge = n.is_read ? '<span class="badge bg-success">' + t('status_read') + '</span>' : '<span class="badge bg-danger">' + t('status_unread') + '</span>';
            return '<tr data-notification-id="' + n.notification_id + '">' +
                '<td class="ps-4"><strong>' + escapeHtml(n.title) + '</strong></td>' +
                '<td class="text-muted" style="max-width: 300px;">' + escapeHtml(n.message ? n.message.substring(0, 80) : '') + (n.message && n.message.length > 80 ? '...' : '') + '</td>' +
                '<td class="text-center">' + statusBadge + '</td>' +
                '<td><small class="text-muted">' + (n.created_at ? escapeHtml(n.created_at) : t('not_available')) + '</small></td>' +
                '<td class="text-center">' +
                (n.is_read ? '' : '<a href="/admin/notifications/mark-read/' + n.notification_id + '" class="btn btn-sm btn-primary"><i class="fa-solid fa-check"></i></a>') +
                '<form method="POST" action="/admin/notifications/' + n.notification_id + '/delete" class="d-inline" onsubmit="return confirm(window.i18n ? i18n.t(\'delete_notification_confirmation\') : \'Delete this notification?\')"><button type="submit" class="btn btn-sm btn-danger"><i class="fa-solid fa-trash"></i></button></form>' +
                '</td>' +
                '</tr>';
        }).join('');
    }

    function renderMLPredictions(rows) {
        if (!rows.length) {
            return '<tr><td colspan="11" class="text-center py-5 text-muted"><i class="fa fa-inbox fa-3x text-muted mb-3"></i><p class="mb-0">' + t('no_matching_predictions') + '</p></td></tr>';
        }
        return rows.map(function (p) {
            var slaHtml = p.sla_hours ? escapeHtml(p.sla_hours) + t('hours') : '<span class="text-muted">' + t('not_available') + '</span>';
            var predictedHtml = p.predicted_minutes ? Math.floor(p.predicted_minutes / 60) + t('hours') + ' ' + Math.round(p.predicted_minutes % 60) + t('minutes') : '<span class="text-muted">' + t('not_available') + '</span>';
            var actualHtml = p.actual_minutes ? Math.floor(p.actual_minutes / 60) + t('hours') + ' ' + Math.round(p.actual_minutes % 60) + t('minutes') : '<span class="text-muted">' + t('awaiting') + '</span>';
            var errorHtml = p.error_minutes ? Math.floor(p.error_minutes / 60) + t('hours') + ' ' + Math.round(p.error_minutes % 60) + t('minutes') : '<span class="text-muted">—</span>';
            return '<tr>' +
                '<td><a href="/support_manager/ticket/' + p.ticket_id + '" class="text-decoration-none fw-semibold">' + escapeHtml(p.ticket_number) + '</a></td>' +
                '<td>' + escapeHtml((p.title || '').substring(0, 50)) + (p.title && p.title.length > 50 ? '...' : '') + '</td>' +
                '<td>' + escapeHtml(p.priority_name || t('not_available')) + '</td>' +
                '<td>' + escapeHtml(p.status_name || t('not_available')) + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(p.model_version || t('not_available')) + '</span></td>' +
                '<td>' + predictedHtml + '</td>' +
                '<td>' + actualHtml + '</td>' +
                '<td>' + errorHtml + '</td>' +
                '<td>' + slaHtml + '</td>' +
                '<td><small class="text-muted">' + (p.prediction_created_at ? escapeHtml(p.prediction_created_at) : t('not_available')) + '</small></td>' +
                '<td><a href="/support_manager/ticket/' + p.ticket_id + '" class="btn btn-sm btn-outline-primary"><i class="fa fa-eye"></i> ' + t('view') + '</a></td>' +
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
            var emptyMessage = form.dataset.emptyMessage || t('no_matching_records');
            var emptyIcon = form.dataset.emptyIcon || 'fa-inbox';
            var tbody = document.querySelector(tableBodySelector);
            if (!searchUrl || !tbody || !pageType) return;

            var renderFn = renderers[pageType] || function (rows) { return ''; };
            var input = form.querySelector('input[name="search"]');
            var timer;

            function setLoading(loading) {
                if (loading) {
                    tbody.innerHTML = '<tr><td colspan="100" class="text-center py-4"><span class="spinner-border spinner-border-sm me-2"></span>' + t('searching') + '</td></tr>';
                }
            }

            function doSearch() {
                var q = input ? input.value.trim() : '';
                var url = searchUrl;
                if (q) {
                    url += (url.includes('?') ? '&' : '?') + 'q=' + encodeURIComponent(q);
                }
                setLoading(true);
                fetch(url)
                    .then(function (res) {
                        if (!res.ok) throw new Error('Network response was not ok');
                        return res.json();
                    })
                    .then(function (data) {
                        var html = renderFn(data.rows || []);
                        tbody.innerHTML = html;
                        var countEl = document.getElementById(form.dataset.countTarget || '');
                        if (countEl && data.count !== undefined) {
                            countEl.textContent = data.count + ' ' + t('total');
                        }
                    })
                    .catch(function () {
                        tbody.innerHTML = '<tr><td colspan="100" class="text-center py-4 text-danger">' + t('error_loading_results') + '</td></tr>';
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
