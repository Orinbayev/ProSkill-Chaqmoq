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

    const lpDashboard = document.querySelector("[data-lp-dashboard-preview]");
    if (lpDashboard && window.matchMedia("(min-width: 981px)").matches) {
        const lpFormatNumber = (value) => Math.round(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        const lpFormatValue = (value, format) => {
            if (format === "money") {
                return `${lpFormatNumber(value)} so'm`;
            }
            if (format === "percent") {
                return `${Math.round(value)}%`;
            }
            return `${Math.round(value)} ta`;
        };

        const lpAnimateCounters = () => {
            if (lpDashboard.dataset.lpCountersStarted === "1") {
                return;
            }
            lpDashboard.dataset.lpCountersStarted = "1";

            lpDashboard.querySelectorAll("[data-lp-counter]").forEach((node) => {
                const target = Number(node.getAttribute("data-lp-counter") || 0);
                const format = node.getAttribute("data-lp-format") || "count";
                const duration = 1500;
                let startedAt = 0;

                const tick = (timestamp) => {
                    if (!startedAt) {
                        startedAt = timestamp;
                    }
                    const progress = Math.min((timestamp - startedAt) / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    node.textContent = lpFormatValue(target * eased, format);
                    if (progress < 1) {
                        window.requestAnimationFrame(tick);
                    }
                };

                window.requestAnimationFrame(tick);
            });
        };

        const lpAnimateRows = () => {
            if (lpDashboard.dataset.lpRowsStarted === "1") {
                return;
            }
            lpDashboard.dataset.lpRowsStarted = "1";

            lpDashboard.querySelectorAll("[data-lp-stagger-row]").forEach((row, index) => {
                row.style.animationDelay = `${index * 50}ms`;
                row.classList.add("is-visible");
            });
        };

        const lpRenderChart = (attempt = 0) => {
            if (lpDashboard.dataset.lpChartReady === "1") {
                return;
            }

            const chartNode = document.getElementById("lp-revenue-chart");
            if (!chartNode) {
                return;
            }

            if (typeof window.ApexCharts === "undefined") {
                if (attempt < 20) {
                    window.setTimeout(() => lpRenderChart(attempt + 1), 150);
                }
                return;
            }

            lpDashboard.dataset.lpChartReady = "1";
            const chart = new window.ApexCharts(chartNode, {
                chart: {
                    type: "area",
                    height: 262,
                    toolbar: { show: false },
                    zoom: { enabled: false },
                    background: "transparent",
                    fontFamily: "inherit",
                    animations: {
                        enabled: true,
                        easing: "easeinout",
                        speed: 950,
                        animateGradually: {
                            enabled: true,
                            delay: 500,
                        },
                        dynamicAnimation: {
                            enabled: true,
                            speed: 450,
                        },
                    },
                },
                series: [
                    {
                        name: "Oylik tushum",
                        data: [8200000, 11500000, 9800000, 14200000, 16100000, 18400000],
                    },
                ],
                colors: ["#22c55e"],
                stroke: {
                    curve: "smooth",
                    width: 3.5,
                    colors: ["#60a5fa"],
                },
                fill: {
                    type: "gradient",
                    gradient: {
                        shadeIntensity: 1,
                        opacityFrom: 0.42,
                        opacityTo: 0.03,
                        stops: [0, 65, 100],
                        colorStops: [
                            [
                                { offset: 0, color: "#3b82f6", opacity: 0.42 },
                                { offset: 60, color: "#22c55e", opacity: 0.16 },
                                { offset: 100, color: "#22c55e", opacity: 0.02 },
                            ],
                        ],
                    },
                },
                dataLabels: { enabled: false },
                markers: {
                    size: 4,
                    strokeWidth: 2,
                    colors: ["#a7f3d0"],
                    strokeColors: "#ffffff",
                    hover: { size: 6 },
                },
                grid: {
                    borderColor: "rgba(148,163,184,0.22)",
                    strokeDashArray: 4,
                    padding: {
                        left: 8,
                        right: 10,
                        top: 4,
                        bottom: 0,
                    },
                },
                legend: { show: false },
                tooltip: {
                    theme: "light",
                    y: {
                        formatter(value) {
                            return `${lpFormatNumber(value)} so'm`;
                        },
                    },
                },
                xaxis: {
                    categories: ["Noy", "Dek", "Yan", "Fev", "Mar", "Apr"],
                    axisBorder: { show: false },
                    axisTicks: { show: false },
                    labels: {
                        style: {
                            colors: "#64748b",
                            fontSize: "12px",
                        },
                    },
                },
                yaxis: {
                    tickAmount: 4,
                    labels: {
                        style: {
                            colors: "#64748b",
                            fontSize: "12px",
                        },
                        formatter(value) {
                            const million = value / 1000000;
                            return `${Math.round(million)} mln`;
                        },
                    },
                },
            });
            chart.render();
        };

        const lpStartDashboard = () => {
            lpAnimateCounters();
            lpAnimateRows();
            lpRenderChart();
        };

        if ("IntersectionObserver" in window) {
            const previewObserver = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (entry.isIntersecting) {
                            lpStartDashboard();
                            previewObserver.unobserve(entry.target);
                        }
                    });
                },
                { threshold: 0.25 }
            );
            previewObserver.observe(lpDashboard);
        } else {
            lpStartDashboard();
        }

        if (window.matchMedia("(pointer: fine)").matches) {
            let tiltFrame = 0;

            const updateTilt = (clientX, clientY) => {
                const rect = lpDashboard.getBoundingClientRect();
                const x = (clientX - rect.left) / rect.width;
                const y = (clientY - rect.top) / rect.height;
                const rotateY = (x - 0.5) * 10;
                const rotateX = (0.5 - y) * 8;

                lpDashboard.style.setProperty("--lp-tilt-x", `${rotateX.toFixed(2)}deg`);
                lpDashboard.style.setProperty("--lp-tilt-y", `${rotateY.toFixed(2)}deg`);
                lpDashboard.style.setProperty("--lp-glow-x", `${(x * 100).toFixed(1)}%`);
                lpDashboard.style.setProperty("--lp-glow-y", `${(y * 100).toFixed(1)}%`);
            };

            lpDashboard.addEventListener("pointermove", (event) => {
                if (tiltFrame) {
                    window.cancelAnimationFrame(tiltFrame);
                }
                tiltFrame = window.requestAnimationFrame(() => {
                    updateTilt(event.clientX, event.clientY);
                });
            });

            lpDashboard.addEventListener("pointerleave", () => {
                if (tiltFrame) {
                    window.cancelAnimationFrame(tiltFrame);
                }
                lpDashboard.style.setProperty("--lp-tilt-x", "0deg");
                lpDashboard.style.setProperty("--lp-tilt-y", "0deg");
                lpDashboard.style.setProperty("--lp-glow-x", "70%");
                lpDashboard.style.setProperty("--lp-glow-y", "18%");
            });
        }
    }
});
