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

    function renderIssueTypes(rows) {
        if (!rows.length) {
            return '<tr id="no-issue-types-row"><td colspan="6" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>No issue types found</td></tr>';
        }
        return rows.map(function(it, index) {
            var statusBadge = it.status === 'Active' ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Inactive</span>';
            return '<tr>' +
                '<td>' + (index + 1) + '</td>' +
                '<td>' + escapeHtml(it.issue_name) + '</td>' +
                '<td><span class="badge bg-info">' + escapeHtml(it.category_name) + '</span></td>' +
                '<td>' + escapeHtml(it.description || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td>' +
                    '<button class="btn btn-warning btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#editIssueTypeModal" data-id="' + it.issue_type_id + '" data-name="' + escapeHtml(it.issue_name) + '" data-category="' + escapeHtml(it.category_name) + '" data-description="' + escapeHtml(it.description || '') + '" data-status="' + escapeHtml(it.status) + '"><i class="fa-solid fa-pen"></i> Edit</button>' +
                    '<button class="btn btn-danger btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#deleteIssueTypeModal" data-id="' + it.issue_type_id + '" data-name="' + escapeHtml(it.issue_name) + '" data-status="' + escapeHtml(it.status) + '"><i class="fa-solid fa-trash"></i></button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-issue-type-search]');
        if (!form) return;

        var tbody = form.closest('.card-body').querySelector('tbody');
        if (!tbody) return;

        var searchInput = form.querySelector('input[name="search"]');
        var categorySelect = form.querySelector('select[name="category_name"]');
        var timer;

        function doSearch() {
            var q = searchInput ? searchInput.value.trim() : '';
            var category = categorySelect ? categorySelect.value : '';
            var url = '/api/issue-types/search';
            var params = [];
            if (q) params.push('q=' + encodeURIComponent(q));
            if (category) params.push('category_name=' + encodeURIComponent(category));
            if (params.length) url += '?' + params.join('&');
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderIssueTypes(data.rows || []);
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

        if (categorySelect) {
            categorySelect.addEventListener('change', function () {
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