document.addEventListener('DOMContentLoaded', () => {
    const translations = {
        uz: {
            hero_badge: 'Telegram integratsiyasi',
            hero_title: 'Markazingizni jadvaldan tizimga olib chiqing va daromad nazoratini kuchaytiring',
            hero_subtitle: "ChaqmoqApp o'quvchi boshqaruvi, davomat, moliya va filial monitoringini yagona boshqaruv panelida birlashtiradi.",
            hero_cta_primary: 'Demo olish',
            hero_cta_secondary: "Narxlarni ko'rish",
            benefit_1: '7 kun bepul sinov',
            benefit_2: 'Tez joriy qilish',
            benefit_3: 'Telegram integratsiyasi',
            insight_title: "Markazlar biz bilan o'smoqda",
            insight_1_value: '+24%',
            insight_1_label: 'Jarayon tezlashuvi',
            insight_2_value: '98%',
            insight_2_label: "To'lov intizomi",
            insight_3_value: '100%',
            insight_3_label: 'Filial monitoringi',
            hello: 'Xush kelibsiz!',
            sign_in: "Kirish uchun ma'lumotlaringizni kiriting",
            credential_label: 'Telefon yoki Gmail',
            credential_placeholder: '+998901234567 yoki ism@gmail.com',
            password_label: 'Parol',
            login_btn: 'Kirish',
            forgot: 'Parolni unutdingizmi?',
            telegram_btn: 'Telegram orqali kirish',
            secure: 'Himoyalangan',
            brand_caption: 'Premium boshqaruv platformasi',
            error_line: "Email yoki parol noto'g'ri."
        },
        ru: {
            hero_badge: 'Интеграция с Telegram',
            hero_title: 'Переведите центр с таблиц на систему и усилите контроль дохода',
            hero_subtitle: 'ChaqmoqApp объединяет управление учениками, посещаемость, финансы и мониторинг филиалов в одной панели.',
            hero_cta_primary: 'Получить демо',
            hero_cta_secondary: 'Смотреть тарифы',
            benefit_1: '7 дней бесплатного теста',
            benefit_2: 'Быстрый запуск',
            benefit_3: 'Интеграция Telegram',
            insight_title: 'Центры растут вместе с нами',
            insight_1_value: '+24%',
            insight_1_label: 'Ускорение процессов',
            insight_2_value: '98%',
            insight_2_label: 'Платежная дисциплина',
            insight_3_value: '100%',
            insight_3_label: 'Мониторинг филиалов',
            hello: 'Добро пожаловать!',
            sign_in: 'Введите данные для входа',
            credential_label: 'Телефон или Gmail',
            credential_placeholder: '+998901234567 или user@gmail.com',
            password_label: 'Пароль',
            login_btn: 'Войти',
            forgot: 'Забыли пароль?',
            telegram_btn: 'Войти через Telegram',
            secure: 'Защищено',
            brand_caption: 'Премиальная платформа управления',
            error_line: 'Неверный email или пароль.'
        },
        en: {
            hero_badge: 'Telegram integration',
            hero_title: 'Move your center from spreadsheets to a system and strengthen revenue control',
            hero_subtitle: 'ChaqmoqApp unifies student management, attendance, finance, and branch monitoring in one panel.',
            hero_cta_primary: 'Get a demo',
            hero_cta_secondary: 'View pricing',
            benefit_1: '7-day free trial',
            benefit_2: 'Fast onboarding',
            benefit_3: 'Telegram integration',
            insight_title: 'Centers grow faster with us',
            insight_1_value: '+24%',
            insight_1_label: 'Process acceleration',
            insight_2_value: '98%',
            insight_2_label: 'Payment discipline',
            insight_3_value: '100%',
            insight_3_label: 'Branch monitoring',
            hello: 'Welcome back!',
            sign_in: 'Enter your details to continue',
            credential_label: 'Phone or Gmail',
            credential_placeholder: '+998901234567 or user@gmail.com',
            password_label: 'Password',
            login_btn: 'Sign in',
            forgot: 'Forgot password?',
            telegram_btn: 'Continue with Telegram',
            secure: 'Secure',
            brand_caption: 'Premium management platform',
            error_line: 'Incorrect email or password.'
        }
    };

    const page = document.getElementById('authPage');
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('usernameInput');
    const passwordInput = document.getElementById('passwordInput');
    const usernameLabel = document.getElementById('txt-username-label');
    const usernameIcon = document.getElementById('usernameIcon');
    const passwordLabel = document.getElementById('txt-password-label');
    const submitBtn = document.getElementById('loginSubmitBtn');
    const eyeIcon = document.getElementById('eyeIcon');
    const eyeOffIcon = document.getElementById('eyeOffIcon');
    const togglePassword = document.getElementById('togglePassword');

    let currentLang = localStorage.getItem('chaqmoq_login_lang') || 'uz';
    if (!translations[currentLang]) {
        currentLang = 'uz';
    }

    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el && typeof value === 'string') {
            el.textContent = value;
        }
    };

    const setFilledState = (inputEl) => {
        if (!inputEl) {
            return;
        }
        const fieldShell = inputEl.closest('.field-shell');
        if (!fieldShell || fieldShell.classList.contains('is-error')) {
            return;
        }
        fieldShell.classList.toggle('is-success', inputEl.value.trim().length > 0);
    };

    const updateLangButtons = () => {
        document.querySelectorAll('[data-lang-btn]').forEach((btn) => {
            const isActive = btn.getAttribute('data-lang-btn') === currentLang;
            btn.classList.toggle('is-active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    };

    const applyLanguage = (lang) => {
        if (!translations[lang]) {
            return;
        }
        currentLang = lang;
        localStorage.setItem('chaqmoq_login_lang', currentLang);

        const t = translations[currentLang];
        setText('txt-hero-badge', t.hero_badge);
        setText('promoTitle', t.hero_title);
        setText('txt-hero-subtitle', t.hero_subtitle);
        setText('txt-hero-cta-primary', t.hero_cta_primary);
        setText('txt-hero-cta-secondary', t.hero_cta_secondary);
        setText('txt-benefit-1', t.benefit_1);
        setText('txt-benefit-2', t.benefit_2);
        setText('txt-benefit-3', t.benefit_3);
        setText('txt-insight-title', t.insight_title);
        setText('txt-insight-1-value', t.insight_1_value);
        setText('txt-insight-1-label', t.insight_1_label);
        setText('txt-insight-2-value', t.insight_2_value);
        setText('txt-insight-2-label', t.insight_2_label);
        setText('txt-insight-3-value', t.insight_3_value);
        setText('txt-insight-3-label', t.insight_3_label);
        setText('txt-hello', t.hello);
        setText('txt-sign-in', t.sign_in);
        setText('txt-login-btn', t.login_btn);
        setText('txt-forgot', t.forgot);
        setText('txt-telegram-btn', t.telegram_btn);
        setText('txt-secure', t.secure);
        setText('txt-brand-caption', t.brand_caption);
        setText('txt-error-line', t.error_line);

        if (usernameLabel) {
            usernameLabel.textContent = t.credential_label;
        }
        if (usernameInput) {
            usernameInput.placeholder = t.credential_placeholder;
            usernameInput.setAttribute('autocomplete', 'username');
            usernameInput.inputMode = 'text';
        }
        if (usernameIcon) {
            usernameIcon.className = 'bi bi-person-lines-fill';
        }
        if (passwordLabel) {
            passwordLabel.textContent = t.password_label;
        }

        updateLangButtons();
    };

    const applyTheme = (themeMode) => {
        if (!page) {
            return;
        }
        const isNight = themeMode === 'night';
        page.classList.toggle('theme-night', isNight);
        localStorage.setItem('chaqmoq_login_theme', isNight ? 'night' : 'light');
    };

    const initTheme = () => {
        // Login should open in brand light mode by default.
        applyTheme('light');
    };

    document.querySelectorAll('[data-lang-btn]').forEach((btn) => {
        btn.addEventListener('click', () => {
            applyLanguage(btn.getAttribute('data-lang-btn'));
        });
    });

    if (togglePassword && passwordInput && eyeIcon && eyeOffIcon) {
        togglePassword.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            eyeIcon.style.display = isPassword ? 'none' : 'inline-flex';
            eyeOffIcon.style.display = isPassword ? 'inline-flex' : 'none';
            togglePassword.setAttribute('aria-label', isPassword ? 'Parolni yashirish' : "Parolni ko'rsatish");
        });
    }

    if (usernameInput) {
        usernameInput.addEventListener('blur', () => setFilledState(usernameInput));
        usernameInput.addEventListener('input', () => {
            const field = usernameInput.closest('.field-shell');
            if (field && field.classList.contains('is-error')) {
                field.classList.remove('is-error');
            }
            setFilledState(usernameInput);
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener('blur', () => setFilledState(passwordInput));
        passwordInput.addEventListener('input', () => {
            const field = passwordInput.closest('.field-shell');
            if (field && field.classList.contains('is-error')) {
                field.classList.remove('is-error');
            }
            setFilledState(passwordInput);
        });
    }

    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', (event) => {
            if (!loginForm.checkValidity()) {
                event.preventDefault();
                loginForm.reportValidity();
                return;
            }
            submitBtn.disabled = true;
            submitBtn.classList.add('is-loading');
        });
    }

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const isNight = page ? page.classList.contains('theme-night') : false;
            applyTheme(isNight ? 'light' : 'night');
        });
    }

    initTheme();
    applyLanguage(currentLang);
    setFilledState(usernameInput);
    setFilledState(passwordInput);
});
