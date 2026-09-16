(() => {
    "use strict";

    const root = document.documentElement;
    const storageKey = "theme";

    const isValidTheme = (theme) => {
        return theme === "light" || theme === "dark";
    };

    const getSystemTheme = () => {
        return window.matchMedia?.("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light";
    };

    const getSavedTheme = () => {
        try {
            const savedTheme = localStorage.getItem(storageKey);

            return isValidTheme(savedTheme)
                ? savedTheme
                : getSystemTheme();
        } catch {
            return getSystemTheme();
        }
    };

    const saveTheme = (theme) => {
        try {
            localStorage.setItem(storageKey, theme);
        } catch {
        }
    };

    const updateButton = () => {
        const button = document.querySelector(
            "[data-aumiau-theme-toggle]"
        );

        if (!button) {
            return;
        }

        const isDark = root.dataset.theme === "dark";

        const label = isDark
            ? "Ativar tema claro"
            : "Ativar tema escuro";

        button.setAttribute("aria-pressed", String(isDark));
        button.setAttribute("aria-label", label);
        button.title = label;
    };

    const applyTheme = (theme, persist = false) => {
        const selectedTheme = isValidTheme(theme)
            ? theme
            : getSystemTheme();

        root.dataset.theme = selectedTheme;
        root.style.colorScheme = selectedTheme;

        if (persist) {
            saveTheme(selectedTheme);
        }

        updateButton();
    };

    // Converte o antigo estado "auto" em claro ou escuro.
    applyTheme(getSavedTheme(), true);

    document.addEventListener("DOMContentLoaded", () => {
        const button = document.querySelector(
            "[data-aumiau-theme-toggle]"
        );

        const profileMenu = document.querySelector(
            "[data-admin-profile-menu]"
        );

        updateButton();

        button?.addEventListener("click", () => {
            const nextTheme =
                root.dataset.theme === "dark"
                    ? "light"
                    : "dark";

            applyTheme(nextTheme, true);
        });

        document.addEventListener("click", (event) => {
            if (
                profileMenu?.open &&
                !profileMenu.contains(event.target)
            ) {
                profileMenu.removeAttribute("open");
            }
        });

        document.addEventListener("keydown", (event) => {
            if (
                event.key === "Escape" &&
                profileMenu?.open
            ) {
                profileMenu.removeAttribute("open");
            }
        });
    });

    window.addEventListener("storage", (event) => {
        if (
            event.key === storageKey &&
            isValidTheme(event.newValue)
        ) {
            applyTheme(event.newValue);
        }
    });
})();