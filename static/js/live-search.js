(function () {
    const DEBOUNCE_MS = 300;

    function setupLiveSearch(form) {
        const searchInput = form.querySelector('input[name="search"]');
        const selectInputs = form.querySelectorAll('select');
        let timer;
        let isSubmitting = false;

        function addLoading() {
            const inputs = form.querySelectorAll('input, select');
            inputs.forEach(function(el) { el.classList.add('search-loading'); });
        }

        function removeLoading() {
            const inputs = form.querySelectorAll('input, select');
            inputs.forEach(function(el) { el.classList.remove('search-loading'); });
        }

        function submitForm() {
            if (isSubmitting) return;
            isSubmitting = true;
            addLoading();
            form.submit();
        }

        if (searchInput) {
            searchInput.addEventListener('input', function () {
                clearTimeout(timer);
                removeLoading();

                if (!this.value.trim()) {
                    timer = setTimeout(function () {
                        submitForm();
                    }, DEBOUNCE_MS);
                    return;
                }

                timer = setTimeout(function () {
                    submitForm();
                }, DEBOUNCE_MS);
            });
        }

        selectInputs.forEach(function(select) {
            select.addEventListener('change', function () {
                clearTimeout(timer);
                removeLoading();
                timer = setTimeout(function () {
                    submitForm();
                }, DEBOUNCE_MS);
            });
        });

        form.addEventListener('submit', function () {
            isSubmitting = true;
            addLoading();
        });

        window.addEventListener('pageshow', function () {
            isSubmitting = false;
            removeLoading();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-live-search]').forEach(function (form) {
            setupLiveSearch(form);
        });
    });
})();
