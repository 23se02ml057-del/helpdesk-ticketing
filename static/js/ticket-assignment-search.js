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

    function renderAssignments(rows) {
        if (!rows.length) {
            return '<tr id="no-ticket-assignments-row"><td colspan="5" class="text-center text-danger">No tickets found</td></tr>';
        }
        return rows.map(function(a, index) {
            var assignedText = a.first_name
                ? escapeHtml(a.first_name) + ' ' + escapeHtml(a.last_name)
                : '<span class="text-danger">Not assigned</span>';
            return '<tr>' +
                '<td>' + (index + 1) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(a.ticket_number) + '</td>' +
                '<td>' + escapeHtml(a.title) + '</td>' +
                '<td>' + assignedText + '</td>' +
                '<td>' +
                    '<button class="btn btn-success btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#assignModal" data-ticket-id="' + a.ticket_id + '" data-ticket-number="' + escapeHtml(a.ticket_number) + '" data-ticket-title="' + escapeHtml(a.title) + '"><i class="fa-solid fa-user-plus me-1"></i> Assign</button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-ticket-assignment-search]');
        if (!form) return;

        var tbody = document.querySelector('.table-scroll tbody');
        if (!tbody) return;

        var input = form.querySelector('input[name="search"]');
        var timer;

        function doSearch() {
            var q = input ? input.value.trim() : '';
            var url = '/api/ticket-assignment/search';
            if (q) {
                url += '?q=' + encodeURIComponent(q);
            }
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderAssignments(data.rows || []);
                })
                .catch(function () {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-danger">Error loading results</td></tr>';
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
})();