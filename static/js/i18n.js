// JavaScript Internationalization (i18n) System
// Provides client-side translation support

(function() {
    'use strict';

    // Translation catalog - loaded from server
    let translations = {};
    let currentLocale = 'en';

    // Initialize i18n
    function init(locale, catalog) {
        currentLocale = locale || 'en';
        translations = catalog || {};
    }

    // Get translated string
    function t(key) {
        if (!key) return '';
        if (translations[key] !== undefined) {
            return translations[key];
        }
        return key;
    }

    // Translate all elements with data-i18n attribute
    function translateDOM() {
        // Translate elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            const key = el.getAttribute('data-i18n');
            const translation = t(key);
            if (translation !== key) {
                el.textContent = translation;
            }
        });

        // Translate elements with data-i18n-placeholder attribute
        document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
            const key = el.getAttribute('data-i18n-placeholder');
            const translation = t(key);
            if (translation !== key) {
                el.setAttribute('placeholder', translation);
            }
        });

        // Translate elements with data-i18n-title attribute
        document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
            const key = el.getAttribute('data-i18n-title');
            const translation = t(key);
            if (translation !== key) {
                el.setAttribute('title', translation);
            }
        });

        // Translate elements with data-i18n-aria-label attribute
        document.querySelectorAll('[data-i18n-aria-label]').forEach(function(el) {
            const key = el.getAttribute('data-i18n-aria-label');
            const translation = t(key);
            if (translation !== key) {
                el.setAttribute('aria-label', translation);
            }
        });

        // Update document lang attribute
        document.documentElement.lang = currentLocale;
    }

    // Shorthand for confirm dialog with translation
    function confirmT(key) {
        return confirm(t(key));
    }

    // Shorthand for alert dialog with translation
    function alertT(key) {
        alert(t(key));
    }

    // Expose globally
    window.i18n = {
        init: init,
        t: t,
        translateDOM: translateDOM,
        confirmT: confirmT,
        alertT: alertT,
        getLocale: function() { return currentLocale; }
    };

    // Auto-translate on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', translateDOM);
    } else {
        translateDOM();
    }
})();
