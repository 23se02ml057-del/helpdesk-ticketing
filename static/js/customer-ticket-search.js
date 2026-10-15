(function () {
    const DEBOUNCE_MS = 300;

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"');
    }

    function renderTickets(rows) {
        if (!rows.length) {
            return '<tr id="no-customer-tickets-row"><td colspan="8" class="text-center py-5 text-muted bg-white"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>No tickets found</td></tr>';
        }
        var viewLabel = window.i18n ? i18n.t('view') : 'View';
        return rows.map(function (t, index) {
            var statusBadge = '';
            if (t.status_name === 'Open') {
                statusBadge = '<span class="badge bg-danger">' + escapeHtml(t.status_name) + '</span>';
            } else if (t.status_name === 'In Progress') {
                statusBadge = '<span class="badge bg-primary">' + escapeHtml(t.status_name) + '</span>';
            } else if (t.status_name === 'Pending') {
                statusBadge = '<span class="badge bg-warning text-dark">' + escapeHtml(t.status_name) + '</span>';
            } else if (t.status_name === 'On Hold') {
                statusBadge = '<span class="badge bg-secondary">' + escapeHtml(t.status_name) + '</span>';
            } else if (t.status_name === 'Resolved') {
                statusBadge = '<span class="badge bg-success">' + escapeHtml(t.status_name) + '</span>';
            } else if (t.status_name === 'Closed') {
                statusBadge = '<span class="badge bg-dark">' + escapeHtml(t.status_name) + '</span>';
            } else {
                statusBadge = '<span class="badge bg-info">' + escapeHtml(t.status_name || 'N/A') + '</span>';
            }

            var viewUrl = window.TICKET_DETAIL_URL ? window.TICKET_DETAIL_URL.replace('/0', '/' + t.ticket_id).replace('=0', '=' + t.ticket_id) : '/customer-tickets/' + t.ticket_id;

            return '<tr>' +
                '<td class="ps-4 text-muted">' + (index + 1) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(t.ticket_number) + '</td>' +
                '<td>' + escapeHtml(t.title) + '</td>' +
                '<td>' + escapeHtml(t.category_name || '-') + '</td>' +
                '<td>' + (t.issue_name ? '<span class="badge bg-info">' + escapeHtml(t.issue_name) + '</span>' : '<span class="text-muted">-</span>') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td>' + escapeHtml(t.created_at) + '</td>' +
                '<td class="text-center">' +
                '<a href="' + viewUrl + '" class="btn btn-sm btn-primary"><i class="fa-solid fa-eye"></i> ' + viewLabel + '</a>' +
                '</td>' +
                '</tr>';
        }).join('');
    }

    // Expose globally for pagination handler
    window.renderCustomerTickets = renderTickets;

    function updateUrlParams(params) {
        var queryString = Array.isArray(params) ? params.join('&') : params;
        var newUrl = window.location.pathname + (queryString ? '?' + queryString : '');
        window.history.replaceState({}, '', newUrl);
    }

    function getCurrentPage() {
        var params = new URLSearchParams(window.location.search);
        return parseInt(params.get('page')) || 1;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-customer-ticket-search]');
        if (!form) return;

        var tbody = document.querySelector('table tbody');
        if (!tbody) return;

        var input = form.querySelector('input[name="search"]');
        var statusFilter = document.getElementById('statusFilter');
        var timer;

        function doSearch(page) {
            var q = input ? input.value.trim() : '';
            var url = '/api/customer-tickets/search';
            var params = [];
            if (q) {
                params.push('q=' + encodeURIComponent(q));
            }
            if (statusFilter && statusFilter.value) {
                params.push('status=' + encodeURIComponent(statusFilter.value));
            }
            var currentPage = page || getCurrentPage();
            params.push('page=' + encodeURIComponent(currentPage));
            if (params.length) {
                url += '?' + params.join('&');
            }

            var wasFocused = document.activeElement === input;
            var cursorPos = wasFocused && input.selectionStart !== null ? input.selectionStart : -1;

            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderTickets(data.rows || []);
                    updateUrlParams(['q=' + encodeURIComponent(q),
                    statusFilter && statusFilter.value ? 'status=' + encodeURIComponent(statusFilter.value) : '',
                    'page=' + currentPage].filter(Boolean).join('&'));
                    if (wasFocused) {
                        input.focus();
                        if (cursorPos >= 0) {
                            input.setSelectionRange(cursorPos, cursorPos);
                        }
                    }
                })
                .catch(function () {
                    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-danger">Error loading results</td></tr>';
                    if (wasFocused) {
                        input.focus();
                    }
                });
        }

        if (input) {
            input.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(function () { doSearch(1); }, DEBOUNCE_MS);
            });
        }

        if (statusFilter) {
            statusFilter.addEventListener('change', function () {
                clearTimeout(timer);
                timer = setTimeout(function () { doSearch(1); }, DEBOUNCE_MS);
            });
        }

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            clearTimeout(timer);
            doSearch(1);
        });
    });
})();