/**
 * ⚡ Chaqmoq Academy - Theme Manager v2
 */

(function () {
    'use strict';

    const STORAGE_KEY = 'theme';
    const THEMES = {
        DARK: 'dark',
        LIGHT: 'light',
        SYSTEM: 'system'
    };

    /**
     * Get preferred theme
     */
    function getPreferredTheme() {
        return localStorage.getItem(STORAGE_KEY) || THEMES.DARK;
    }

    /**
     * Apply theme
     */
    function applyTheme(theme) {
        let activeTheme = theme;

        if (theme === THEMES.SYSTEM) {
            activeTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
                ? THEMES.DARK
                : THEMES.LIGHT;
        }

        document.documentElement.setAttribute('data-theme', activeTheme);

        // Update all toggle elements
        updateToggleUI(activeTheme);
    }

    /**
     * Updated UI elements (Icons, Tooltips)
     */
    function updateToggleUI(activeTheme) {
        const toggleBtns = document.querySelectorAll('.theme-toggle-btn');

        toggleBtns.forEach(btn => {
            const icon = btn.querySelector('i');
            if (icon) {
                if (activeTheme === THEMES.DARK) {
                    icon.className = 'fa-solid fa-sun'; // Show sun to switch to light
                } else {
                    icon.className = 'fa-solid fa-moon'; // Show moon to switch to dark
                }
            }

            // Update tooltip text if using data-title or title
            const label = activeTheme === THEMES.DARK ? 'Light Mode' : 'Dark Mode';
            if (btn.hasAttribute('data-title')) btn.setAttribute('data-title', label);
            if (btn.hasAttribute('title')) btn.setAttribute('title', label);
        });
    }

    /**
     * Global Toggle Function
     */
    window.toggleTheme = function () {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === THEMES.DARK ? THEMES.LIGHT : THEMES.DARK;
        localStorage.setItem(STORAGE_KEY, next);
        applyTheme(next);
    };

    /**
     * Set specific theme
     */
    window.setTheme = function (theme) {
        localStorage.setItem(STORAGE_KEY, theme);
        applyTheme(theme);
    };

    // Initialize
    function init() {
        const theme = getPreferredTheme();
        applyTheme(theme);

        // System preference listener
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (localStorage.getItem(STORAGE_KEY) === THEMES.SYSTEM) {
                applyTheme(THEMES.SYSTEM);
            }
        });
    }

    // Run when script loads
    init();

    // Re-run UI update after DOM content loaded to catch all buttons
    document.addEventListener('DOMContentLoaded', () => {
        updateToggleUI(document.documentElement.getAttribute('data-theme'));
    });

})();
