(function () {
    const DEBOUNCE_MS = 300;
    let activeController = null;
    let requestSequence = 0;

    function escapeHtml(value) {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function translate(key, fallback) {
        if (window.i18n && typeof window.i18n.t === 'function') {
            var translated = window.i18n.t(key);
            return translated && translated !== key ? translated : fallback;
        }
        return fallback;
    }

    function statusClass(status) {
        if (status === 'Open') return 'bg-danger';
        if (status === 'In Progress') return 'bg-warning text-dark';
        if (status === 'Resolved') return 'bg-success';
        if (status === 'Closed') return 'bg-secondary';
        if (status === 'On Hold') return 'bg-info';
        if (status === 'New') return 'bg-primary';
        return 'bg-secondary';
    }

    function statusLabel(status) {
        if (status === 'Open') return translate('status_open', status);
        if (status === 'In Progress') return translate('status_in_progress', status);
        if (status === 'On Hold') return translate('status_on_hold', status);
        if (status === 'Resolved') return translate('status_resolved', status);
        if (status === 'Closed') return translate('status_closed', status);
        if (status === 'New') return translate('status_new', status);
        return status || '-';
    }


    function formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            var d = new Date(dateStr);
            if (isNaN(d.getTime())) return '-';
            var day = String(d.getDate()).padStart(2, '0');
            var month = d.toLocaleDateString('en-US', { month: 'short' });
            var year = d.getFullYear();
            return day + ' ' + month + ' ' + year;
        } catch (e) {
            return '-';
        }
    }

    function renderTickets(rows) {
        if (!Array.isArray(rows)) return '';
        if (!rows.length) {
            return '<tr id="no-tickets-row"><td colspan="11" class="text-center py-5 text-muted bg-white"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>' + translate('no_support_tickets_found', 'No support tickets found') + '</td></tr>';
        }
        return rows.map(function (ticket, index) {
            var ticketId = Number(ticket.ticket_id);
            var ticketNumber = ticket.ticket_number || '';
            var title = ticket.title || '';
            var description = ticket.description || '';
            var category = ticket.category_name || '-';
            var priority = ticket.priority_name || '-';
            var status = ticket.status_name || '';
            var requester = [ticket.requester_first, ticket.requester_last].filter(Boolean).join(' ') || '-';
            var agent = [ticket.agent_first, ticket.agent_last].filter(Boolean).join(' ') || '-';
            var issue = ticket.issue_name ? '<span class="badge bg-info">' + escapeHtml(ticket.issue_name) + '</span>' : '<span class="text-muted">-</span>';
            var safeId = Number.isInteger(ticketId) ? ticketId : 0;
            var requesterId = ticket.requester_id || '';
            var assignedTo = ticket.assigned_to || '';
            var issueTypeId = ticket.issue_type_id || '';
            var departmentId = ticket.department_id || '';
            return '<tr>' +
                '<td class="ps-4 text-muted">' + (index + 1) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(ticketNumber) + '</td>' +
                '<td>' + escapeHtml(title) + '</td>' +
                '<td>' + escapeHtml(category) + '</td>' +
                '<td><span class="badge ' + (priority === 'High' || priority === 'Critical' ? 'bg-danger' : priority === 'Medium' ? 'bg-warning text-dark' : priority === 'Low' ? 'bg-success' : 'bg-secondary') + '">' + escapeHtml(priority) + '</span></td>' +
                '<td><span class="badge ' + statusClass(status) + '">' + escapeHtml(statusLabel(status)) + '</span></td>' +
                '<td>' + escapeHtml(requester) + '</td>' +
                '<td>' + escapeHtml(agent) + '</td>' +
                '<td>' + issue + '</td>' +
                '<td class="sa-col-date">' + formatDate(ticket.created_at) + '</td>' +
                '<td class="text-center"><div class="d-inline-flex gap-2">' +
                    '<a href="/super-admin/tickets/' + safeId + '" class="btn btn-sm btn-outline-primary"><i class="fa fa-eye"></i> <span class="btn-text">' + translate('view', 'View') + '</span></a>' +
                    '<button class="btn btn-warning btn-sm h-auto text-dark" data-bs-toggle="modal" data-bs-target="#editTicketModal" data-id="' + safeId + '" data-number="' + escapeHtml(ticketNumber) + '" data-title="' + escapeHtml(title) + '" data-description="' + escapeHtml(description) + '" data-category="' + escapeHtml(ticket.category_name || '') + '" data-priority="' + escapeHtml(priority) + '" data-status="' + escapeHtml(status) + '" data-requester-id="' + escapeHtml(requesterId) + '" data-assigned-to="' + escapeHtml(assignedTo) + '" data-issue-type-id="' + escapeHtml(issueTypeId) + '" data-department-id="' + escapeHtml(departmentId) + '"><i class="fa-solid fa-pen"></i> <span class="btn-text">' + translate('edit', 'Edit') + '</span></button>' +
                    '<button class="btn btn-danger btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#deleteTicketModal" data-id="' + safeId + '" data-number="' + escapeHtml(ticketNumber) + '"><i class="fa-solid fa-trash"></i> <span class="btn-text">' + translate('delete', 'Delete') + '</span></button>' +
                '</div></td>' +
            '</tr>';
        }).join('');
    }

    function updatePagination(data) {
        var page = Number(data.page) || 1;
        var perPage = Number(data.per_page) || 10;
        var total = Math.max(Number(data.total) || 0, 0);
        var totalPages = Math.max(Number(data.total_pages) || 1, 1);
        var start = total > 0 ? (page - 1) * perPage + 1 : 0;
        var end = Math.min(page * perPage, total);
        var showingStart = document.querySelector('.pagination-showing-start');
        var showingEnd = document.querySelector('.pagination-showing-end');
        var showingTotal = document.querySelector('.pagination-showing-total');
        var pageIndicator = document.querySelector('.pagination-page-indicator');
        var prevBtn = document.querySelector('.pagination-prev');
        var prevItem = prevBtn ? prevBtn.closest('.page-item') : null;
        var nextBtn = document.querySelector('.pagination-next');
        var nextItem = nextBtn ? nextBtn.closest('.page-item') : null;

        if (showingStart) showingStart.textContent = start;
        if (showingEnd) showingEnd.textContent = end;
        if (showingTotal) showingTotal.textContent = total;
        if (pageIndicator) {
            pageIndicator.textContent = 'Page ' + page + ' of ' + totalPages;
            pageIndicator.dataset.page = page;
            pageIndicator.dataset.totalPages = totalPages;
        }

        if (prevBtn && prevItem) {
            var hasPrev = page > 1 && Boolean(data.has_prev);
            prevItem.classList.toggle('disabled', !hasPrev);
            prevBtn.classList.remove('disabled');
            prevItem.setAttribute('aria-disabled', hasPrev ? 'false' : 'true');
            prevBtn.setAttribute('aria-disabled', hasPrev ? 'false' : 'true');
            prevBtn.tabIndex = hasPrev ? 0 : -1;
            prevBtn.dataset.page = hasPrev ? page - 1 : page;
        }
        if (nextBtn && nextItem) {
            var hasNext = page < totalPages && Boolean(data.has_next);
            nextItem.classList.toggle('disabled', !hasNext);
            nextBtn.classList.remove('disabled');
            nextItem.setAttribute('aria-disabled', hasNext ? 'false' : 'true');
            nextBtn.setAttribute('aria-disabled', hasNext ? 'false' : 'true');
            nextBtn.tabIndex = hasNext ? 0 : -1;
            nextBtn.dataset.page = hasNext ? page + 1 : page;
        }
    }

    function setLoading(loading) {
        var status = document.getElementById('ticketSearchStatus');
        if (status) status.classList.toggle('d-none', !loading);
    }

    function showError() {
        var tbody = document.getElementById('ticketsTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center py-4 text-danger">' + translate('error_loading_results', 'Error loading results') + '</td></tr>';
        }
    }

    function parseResponse(response) {
        var contentType = response.headers.get('content-type') || '';
        if (!response.ok) throw new Error('Request failed');
        if (contentType.indexOf('application/json') === -1) throw new Error('Invalid response');
        return response.json().then(function (data) {
            if (!data || !Array.isArray(data.tickets)) throw new Error('Invalid response');
            return data;
        });
    }

    function buildUrl(page) {
        var form = document.querySelector('form[data-ticket-search]');
        var input = form ? form.querySelector('input[name="search"]') : null;
        var statusSelect = form ? form.querySelector('select[name="status"]') : null;
        var apiUrl = form && form.dataset.apiUrl ? form.dataset.apiUrl : '/api/tickets/search';
        var params = new URLSearchParams();
        var search = input ? input.value.trim() : '';
        var status = statusSelect ? statusSelect.value.trim() : '';
        if (search) params.set('search', search);
        if (status) params.set('status', status);
        params.set('page', page);
        return apiUrl + '?' + params.toString();
    }

    function doPageRequest(url) {
        if (activeController) activeController.abort();
        if (typeof AbortController === 'undefined') {
            fetch(url, { headers: { Accept: 'application/json' } })
                .then(parseResponse)
                .then(function (data) {
                    var tbody = document.getElementById('ticketsTableBody');
                    if (tbody) tbody.innerHTML = renderTickets(data.tickets);
                    updatePagination(data);
                })
                .catch(showError);
            return;
        }

        activeController = new AbortController();
        var controller = activeController;
        var sequence = ++requestSequence;
        setLoading(true);
        fetch(url, {
            headers: { Accept: 'application/json' },
            signal: controller.signal
        })
            .then(parseResponse)
            .then(function (data) {
                if (sequence !== requestSequence) return;
                var tbody = document.getElementById('ticketsTableBody');
                if (tbody) tbody.innerHTML = renderTickets(data.tickets);
                updatePagination(data);
            })
            .catch(function (error) {
                if (error.name === 'AbortError' || sequence !== requestSequence) return;
                showError();
            })
            .finally(function () {
                if (sequence === requestSequence) setLoading(false);
            });
    }

    function doSearch(page) {
        doPageRequest(buildUrl(page || 1));
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-ticket-search]');
        var tbody = document.getElementById('ticketsTableBody');
        if (!form || !tbody) return;

        var input = form.querySelector('input[name="search"]');
        var statusSelect = form.querySelector('select[name="status"]');
        var timer = null;

        if (input) {
            input.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(function () { doSearch(1); }, DEBOUNCE_MS);
            });
        }

        if (statusSelect) {
            statusSelect.addEventListener('change', function () { doSearch(1); });
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            clearTimeout(timer);
            doSearch(1);
        });

        var pageIndicator = document.querySelector('.pagination-page-indicator');
        var prevBtn = document.querySelector('.pagination-prev');
        var nextBtn = document.querySelector('.pagination-next');
        if (prevBtn) {
            var prevItem = prevBtn.closest('.page-item');
            prevBtn.addEventListener('click', function (event) {
                event.preventDefault();
                if (!prevItem || prevItem.classList.contains('disabled')) return;
                var currentPage = Number(pageIndicator && pageIndicator.dataset.page) || 1;
                var previousPage = currentPage - 1;
                if (previousPage < 1) return;
                doPageRequest(buildUrl(previousPage));
            });
        }
        if (nextBtn) {
            var nextItem = nextBtn.closest('.page-item');
            nextBtn.addEventListener('click', function (event) {
                event.preventDefault();
                if (!nextItem || nextItem.classList.contains('disabled')) return;
                var currentPage = Number(pageIndicator && pageIndicator.dataset.page) || 1;
                var totalPages = Number(pageIndicator && pageIndicator.dataset.totalPages) || 1;
                var nextPage = currentPage + 1;
                if (nextPage > totalPages) return;
                doPageRequest(buildUrl(nextPage));
            });
        }

        var editModal = document.getElementById('editTicketModal');
        if (editModal) {
            editModal.addEventListener('show.bs.modal', function (event) {
                var button = event.relatedTarget;
                if (!button) return;
                var id = button.getAttribute('data-id');
                var number = button.getAttribute('data-number');
                var title = button.getAttribute('data-title');
                var description = button.getAttribute('data-description');
                var category = button.getAttribute('data-category');
                var priority = button.getAttribute('data-priority');
                var status = button.getAttribute('data-status');
                var requesterId = button.getAttribute('data-requester-id');
                var assignedTo = button.getAttribute('data-assigned-to');
                var issueTypeId = button.getAttribute('data-issue-type-id');
                var departmentId = button.getAttribute('data-department-id');

                document.getElementById('editTicketId').value = id || '';
                document.getElementById('editTicketNumber').value = number || '';
                document.getElementById('editTitle').value = title || '';
                document.getElementById('editDescription').value = description || '';
                document.getElementById('editCategory').value = category || '';
                document.getElementById('editPriority').value = priority || '';
                document.getElementById('editStatus').value = status || '';
                document.getElementById('editRequester').value = requesterId || '';
                document.getElementById('editAssignedTo').value = assignedTo || '';
                document.getElementById('editIssueType').value = issueTypeId || '';
                document.getElementById('editDepartment').value = departmentId || '';

                var editForm = document.getElementById('editForm');
                if (editForm && id) {
                    editForm.action = '/edit-ticket/' + id;
                }
            });
        }

        var deleteModal = document.getElementById('deleteTicketModal');
        if (deleteModal) {
            deleteModal.addEventListener('show.bs.modal', function (event) {
                var button = event.relatedTarget;
                if (!button) return;
                var id = button.getAttribute('data-id');
                var number = button.getAttribute('data-number');

                var deleteTicketNumber = document.getElementById('deleteTicketNumber');
                if (deleteTicketNumber) {
                    deleteTicketNumber.textContent = number || '';
                }

                var deleteForm = document.getElementById('deleteForm');
                if (deleteForm && id) {
                    deleteForm.action = '/delete-ticket/' + id;
                }
            });
        }
    });
})();
