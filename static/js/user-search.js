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

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function renderUsers(rows) {
        if (!rows.length) {
            return '<tr><td colspan="8" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>No users found</td></tr>';
        }
        return rows.map(function(u) {
            var statusClass = u.status === 'Active' ? 'bg-success' : 'bg-danger';
            var statusText = u.status === 'Active' ? 'Active' : 'Inactive';
            var statusBadge = '<span class="badge ' + statusClass + ' user-status-toggle" style="cursor:pointer;" data-user-id="' + escapeHtml(u.user_id) + '" data-status="' + escapeHtml(u.status) + '">' + escapeHtml(statusText) + '</span>';
            return '<tr>' +
                '<td style="text-align:center;">' + escapeHtml(u.user_id) + '</td>' +
                '<td><div class="d-flex align-items-center"><div class="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user"></i></div><div><div class="fw-semibold">' + escapeHtml(u.first_name) + ' ' + escapeHtml(u.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(u.email) + '</td>' +
                '<td>' + escapeHtml(u.mobile || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td>' + escapeHtml(u.department_name || '-') + '</td>' +
                '<td>' + escapeHtml(u.role_name || '-') + '</td>' +
                '<td>' +
                    '<button class="btn btn-warning btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#editUserModal" data-id="' + escapeHtml(u.user_id) + '" data-first="' + escapeHtml(u.first_name) + '" data-last="' + escapeHtml(u.last_name) + '" data-email="' + escapeHtml(u.email) + '" data-mobile="' + escapeHtml(u.mobile) + '" data-status="' + escapeHtml(u.status) + '" data-department="' + escapeHtml(u.department_id || '') + '" data-role="' + escapeHtml(u.role_id || '') + '" data-skills="' + escapeHtml(u.skills || '') + '"><i class="fa fa-edit"></i></button>' +
                    '<button class="btn btn-danger btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#deleteUserModal" data-id="' + escapeHtml(u.user_id) + '" data-name="' + escapeHtml(u.first_name) + ' ' + escapeHtml(u.last_name) + '"><i class="fa fa-trash"></i></button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    function init() {
        var form = document.querySelector('form[data-user-search]');
        if (!form) return;

        var tbody = form.closest('.card-body').querySelector('tbody');
        if (!tbody) {
            tbody = document.querySelector('.table-scroll tbody');
        }
        if (!tbody) return;

        var input = form.querySelector('input[name="search"]');
        var statusSelect = form.querySelector('select[name="status"]');
        var timer;
        var abortController = null;

        function doSearch() {
            var q = input ? input.value.trim() : '';
            var status = statusSelect ? statusSelect.value : '';
            var url = '/users/api/users/search';
            var params = [];
            if (q) params.push('q=' + encodeURIComponent(q));
            if (status) params.push('status=' + encodeURIComponent(status));
            if (params.length) url += '?' + params.join('&');

            if (abortController) {
                abortController.abort();
            }
            abortController = new AbortController();

            fetch(url, { signal: abortController.signal })
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    var wasFocused = document.activeElement === input;
                    var cursorPos = wasFocused && input.selectionStart !== null ? input.selectionStart : -1;
                    tbody.innerHTML = renderUsers(data.rows || []);
                    if (wasFocused) {
                        input.focus();
                        if (cursorPos >= 0) {
                            input.setSelectionRange(cursorPos, cursorPos);
                        }
                    }
                })
                .catch(function (err) {
                    var wasFocused = document.activeElement === input;
                    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-danger">Error loading results</td></tr>';
                    if (wasFocused) {
                        input.focus();
                    }
                });
        }

        if (input) {
            input.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(doSearch, DEBOUNCE_MS);
            });
        }

        if (statusSelect) {
            statusSelect.addEventListener('change', function () {
                clearTimeout(timer);
                timer = setTimeout(doSearch, DEBOUNCE_MS);
            });
        }

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            clearTimeout(timer);
            doSearch();
        });

        document.addEventListener('click', function(e) {
            var badge = e.target.closest('.user-status-toggle');
            if (!badge) return;
            e.preventDefault();
            e.stopPropagation();
            var userId = badge.getAttribute('data-user-id');
            var currentStatus = badge.getAttribute('data-status');
            var newStatus = currentStatus === 'Active' ? 'Inactive' : 'Active';
            var csrfToken = getCsrfToken();
            fetch('/users/api/toggle-status/' + userId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(function(res) {
                if (!res.ok) throw new Error('Failed to update status');
                return res.json();
            })
            .then(function(data) {
                if (data.status === 'Active') {
                    badge.className = 'badge bg-success user-status-toggle';
                    badge.style.cursor = 'pointer';
                    badge.setAttribute('data-status', 'Active');
                    badge.textContent = 'Active';
                } else {
                    badge.className = 'badge bg-danger user-status-toggle';
                    badge.style.cursor = 'pointer';
                    badge.setAttribute('data-status', 'Inactive');
                    badge.textContent = 'Inactive';
                }
            })
            .catch(function() {
                alert('Failed to update status. Please try again.');
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
