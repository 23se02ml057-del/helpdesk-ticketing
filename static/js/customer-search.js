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

    function renderCustomers(rows) {
        if (!rows.length) {
            return '<tr id="no-customers-row"><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>No customers found</td></tr>';
        }
        return rows.map(function(c) {
            var statusBadge = c.status === 'Active' ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-danger">Inactive</span>';
            return '<tr id="customer-row-' + c.user_id + '">' +
                '<td><div class="d-flex align-items-center"><div class="bg-info text-white rounded-circle d-flex justify-content-center align-items-center me-2" style="width:35px; height:35px; font-size:14px;"><i class="fa fa-user"></i></div><div><div class="fw-semibold">' + escapeHtml(c.first_name) + ' ' + escapeHtml(c.last_name) + '</div></div></div></td>' +
                '<td>' + escapeHtml(c.email) + '</td>' +
                '<td>' + escapeHtml(c.mobile || 'N/A') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td>' + escapeHtml(c.created_at || 'N/A') + '</td>' +
                '<td>' +
                    '<button class="btn btn-warning btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#editCustomerModal" data-id="' + c.user_id + '" data-first="' + escapeHtml(c.first_name) + '" data-last="' + escapeHtml(c.last_name) + '" data-email="' + escapeHtml(c.email) + '" data-mobile="' + escapeHtml(c.mobile || '') + '" data-status="' + escapeHtml(c.status) + '"><i class="fa fa-edit"></i></button>' +
                    '<button class="btn btn-danger btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#deleteCustomerModal" data-id="' + c.user_id + '" data-name="' + escapeHtml(c.first_name) + ' ' + escapeHtml(c.last_name) + '"><i class="fa fa-trash"></i></button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    function init() {
        var form = document.querySelector('form[data-customer-search]');
        if (!form) return;

        var tableScroll = document.querySelector('.table-scroll');
        var tbody = tableScroll ? tableScroll.querySelector('tbody') : null;
        if (!tbody) {
            tbody = form.closest('.card-body').querySelector('tbody');
        }
        if (!tbody) return;

        var input = form.querySelector('input[name="search"]');
        var statusSelect = form.querySelector('select[name="status"]');
        var timer;

        function doSearch() {
            var q = input ? input.value.trim() : '';
            var status = statusSelect ? statusSelect.value : '';
            var url = '/admin/api/customers/search';
            var params = [];
            if (q) params.push('q=' + encodeURIComponent(q));
            if (status) params.push('status=' + encodeURIComponent(status));
            if (params.length) url += '?' + params.join('&');
            
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    var wasFocused = document.activeElement === input;
                    var cursorPos = wasFocused && input.selectionStart !== null ? input.selectionStart : -1;
                    tbody.innerHTML = renderCustomers(data.rows || []);
                    if (wasFocused) {
                        input.focus();
                        if (cursorPos >= 0) {
                            input.setSelectionRange(cursorPos, cursorPos);
                        }
                    }
                })
                .catch(function () {
                    var wasFocused = document.activeElement === input;
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-danger">Error loading results</td></tr>';
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
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();