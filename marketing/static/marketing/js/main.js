document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector(".site-header");
    const mobileButton = document.querySelector("[data-mobile-toggle]");
    const mobileMenu = document.querySelector("[data-mobile-menu]");

    const syncHeaderState = () => {
        if (!header) {
            return;
        }
        header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    syncHeaderState();
    window.addEventListener("scroll", syncHeaderState, { passive: true });

    if (mobileButton && mobileMenu) {
        const closeMenu = () => {
            mobileMenu.classList.remove("is-open");
            mobileButton.setAttribute("aria-expanded", "false");
        };

        mobileButton.addEventListener("click", () => {
            const isOpen = mobileMenu.classList.toggle("is-open");
            mobileButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof Node)) {
                return;
            }
            if (!mobileMenu.classList.contains("is-open")) {
                return;
            }
            if (mobileMenu.contains(target) || mobileButton.contains(target)) {
                return;
            }
            closeMenu();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeMenu();
            }
        });

        mobileMenu.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", () => {
                closeMenu();
            });
        });
    }

    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.addEventListener("click", (event) => {
            const targetId = link.getAttribute("href");
            if (!targetId || targetId === "#") {
                return;
            }
            const target = document.querySelector(targetId);
            if (!target) {
                return;
            }
            event.preventDefault();
            target.scrollIntoView({ behavior: "smooth", block: "start" });
            if (mobileMenu) {
                mobileMenu.classList.remove("is-open");
            }
            if (mobileButton) {
                mobileButton.setAttribute("aria-expanded", "false");
            }
        });
    });

    document.querySelectorAll("[data-accordion]").forEach((accordion) => {
        const items = accordion.querySelectorAll(".faq-item");
        const setHeight = (item) => {
            const content = item.querySelector("[data-accordion-content]");
            if (!content) {
                return;
            }
            content.style.maxHeight = item.classList.contains("open") ? `${content.scrollHeight}px` : "0px";
        };

        items.forEach((item) => {
            setHeight(item);
            const btn = item.querySelector("[data-accordion-btn]");
            if (!btn) {
                return;
            }
            btn.addEventListener("click", () => {
                const isOpen = item.classList.contains("open");
                items.forEach((entry) => {
                    if (entry !== item) {
                        entry.classList.remove("open");
                        setHeight(entry);
                    }
                });
                item.classList.toggle("open", !isOpen);
                setHeight(item);
            });
        });
    });

    const testimonialList = document.querySelector("[data-testimonial-list]");
    if (testimonialList) {
        const items = testimonialList.querySelectorAll("[data-testimonial-item]");
        const quoteNode = document.querySelector("[data-testimonial-text]");
        const nameNode = document.querySelector("[data-testimonial-name]");
        const metaNode = document.querySelector("[data-testimonial-meta]");
        const starsNode = document.querySelector("[data-testimonial-stars]");
        const avatarNode = document.querySelector("[data-testimonial-avatar]");
        const avatarFallbackNode = document.querySelector("[data-testimonial-avatar-fallback]");

        const renderStars = (ratingValue) => {
            if (!starsNode) {
                return;
            }
            const safeRating = Math.max(1, Math.min(5, Number.parseInt(ratingValue || "5", 10)));
            starsNode.innerHTML = "";
            for (let index = 1; index <= 5; index += 1) {
                const icon = document.createElement("i");
                icon.className = index <= safeRating ? "bi bi-star-fill" : "bi bi-star";
                starsNode.appendChild(icon);
            }
            starsNode.setAttribute("aria-label", `${safeRating} / 5`);
        };

        const applyItem = (item) => {
            if (!item) {
                return;
            }

            items.forEach((entry) => entry.classList.remove("is-active"));
            item.classList.add("is-active");

            const name = item.getAttribute("data-name") || "";
            const center = item.getAttribute("data-center") || "";
            const role = item.getAttribute("data-role") || "";
            const text = item.getAttribute("data-text") || "";
            const avatar = item.getAttribute("data-avatar") || "";
            const rating = item.getAttribute("data-rating") || "5";

            if (quoteNode) {
                quoteNode.textContent = `"${text}"`;
            }
            if (nameNode) {
                nameNode.textContent = name;
            }
            if (metaNode) {
                metaNode.textContent = role ? `${center} • ${role}` : center;
            }
            renderStars(rating);

            if (avatarNode) {
                if (avatar) {
                    avatarNode.src = avatar;
                    avatarNode.alt = name;
                    avatarNode.hidden = false;
                    if (avatarFallbackNode) {
                        avatarFallbackNode.hidden = true;
                    }
                } else {
                    avatarNode.src = "";
                    avatarNode.alt = "";
                    avatarNode.hidden = true;
                    if (avatarFallbackNode) {
                        avatarFallbackNode.hidden = false;
                        avatarFallbackNode.textContent = name ? name.charAt(0).toUpperCase() : "C";
                    }
                }
            }
        };

        items.forEach((item) => {
            item.addEventListener("click", () => {
                applyItem(item);
            });
        });

        const initial = testimonialList.querySelector(".is-active") || items[0];
        applyItem(initial);
    }

    const durationButtons = document.querySelectorAll("[data-duration-btn]");
    const pricingCards = document.querySelectorAll("[data-duration]");

    if (durationButtons.length && pricingCards.length) {
        const showByDuration = (value) => {
            pricingCards.forEach((card) => {
                const isVisible = card.dataset.duration === value || value === "all";
                card.hidden = !isVisible;
                if (isVisible) {
                    card.removeAttribute("aria-hidden");
                } else {
                    card.setAttribute("aria-hidden", "true");
                }
            });
        };

        durationButtons.forEach((btn, index) => {
            if (index === 0) {
                showByDuration(btn.dataset.durationBtn || "all");
            }
            btn.addEventListener("click", () => {
                durationButtons.forEach((entry) => entry.classList.remove("active"));
                btn.classList.add("active");
                showByDuration(btn.dataset.durationBtn || "all");
            });
        });
    }

    const revealItems = document.querySelectorAll(".reveal-up");
    if ("IntersectionObserver" in window && revealItems.length) {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12 }
        );
        revealItems.forEach((element) => observer.observe(element));
    } else {
        revealItems.forEach((element) => element.classList.add("visible"));
    }

    const demoForm = document.querySelector("[data-demo-form]");
    if (demoForm) {
        demoForm.addEventListener("submit", () => {
            const submitBtn = demoForm.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = demoForm.dataset.submittingText || submitBtn.textContent;
            }
        });
    }
});
