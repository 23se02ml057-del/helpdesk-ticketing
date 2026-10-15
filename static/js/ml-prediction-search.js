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

    function renderPredictions(rows) {
        if (!rows.length) {
            return '<tr id="no-ml-predictions-row"><td colspan="10" class="text-center py-5 text-muted"><i class="fa fa-inbox fa-3x text-muted mb-3"></i><p class="mb-0">No ML predictions found</p></td></tr>';
        }
        return rows.map(function(p) {
            var slaHtml = p.sla_hours ? escapeHtml(p.sla_hours) + 'h' : '<span class="text-muted">N/A</span>';
            var predictedHtml = p.predicted_minutes ? Math.floor(p.predicted_minutes / 60) + 'h ' + Math.round(p.predicted_minutes % 60) + 'min' : '<span class="text-muted">N/A</span>';
            var actualHtml = p.actual_minutes ? Math.floor(p.actual_minutes / 60) + 'h ' + Math.round(p.actual_minutes % 60) + 'min' : '<span class="text-muted">Awaiting</span>';
            var errorHtml = p.error_minutes ? Math.floor(p.error_minutes / 60) + 'h ' + Math.round(p.error_minutes % 60) + 'min' : '<span class="text-muted">—</span>';
            return '<tr>' +
                '<td><a href="/super-admin/tickets/' + p.ticket_id + '" class="text-decoration-none">' + escapeHtml(p.ticket_number) + '</a></td>' +
                '<td>' + escapeHtml((p.title || '').substring(0, 50)) + (p.title && p.title.length > 50 ? '...' : '') + '</td>' +
                '<td>' + escapeHtml(p.priority_name || 'N/A') + '</td>' +
                '<td>' + escapeHtml(p.status_name || 'N/A') + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(p.model_version || 'N/A') + '</span></td>' +
                '<td>' + predictedHtml + '</td>' +
                '<td>' + actualHtml + '</td>' +
                '<td>' + errorHtml + '</td>' +
                '<td>' + slaHtml + '</td>' +
                '<td><small class="text-muted">' + escapeHtml(p.prediction_created_at || 'N/A') + '</small></td>' +
            '</tr>';
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-ml-prediction-search]');
        if (!form) return;

        var tbody = form.closest('.table-responsive').querySelector('tbody');
        if (!tbody) return;

        var input = form.querySelector('input[name="search"]');
        var timer;

        function doSearch() {
            var q = input ? input.value.trim() : '';
            var url = '/api/ml-prediction-history/search';
            if (q) {
                url += '?q=' + encodeURIComponent(q);
            }
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderPredictions(data.rows || []);
                })
                .catch(function () {
                    tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-danger">Error loading results</td></tr>';
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