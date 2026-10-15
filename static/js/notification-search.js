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

    function renderNotifications(rows) {
        if (!rows.length) {
            return '<tr id="no-notifications-row"><td colspan="6" class="text-center text-danger">No Notifications Found</td></tr>';
        }
        return rows.map(function(n) {
            var statusBadge = n.is_read
                ? '<span class="badge bg-success">Read</span>'
                : '<span class="badge bg-danger">Unread</span>';
            return '<tr>' +
                '<td class="text-center">' + escapeHtml(n.notification_id) + '</td>' +
                '<td>' + escapeHtml(n.first_name) + ' ' + escapeHtml(n.last_name) + '</td>' +
                '<td><strong>' + escapeHtml(n.title) + '</strong></td>' +
                '<td>' + escapeHtml(n.message) + '</td>' +
                '<td class="text-center">' + statusBadge + '</td>' +
                '<td>' + escapeHtml(n.created_at) + '</td>' +
            '</tr>';
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-notification-search]');
        if (!form) return;

        var tableScroll = form.closest('.table-scroll');
        var tbody = tableScroll ? tableScroll.querySelector('tbody') : null;
        if (!tbody) return;

        var searchInput = form.querySelector('input[name="search"]');
        var isReadSelect = form.querySelector('select[name="is_read"]');
        var dateFromInput = form.querySelector('input[name="date_from"]');
        var dateToInput = form.querySelector('input[name="date_to"]');
        var timer;

        function doSearch() {
            var q = searchInput ? searchInput.value.trim() : '';
            var isRead = isReadSelect ? isReadSelect.value : '';
            var dateFrom = dateFromInput ? dateFromInput.value : '';
            var dateTo = dateToInput ? dateToInput.value : '';
            var url = '/api/notification-report/search';
            var params = [];
            if (q) params.push('q=' + encodeURIComponent(q));
            if (isRead) params.push('is_read=' + encodeURIComponent(isRead));
            if (dateFrom) params.push('date_from=' + encodeURIComponent(dateFrom));
            if (dateTo) params.push('date_to=' + encodeURIComponent(dateTo));
            if (params.length) url += '?' + params.join('&');
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderNotifications(data.rows || []);
                })
                .catch(function () {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-danger">Error loading results</td></tr>';
                });
        }

        if (searchInput) {
            searchInput.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(doSearch, DEBOUNCE_MS);
            });
        }

        if (isReadSelect) {
            isReadSelect.addEventListener('change', function () {
                clearTimeout(timer);
                timer = setTimeout(doSearch, DEBOUNCE_MS);
            });
        }

        if (dateFromInput) {
            dateFromInput.addEventListener('change', function () {
                clearTimeout(timer);
                timer = setTimeout(doSearch, DEBOUNCE_MS);
            });
        }

        if (dateToInput) {
            dateToInput.addEventListener('change', function () {
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
})();