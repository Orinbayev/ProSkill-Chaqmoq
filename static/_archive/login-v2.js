document.addEventListener('DOMContentLoaded', () => {
    const translations = {
        uz: {
            hero_badge: 'Telegram integratsiyasi',
            hero_title: 'Markazingizni jadvaldan tizimga olib chiqing va daromad nazoratini kuchaytiring',
            hero_subtitle: 'ChaqmoqApp o‘quvchi boshqaruvi, davomat, moliya va filial monitoringini yagona boshqaruv panelida birlashtiradi.',
            hero_cta_primary: 'Platformaga kirish',
            hero_cta_secondary: 'Narxlarni ko‘rish',
            benefit_1: '7 kun bepul sinov',
            benefit_2: 'Tez joriy qilish',
            benefit_3: 'Telegram integratsiyasi',
            stat_1_label: 'Jarayon tezlashuvi',
            stat_2_label: 'To‘lov intizomi',
            chip_1: 'Davomat nazorati',
            chip_2: 'Filial monitoringi',
            chip_3: 'Avtomatik eslatmalar',
            hello: 'Xush kelibsiz!',
            sign_in: "Kirish uchun ma'lumotlaringizni kiriting",
            tab_email: 'Email orqali',
            tab_phone: 'Telefon orqali',
            email_label: 'Email manzili',
            phone_label: 'Telefon raqami',
            password_label: 'Parol',
            email_placeholder: 'example@mail.com',
            phone_placeholder: '+998901234567',
            login_btn: 'Kirish',
            forgot: 'Parolni unutdingizmi?',
            telegram_btn: 'Telegram orqali kirish',
            secure: 'Himoyalangan',
            brand_caption: 'Premium boshqaruv platformasi',
            error_line: 'Email yoki parol noto‘g‘ri.'
        },
        ru: {
            hero_badge: 'Интеграция с Telegram',
            hero_title: 'Переведите центр с таблиц на систему и усилите контроль дохода',
            hero_subtitle: 'ChaqmoqApp объединяет управление учениками, посещаемость, финансы и мониторинг филиалов в одной панели.',
            hero_cta_primary: 'Войти в платформу',
            hero_cta_secondary: 'Смотреть тарифы',
            benefit_1: '7 дней бесплатного теста',
            benefit_2: 'Быстрый запуск',
            benefit_3: 'Интеграция Telegram',
            stat_1_label: 'Ускорение процессов',
            stat_2_label: 'Платежная дисциплина',
            chip_1: 'Контроль посещаемости',
            chip_2: 'Мониторинг филиалов',
            chip_3: 'Авто напоминания',
            hello: 'Добро пожаловать!',
            sign_in: 'Введите данные для входа',
            tab_email: 'Через Email',
            tab_phone: 'Через телефон',
            email_label: 'Email адрес',
            phone_label: 'Номер телефона',
            password_label: 'Пароль',
            email_placeholder: 'example@mail.com',
            phone_placeholder: '+998901234567',
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
            hero_cta_primary: 'Enter platform',
            hero_cta_secondary: 'View pricing',
            benefit_1: '7-day free trial',
            benefit_2: 'Fast onboarding',
            benefit_3: 'Telegram integration',
            stat_1_label: 'Process acceleration',
            stat_2_label: 'Payment discipline',
            chip_1: 'Attendance control',
            chip_2: 'Branch monitoring',
            chip_3: 'Automated reminders',
            hello: 'Welcome back!',
            sign_in: 'Enter your details to continue',
            tab_email: 'With Email',
            tab_phone: 'With Phone',
            email_label: 'Email address',
            phone_label: 'Phone number',
            password_label: 'Password',
            email_placeholder: 'example@mail.com',
            phone_placeholder: '+998901234567',
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
    const tabEmail = document.getElementById('tab-email');
    const tabPhone = document.getElementById('tab-phone');
    const submitBtn = document.getElementById('loginSubmitBtn');
    const eyeIcon = document.getElementById('eyeIcon');
    const eyeOffIcon = document.getElementById('eyeOffIcon');
    const togglePassword = document.getElementById('togglePassword');

    let currentLang = localStorage.getItem('chaqmoq_login_lang') || 'uz';
    let currentTab = localStorage.getItem('chaqmoq_login_tab') || 'email';

    if (!translations[currentLang]) {
        currentLang = 'uz';
    }
    if (!['email', 'phone'].includes(currentTab)) {
        currentTab = 'email';
    }

    const textMap = {
        txtHeroBadge: 'txt-hero-badge',
        txtHeroSubtitle: 'txt-hero-subtitle',
        txtHeroCtaPrimary: 'txt-hero-cta-primary',
        txtHeroCtaSecondary: 'txt-hero-cta-secondary',
        txtBenefit1: 'txt-benefit-1',
        txtBenefit2: 'txt-benefit-2',
        txtBenefit3: 'txt-benefit-3',
        txtStat1Label: 'txt-stat-1-label',
        txtStat2Label: 'txt-stat-2-label',
        txtChip1: 'txt-chip-1',
        txtChip2: 'txt-chip-2',
        txtChip3: 'txt-chip-3',
        txtHello: 'txt-hello',
        txtSignIn: 'txt-sign-in',
        txtTabEmail: 'txt-tab-email',
        txtTabPhone: 'txt-tab-phone',
        txtLoginBtn: 'txt-login-btn',
        txtForgot: 'txt-forgot',
        txtTelegramBtn: 'txt-telegram-btn',
        txtSecure: 'txt-secure',
        txtBrandCaption: 'txt-brand-caption',
        txtErrorLine: 'txt-error-line'
    };

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

    const applyTab = (tab) => {
        currentTab = tab === 'phone' ? 'phone' : 'email';
        localStorage.setItem('chaqmoq_login_tab', currentTab);

        const t = translations[currentLang];
        const emailActive = currentTab === 'email';

        if (tabEmail) {
            tabEmail.classList.toggle('is-active', emailActive);
            tabEmail.setAttribute('aria-selected', emailActive ? 'true' : 'false');
        }
        if (tabPhone) {
            tabPhone.classList.toggle('is-active', !emailActive);
            tabPhone.setAttribute('aria-selected', !emailActive ? 'true' : 'false');
        }

        if (usernameLabel) {
            usernameLabel.textContent = emailActive ? t.email_label : t.phone_label;
        }
        if (usernameInput) {
            usernameInput.placeholder = emailActive ? t.email_placeholder : t.phone_placeholder;
            usernameInput.inputMode = emailActive ? 'email' : 'tel';
            usernameInput.setAttribute('autocomplete', emailActive ? 'username' : 'tel');
        }
        if (usernameIcon) {
            usernameIcon.className = emailActive ? 'bi bi-envelope' : 'bi bi-telephone';
        }
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
        setText(textMap.txtHeroBadge, t.hero_badge);
        setText('promoTitle', t.hero_title);
        setText(textMap.txtHeroSubtitle, t.hero_subtitle);
        setText(textMap.txtHeroCtaPrimary, t.hero_cta_primary);
        setText(textMap.txtHeroCtaSecondary, t.hero_cta_secondary);
        setText(textMap.txtBenefit1, t.benefit_1);
        setText(textMap.txtBenefit2, t.benefit_2);
        setText(textMap.txtBenefit3, t.benefit_3);
        setText(textMap.txtStat1Label, t.stat_1_label);
        setText(textMap.txtStat2Label, t.stat_2_label);
        setText(textMap.txtChip1, t.chip_1);
        setText(textMap.txtChip2, t.chip_2);
        setText(textMap.txtChip3, t.chip_3);
        setText(textMap.txtHello, t.hello);
        setText(textMap.txtSignIn, t.sign_in);
        setText(textMap.txtTabEmail, t.tab_email);
        setText(textMap.txtTabPhone, t.tab_phone);
        setText(textMap.txtLoginBtn, t.login_btn);
        setText(textMap.txtForgot, t.forgot);
        setText(textMap.txtTelegramBtn, t.telegram_btn);
        setText(textMap.txtSecure, t.secure);
        setText(textMap.txtBrandCaption, t.brand_caption);
        setText(textMap.txtErrorLine, t.error_line);

        if (passwordLabel) {
            passwordLabel.textContent = t.password_label;
        }

        updateLangButtons();
        applyTab(currentTab);
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
        const savedTheme = localStorage.getItem('chaqmoq_login_theme') || 'light';
        applyTheme(savedTheme);
    };

    document.querySelectorAll('[data-lang-btn]').forEach((btn) => {
        btn.addEventListener('click', () => {
            applyLanguage(btn.getAttribute('data-lang-btn'));
        });
    });

    if (tabEmail) {
        tabEmail.addEventListener('click', () => applyTab('email'));
    }
    if (tabPhone) {
        tabPhone.addEventListener('click', () => applyTab('phone'));
    }

    if (togglePassword && passwordInput && eyeIcon && eyeOffIcon) {
        togglePassword.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            eyeIcon.style.display = isPassword ? 'none' : 'inline-flex';
            eyeOffIcon.style.display = isPassword ? 'inline-flex' : 'none';
            togglePassword.setAttribute('aria-label', isPassword ? 'Parolni yashirish' : 'Parolni ko‘rsatish');
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
    applyTab(currentTab);
    setFilledState(usernameInput);
    setFilledState(passwordInput);
});
