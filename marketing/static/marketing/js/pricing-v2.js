document.addEventListener("DOMContentLoaded", () => {
    const compareToggle = document.querySelector("[data-pricing-compare-toggle]");
    const comparePanel = document.querySelector("[data-pricing-compare]");
    const durationButtons = Array.from(document.querySelectorAll("[data-duration-btn]"));
    const compareRows = Array.from(document.querySelectorAll(".pricing-v2-compare-table tbody tr[data-duration]"));

    const activeDuration = () => {
        const activeBtn = durationButtons.find((button) => button.classList.contains("active"));
        return activeBtn ? activeBtn.getAttribute("data-duration-btn") || "all" : "all";
    };

    const syncCompareRows = () => {
        if (!compareRows.length) {
            return;
        }
        const selectedDuration = activeDuration();
        compareRows.forEach((row) => {
            row.hidden = !(selectedDuration === "all" || row.dataset.duration === selectedDuration);
        });
    };

    if (compareToggle && comparePanel) {
        const showLabel = compareToggle.dataset.showLabel || compareToggle.textContent?.trim() || "Solishtirish";
        const hideLabel = compareToggle.dataset.hideLabel || "Yopish";

        compareToggle.addEventListener("click", () => {
            const isHidden = comparePanel.hasAttribute("hidden");
            if (isHidden) {
                comparePanel.removeAttribute("hidden");
                compareToggle.setAttribute("aria-expanded", "true");
                compareToggle.textContent = hideLabel;
                syncCompareRows();
                comparePanel.scrollIntoView({ behavior: "smooth", block: "start" });
            } else {
                comparePanel.setAttribute("hidden", "hidden");
                compareToggle.setAttribute("aria-expanded", "false");
                compareToggle.textContent = showLabel;
            }
        });
    }

    durationButtons.forEach((button) => {
        button.addEventListener("click", () => {
            window.requestAnimationFrame(syncCompareRows);
        });
    });
    syncCompareRows();

    const modalTriggers = Array.from(document.querySelectorAll("[data-plan-open]"));
    const modalMap = new Map(
        Array.from(document.querySelectorAll("[data-plan-modal]"))
            .map((modalElement) => [modalElement.getAttribute("data-plan-modal"), modalElement])
    );

    let activeModal = null;
    let activeTrigger = null;

    const closeModal = (modalElement, returnFocus = true) => {
        if (!modalElement) {
            return;
        }

        modalElement.setAttribute("hidden", "hidden");
        document.body.classList.remove("pricing-modal-open");

        if (activeTrigger) {
            activeTrigger.setAttribute("aria-expanded", "false");
            if (returnFocus) {
                activeTrigger.focus();
            }
        }

        activeModal = null;
        activeTrigger = null;
    };

    const openModal = (modalElement, triggerButton) => {
        if (!modalElement) {
            return;
        }

        if (activeModal && activeModal !== modalElement) {
            closeModal(activeModal, false);
        }

        modalElement.removeAttribute("hidden");
        document.body.classList.add("pricing-modal-open");

        activeModal = modalElement;
        activeTrigger = triggerButton;

        if (activeTrigger) {
            activeTrigger.setAttribute("aria-expanded", "true");
        }

        const dialog = modalElement.querySelector(".pricing-v2-modal-dialog");
        if (dialog) {
            window.requestAnimationFrame(() => {
                dialog.focus();
            });
        }
    };

    modalTriggers.forEach((triggerButton) => {
        const modalId = triggerButton.getAttribute("data-plan-open");
        if (!modalId) {
            return;
        }
        const targetModal = modalMap.get(modalId);
        if (!targetModal) {
            return;
        }

        triggerButton.setAttribute("aria-expanded", "false");
        triggerButton.addEventListener("click", () => {
            openModal(targetModal, triggerButton);
        });
    });

    modalMap.forEach((modalElement) => {
        modalElement.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }
            if (target.closest("[data-plan-close]")) {
                closeModal(modalElement);
            }
        });
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && activeModal) {
            closeModal(activeModal);
        }
    });
});
