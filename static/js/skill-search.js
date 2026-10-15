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

    function renderSkills(rows) {
        if (!rows.length) {
            return '<tr id="no-skills-row"><td colspan="6" class="text-center py-4 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i>No skills found</td></tr>';
        }
        return rows.map(function(s, index) {
            var statusBadge = s.status === 'Active' ? '<span class="badge bg-success px-3 py-2">Active</span>' : '<span class="badge bg-secondary px-3 py-2">Inactive</span>';
            return '<tr>' +
                '<td>' + (index + 1) + '</td>' +
                '<td><i class="fa-solid fa-brain text-primary"></i> ' + escapeHtml(s.skill_name) + '</td>' +
                '<td>' + escapeHtml(s.department_name || '-') + '</td>' +
                '<td>' + escapeHtml(s.category_display || s.category || '-') + '</td>' +
                '<td>' + statusBadge + '</td>' +
                '<td class="text-center">' +
                    '<button class="btn btn-warning btn-sm h-auto me-1" data-bs-toggle="modal" data-bs-target="#editSkillModal" data-id="' + s.skill_id + '" data-name="' + escapeHtml(s.skill_name) + '" data-category="' + escapeHtml(s.category || '') + '" data-status="' + escapeHtml(s.status) + '" data-department="' + escapeHtml(s.department_name || '') + '"><i class="fa-solid fa-pen"></i> Edit</button>' +
                    '<button class="btn btn-danger btn-sm h-auto" data-bs-toggle="modal" data-bs-target="#deleteSkillModal" data-id="' + s.skill_id + '" data-name="' + escapeHtml(s.skill_name) + '"><i class="fa-solid fa-trash"></i></button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form[data-skill-search]');
        if (!form) return;

        var cardBody = form.closest('.card-body');
        var tbody = cardBody ? cardBody.querySelector('tbody') : null;
        if (!tbody) return;

        var searchInput = form.querySelector('input[name="search"]');
        var departmentSelect = form.querySelector('select[name="department_id"]');
        var categorySelect = form.querySelector('select[name="category_name"]');
        var timer;

        function doSearch() {
            var q = searchInput ? searchInput.value.trim() : '';
            var dept = departmentSelect ? departmentSelect.value : '';
            var cat = categorySelect ? categorySelect.value : '';
            var url = '/api/skills/search';
            var params = [];
            if (q) params.push('q=' + encodeURIComponent(q));
            if (dept) params.push('department_id=' + encodeURIComponent(dept));
            if (cat) params.push('category_name=' + encodeURIComponent(cat));
            if (params.length) url += '?' + params.join('&');
            fetch(url)
                .then(function (res) {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                })
                .then(function (data) {
                    tbody.innerHTML = renderSkills(data.rows || []);
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

        if (departmentSelect) {
            departmentSelect.addEventListener('change', function () {
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