document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-plan-form]");
    if (!form) {
        return;
    }

    const langButtons = Array.from(form.querySelectorAll("[data-lang-tab]"));
    const langPanels = Array.from(form.querySelectorAll("[data-lang-panel]"));
    const featureList = form.querySelector("[data-feature-list]");
    const addFeatureButton = form.querySelector("[data-feature-add]");
    const featureTemplate = document.getElementById("plan-feature-row-template");

    const unsavedIndicator = form.querySelector("[data-unsaved-indicator]");

    const previewName = form.querySelector("[data-preview-name]");
    const previewRange = form.querySelector("[data-preview-range]");
    const previewPrice = form.querySelector("[data-preview-price]");
    const previewOld = form.querySelector("[data-preview-old]");
    const previewDiscount = form.querySelector("[data-preview-discount]");
    const previewBadge = form.querySelector("[data-preview-badge]");
    const previewFeatures = form.querySelector("[data-preview-features]");
    const previewMore = form.querySelector("[data-preview-more]");

    const fieldByName = (name) => form.querySelector(`[name="${name}"]`);
    const valueByName = (name) => {
        const field = fieldByName(name);
        return field ? field.value.trim() : "";
    };

    const checkedByName = (name) => {
        const field = fieldByName(name);
        return Boolean(field && field.checked);
    };

    let activeLang = "uz";

    const getInitialLangFromErrors = () => {
        const errorPanel = form.querySelector(".pp-lang-panel .mkt-error");
        if (!errorPanel) {
            return "uz";
        }
        const panel = errorPanel.closest("[data-lang-panel]");
        return panel ? panel.getAttribute("data-lang-panel") || "uz" : "uz";
    };

    const setFeatureLangVisibility = () => {
        if (!featureList) {
            return;
        }
        featureList.querySelectorAll("[data-lang-field]").forEach((node) => {
            const nodeLang = node.getAttribute("data-lang-field");
            node.hidden = nodeLang !== activeLang;
        });
    };

    const applyLang = (lang) => {
        activeLang = lang;

        langButtons.forEach((button) => {
            const isActive = button.getAttribute("data-lang-tab") === lang;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
        });

        langPanels.forEach((panel) => {
            const isActive = panel.getAttribute("data-lang-panel") === lang;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });

        setFeatureLangVisibility();
        refreshPreview();
    };

    const getFeatureRows = () => {
        if (!featureList) {
            return [];
        }
        return Array.from(featureList.querySelectorAll("[data-feature-row]"));
    };

    const updateRowIdentifiers = (rowElement, rowIndex) => {
        const index = rowIndex + 1;
        const orderNode = rowElement.querySelector("[data-feature-order]");
        if (orderNode) {
            orderNode.textContent = String(index);
        }

        const idMap = [
            { selector: "[data-feature-base]", id: `feature-base-${index}` },
            { selector: "[data-feature-uz]", id: `feature-uz-${index}` },
            { selector: "[data-feature-ru]", id: `feature-ru-${index}` },
            { selector: "[data-feature-en]", id: `feature-en-${index}` },
        ];

        idMap.forEach((entry) => {
            const input = rowElement.querySelector(entry.selector);
            if (!input) {
                return;
            }
            input.id = entry.id;
            const label = input.closest(".pp-field")?.querySelector("label");
            if (label) {
                label.setAttribute("for", entry.id);
            }
        });
    };

    const refreshFeatureRows = () => {
        const rows = getFeatureRows();
        rows.forEach((rowElement, index) => {
            updateRowIdentifiers(rowElement, index);

            const upButton = rowElement.querySelector("[data-feature-up]");
            const downButton = rowElement.querySelector("[data-feature-down]");
            const removeButton = rowElement.querySelector("[data-feature-remove]");

            if (upButton) {
                upButton.disabled = index === 0;
            }
            if (downButton) {
                downButton.disabled = index === rows.length - 1;
            }
            if (removeButton) {
                removeButton.disabled = rows.length === 1;
            }
        });

        setFeatureLangVisibility();
    };

    const createFeatureRow = () => {
        if (!featureTemplate) {
            return null;
        }

        const wrapper = document.createElement("div");
        const nextIndex = getFeatureRows().length + 1;
        wrapper.innerHTML = featureTemplate.innerHTML.replaceAll("__index__", String(nextIndex)).trim();

        const rowElement = wrapper.firstElementChild;
        if (!rowElement) {
            return null;
        }
        return rowElement;
    };

    const formatPrice = (value) => {
        if (!value) {
            return "0";
        }
        const normalized = value.replace(/\s+/g, "").replace(/,/g, ".");
        const parsed = Number.parseFloat(normalized);
        if (Number.isNaN(parsed)) {
            return value;
        }
        return new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 0 }).format(parsed);
    };

    const localizedValue = (baseName, mapByLang) => {
        const localizedName = mapByLang[activeLang];
        if (!localizedName) {
            return valueByName(baseName);
        }
        return valueByName(localizedName) || valueByName(baseName);
    };

    const featureTextFromRow = (rowElement) => {
        if (!rowElement) {
            return "";
        }

        const baseInput = rowElement.querySelector("[data-feature-base]");
        const localInput = rowElement.querySelector(`[data-feature-${activeLang}]`);

        const localValue = localInput ? localInput.value.trim() : "";
        const baseValue = baseInput ? baseInput.value.trim() : "";
        return localValue || baseValue;
    };

    function refreshPreview() {
        const planName = localizedValue("name", { uz: "name_uz", ru: "name_ru", en: "name_en" }) || "Tarif nomi";
        const studentRange =
            localizedValue("student_range", { uz: "student_range_uz", ru: "student_range_ru", en: "student_range_en" }) ||
            "O'quvchi limiti";

        const badgeText =
            localizedValue("badge_text", { uz: "badge_text_uz", ru: "badge_text_ru", en: "badge_text_en" }) ||
            (checkedByName("is_recommended") ? "Tavsiya etiladi" : "");

        const discountText =
            localizedValue("discount_label", {
                uz: "discount_label_uz",
                ru: "discount_label_ru",
                en: "discount_label_en",
            }) || "";

        if (previewName) {
            previewName.textContent = planName;
        }
        if (previewRange) {
            previewRange.textContent = studentRange;
        }

        if (previewPrice) {
            previewPrice.textContent = formatPrice(valueByName("current_price"));
        }

        if (previewOld) {
            const oldValue = valueByName("old_price");
            if (oldValue) {
                previewOld.hidden = false;
                previewOld.textContent = `${formatPrice(oldValue)} so'm`;
            } else {
                previewOld.hidden = true;
                previewOld.textContent = "";
            }
        }

        if (previewDiscount) {
            if (discountText) {
                previewDiscount.hidden = false;
                previewDiscount.textContent = discountText;
            } else {
                previewDiscount.hidden = true;
                previewDiscount.textContent = "";
            }
        }

        if (previewBadge) {
            if (badgeText) {
                previewBadge.hidden = false;
                previewBadge.textContent = badgeText;
            } else {
                previewBadge.hidden = true;
                previewBadge.textContent = "";
            }
        }

        const featureValues = getFeatureRows()
            .map((rowElement) => featureTextFromRow(rowElement))
            .filter((itemText) => itemText.length > 0);

        if (previewFeatures) {
            previewFeatures.innerHTML = "";
            const previewItems = featureValues.slice(0, 6);
            if (!previewItems.length) {
                const li = document.createElement("li");
                li.textContent = "Feature kiriting";
                previewFeatures.appendChild(li);
            } else {
                previewItems.forEach((itemText) => {
                    const li = document.createElement("li");
                    li.textContent = itemText;
                    previewFeatures.appendChild(li);
                });
            }
        }

        if (previewMore) {
            const extraCount = Math.max(0, featureValues.length - 6);
            if (extraCount > 0) {
                previewMore.hidden = false;
                previewMore.textContent = `+${extraCount} ta qo'shimcha feature`;
            } else {
                previewMore.hidden = true;
                previewMore.textContent = "";
            }
        }
    }

    const serializeForm = () => {
        const formData = new FormData(form);
        return Array.from(formData.entries())
            .map(([key, value]) => `${key}=${value}`)
            .join("||");
    };

    let initialSnapshot = "";

    const syncDirtyState = () => {
        if (!unsavedIndicator) {
            return;
        }

        const isDirty = serializeForm() !== initialSnapshot;
        unsavedIndicator.classList.toggle("is-dirty", isDirty);
        unsavedIndicator.textContent = isDirty
            ? "Saqlanmagan o'zgarishlar bor"
            : "Saqlanmagan o'zgarishlar yo'q";
    };

    if (addFeatureButton && featureList) {
        addFeatureButton.addEventListener("click", () => {
            const rowElement = createFeatureRow();
            if (!rowElement) {
                return;
            }
            featureList.appendChild(rowElement);
            refreshFeatureRows();
            refreshPreview();
            syncDirtyState();

            const firstInput = rowElement.querySelector("[data-feature-base]");
            if (firstInput) {
                firstInput.focus();
            }
        });
    }

    if (featureList) {
        featureList.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }

            const rowElement = target.closest("[data-feature-row]");
            if (!rowElement) {
                return;
            }

            if (target.closest("[data-feature-remove]")) {
                const rows = getFeatureRows();
                if (rows.length === 1) {
                    rowElement.querySelectorAll("input[type='text']").forEach((input) => {
                        input.value = "";
                    });
                    const idInput = rowElement.querySelector("input[name='feature_id[]']");
                    if (idInput) {
                        idInput.value = "";
                    }
                } else {
                    rowElement.remove();
                }
                refreshFeatureRows();
                refreshPreview();
                syncDirtyState();
                return;
            }

            if (target.closest("[data-feature-up]")) {
                const previousRow = rowElement.previousElementSibling;
                if (previousRow) {
                    featureList.insertBefore(rowElement, previousRow);
                    refreshFeatureRows();
                    refreshPreview();
                    syncDirtyState();
                }
                return;
            }

            if (target.closest("[data-feature-down]")) {
                const nextRow = rowElement.nextElementSibling;
                if (nextRow) {
                    featureList.insertBefore(nextRow, rowElement);
                    refreshFeatureRows();
                    refreshPreview();
                    syncDirtyState();
                }
            }
        });
    }

    langButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const lang = button.getAttribute("data-lang-tab") || "uz";
            applyLang(lang);
        });
    });

    form.addEventListener("input", () => {
        refreshPreview();
        syncDirtyState();
    });

    form.addEventListener("change", () => {
        refreshPreview();
        syncDirtyState();
    });

    window.addEventListener("beforeunload", (event) => {
        if (serializeForm() === initialSnapshot) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });

    form.addEventListener("submit", () => {
        initialSnapshot = serializeForm();
    });

    refreshFeatureRows();
    applyLang(getInitialLangFromErrors());
    initialSnapshot = serializeForm();
    syncDirtyState();
    refreshPreview();
});
