(function () {
    "use strict";

    function getRole() {
        const htmlRole = document.documentElement.getAttribute("data-role-theme-role");
        if (htmlRole) {
            return htmlRole;
        }

        const body = document.body;
        if (!body) {
            return null;
        }

        const roles = ["superadmin", "director", "manager", "teacher", "student", "parent"];
        return roles.find((role) => body.classList.contains("role-" + role)) || null;
    }

    function getConfig(role) {
        if (!role) {
            return null;
        }

        const config = {
            role: role,
            attr: "data-role-theme",
            storageKey: "chaqmoq_" + role + "_theme",
        };

        if (role === "student") {
            config.legacyAttr = "data-student-theme";
        } else if (role === "parent") {
            config.legacyAttr = "data-parent-theme";
        }

        return config;
    }

    function getStoredTheme(config) {
        try {
            return localStorage.getItem(config.storageKey) === "light" ? "light" : "dark";
        } catch (error) {
            return "dark";
        }
    }

    function persistTheme(config, theme) {
        try {
            localStorage.setItem(config.storageKey, theme);
        } catch (error) {
            // Ignore storage failures.
        }
    }

    function updateButtons(role, theme) {
        const currentLabel = theme === "light" ? "Light" : "Dark";
        const nextLabel = theme === "light" ? "Dark" : "Light";

        document.querySelectorAll('.js-role-theme-toggle[data-theme-role="' + role + '"]').forEach((button) => {
            button.setAttribute("aria-pressed", String(theme === "light"));
            button.setAttribute("aria-label", nextLabel + " rejimga o'tish");
            button.setAttribute("title", nextLabel + " rejimga o'tish");

            const icon = button.querySelector(".js-role-theme-icon");
            if (icon) {
                icon.className = theme === "light"
                    ? "fa-solid fa-lightbulb js-role-theme-icon"
                    : "fa-regular fa-lightbulb js-role-theme-icon";
            }

            const label = button.querySelector(".js-role-theme-label");
            if (label) {
                label.textContent = currentLabel;
            }
        });
    }

    function applyTheme(role, theme) {
        const config = getConfig(role);
        if (!config) {
            return;
        }

        const activeTheme = theme === "light" ? "light" : "dark";
        const previousTheme = document.documentElement.getAttribute(config.attr) === "light" ? "light" : "dark";
        document.documentElement.setAttribute(config.attr, activeTheme);
        document.documentElement.setAttribute("data-role-theme-role", role);

        if (config.legacyAttr) {
            document.documentElement.setAttribute(config.legacyAttr, activeTheme);
        }

        document.documentElement.style.colorScheme = activeTheme;
        persistTheme(config, activeTheme);
        updateButtons(role, activeTheme);

        document.dispatchEvent(new CustomEvent("role-theme:change", {
            detail: {
                role: role,
                theme: activeTheme,
                previousTheme: previousTheme,
            },
        }));
    }

    function init() {
        const role = getRole();
        const config = getConfig(role);
        if (!role || !config) {
            return;
        }

        applyTheme(role, getStoredTheme(config));

        document.querySelectorAll('.js-role-theme-toggle[data-theme-role="' + role + '"]').forEach((button) => {
            button.addEventListener("click", function () {
                const currentTheme = document.documentElement.getAttribute(config.attr) === "light" ? "light" : "dark";
                applyTheme(role, currentTheme === "dark" ? "light" : "dark");
            });
        });

        window.toggleRoleTheme = function toggleRoleTheme() {
            const currentTheme = document.documentElement.getAttribute(config.attr) === "light" ? "light" : "dark";
            applyTheme(role, currentTheme === "dark" ? "light" : "dark");
        };
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
