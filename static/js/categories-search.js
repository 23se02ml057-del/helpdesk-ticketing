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

    function formatDate(dateStr) {
        if (!dateStr || dateStr === '-') return '-';
        try {
            var d = new Date(dateStr);
            if (isNaN(d.getTime())) return escapeHtml(dateStr);
            var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            var day = d.getDate();
            var month = months[d.getMonth()];
            var year = d.getFullYear();
            var hours = d.getHours();
            var minutes = d.getMinutes();
            var ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12;
            hours = hours ? hours : 12;
            hours = String(hours).padStart(2, '0');
            minutes = String(minutes).padStart(2, '0');
            return day + ' ' + month + ' ' + year + ', ' + hours + ':' + minutes + ' ' + ampm;
        } catch (e) {
            return escapeHtml(dateStr);
        }
    }

    function renderCategories(rows) {
        if (!rows.length) {
            return '<tr id="no-categories-row"><td colspan="4" class="text-center py-5 text-muted"><i class="fa-regular fa-folder-open d-block fs-3 mb-2 opacity-50"></i><div>No categories found</div><small class="text-muted">Try changing your search keyword.</small></td></tr>';
        }
        return rows.map(function(c, index) {
            var editData = 'data-category-name="' + escapeHtml(c.category_name) + '"';
            var deleteData = 'data-category-name="' + escapeHtml(c.category_name) + '"';
            return '<tr>' +
                '<td>' + (index + 1) + '</td>' +
                '<td class="fw-semibold">' + escapeHtml(c.category_name) + '</td>' +
                '<td class="category-created">' + formatDate(c.created_at) + '</td>' +
                '<td class="text-nowrap">' +
                    '<button class="btn btn-warning btn-sm me-1" data-bs-toggle="modal" data-bs-target="#editCategoryModal" ' + editData + '><i class="fa-solid fa-pen"></i> Edit</button>' +
                    '<button class="btn btn-danger btn-sm" data-bs-toggle="modal" data-bs-target="#deleteCategoryModal" ' + deleteData + '><i class="fa-solid fa-trash"></i> Delete</button>' +
                '</td>' +
            '</tr>';
        }).join('');
    }

    function formatAllDates() {
        document.querySelectorAll('.category-created').forEach(function (cell) {
            cell.innerHTML = formatDate(cell.textContent);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        formatAllDates();

        var form = document.querySelector('form[data-categories-search]');
        if (form) {
            var tbody = document.querySelector('#categories-tbody');
            var searchInput = form.querySelector('input[name="search"]');
            var clearBtn = document.getElementById('category-search-clear');
            var timer;

            function doSearch() {
                var q = searchInput ? searchInput.value.trim() : '';
                var url = '/api/categories/search';
                if (q) {
                    url += '?q=' + encodeURIComponent(q);
                }
                if (clearBtn) {
                    clearBtn.style.display = q ? 'inline-block' : 'none';
                }
                fetch(url)
                    .then(function (res) {
                        if (!res.ok) throw new Error('Network response was not ok');
                        return res.json();
                    })
                    .then(function (data) {
                        tbody.innerHTML = renderCategories(data.rows || []);
                        bindModalButtons();
                    })
                    .catch(function () {
                        tbody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-danger">Error loading results</td></tr>';
                    });
            }

            if (searchInput) {
                searchInput.addEventListener('input', function () {
                    clearTimeout(timer);
                    timer = setTimeout(doSearch, DEBOUNCE_MS);
                });
            }

            if (clearBtn) {
                clearBtn.addEventListener('click', function () {
                    searchInput.value = '';
                    clearTimeout(timer);
                    doSearch();
                    searchInput.focus();
                });
            }

            form.addEventListener('submit', function (e) {
                e.preventDefault();
                clearTimeout(timer);
                doSearch();
            });
        }

        function bindModalButtons() {
            document.querySelectorAll('#categories-tbody [data-bs-target="#editCategoryModal"]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var name = btn.getAttribute('data-category-name');
                    var desc = btn.getAttribute('data-category-description');
                    document.getElementById('edit-old-category').value = name;
                    document.getElementById('edit-category-name').value = name;
                });
            });
            document.querySelectorAll('#categories-tbody [data-bs-target="#deleteCategoryModal"]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var name = btn.getAttribute('data-category-name');
                    document.getElementById('delete-category-name').value = name;
                    var text = document.getElementById('delete-category-text');
                    if (text) {
                        var strong = text.querySelector('strong');
                        if (strong) strong.textContent = name;
                    }
                });
            });
        }

        bindModalButtons();
    });
})();
