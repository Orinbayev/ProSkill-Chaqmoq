from collections import OrderedDict
import re

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone, translation

from .forms import DemoLeadForm
from .models import (
    FAQ,
    FeatureBlock,
    PartnerLogo,
    PricingPlan,
    ScreenshotSection,
    SiteSetting,
    StaticPage,
    SupportCard,
    Testimonial,
    Vacancy,
)
from .services import notify_telegram_new_lead


SUPPORTED_LANGUAGES = ("uz", "ru", "en")
LANGUAGE_LABELS = {
    "uz": "O'zbek",
    "ru": "Русский",
    "en": "English",
}


MARKETING_UI = {
    "uz": {
        "lang_name": "O'zbek",
        "seo_default_title": "ChaqmoqApp | O'quv markazlar uchun premium boshqaruv platformasi",
        "seo_default_description": "O'quvchilar, guruhlar, davomat, to'lov va qarzdorlikni bitta bulutli tizimda boshqaring.",
        "menu_pricing": "Narxlar",
        "menu_features": "Imkoniyatlar",
        "menu_support": "Qo'llab-quvvatlash",
        "menu_vacancies": "Vakansiyalar",
        "menu_demo": "Demo olish",
        "menu_login": "Platformaga kirish",
        "menu_aria_label": "Asosiy menyu",
        "language_switcher_aria": "Til almashtirgich",
        "menu_toggle_aria": "Menyuni ochish yoki yopish",
        "messages_label": "Xabarlar",
        "month_label": "oy",
        "money_label": "so'm",
        "hero_eyebrow": "Ta'lim markazlari uchun bulutli SaaS",
        "hero_title": "Markazingizni jadvaldan tizimga olib chiqing va daromad nazoratini kuchaytiring",
        "hero_subtitle": "ChaqmoqApp o'quvchi boshqaruvi, davomat, moliya va filial monitoringini yagona boshqaruv paneliga birlashtiradi.",
        "hero_benefit_1": "7 kun bepul sinov",
        "hero_benefit_2": "Tez joriy qilish",
        "hero_benefit_3": "Telegram integratsiyasi",
        "hero_metric_1": "Jarayon tezlashuvi",
        "hero_metric_2": "To'lov intizomi",
        "hero_metric_3": "Bulutli kirish",
        "partners_eyebrow": "Ishonch bloki",
        "partners_title": "Biz bilan ishlayotgan markazlar",
        "partners_empty": "Hamkor markazlar logolari hozircha qo'shilmagan.",
        "features_eyebrow": "Nega ChaqmoqApp?",
        "features_title": "Markaz egasi va administrator uchun eng zarur funksiyalar",
        "feature_empty_title": "CRM + Davomat",
        "feature_empty_text": "Kerakli marketing bloklarini superadmin paneldan to'ldiring.",
        "before_after_eyebrow": "Platforma qanday yordam beradi?",
        "before_after_title": "Oldingi tartibsizlik o'rniga real vaqtdagi nazorat",
        "before_title": "Oldin",
        "after_title": "ChaqmoqApp bilan",
        "before_1": "To'lov va davomat turli jadvallarda yuritiladi",
        "before_2": "Qarzdorlar nazorati qo'lda tekshiriladi",
        "before_3": "Filiallar bo'yicha umumiy hisobot kechikadi",
        "before_4": "Rahbar qaror uchun toza ma'lumot ololmaydi",
        "after_1": "O'quvchi, guruh, davomat va moliya bitta tizimda",
        "after_2": "Qarzdorlik bo'yicha aniq ro'yxat va ogohlantirishlar",
        "after_3": "Filial kesimidagi statistika real vaqt rejimida",
        "after_4": "Direktor uchun tezkor analitika va nazorat",
        "screens_eyebrow": "Platforma ko'rinishi",
        "screens_title": "Boshqaruv panelining asosiy oynalari",
        "screens_empty": "Ekran rasmlarini admin paneldan qo'shing.",
        "pricing_eyebrow": "Tariflar",
        "pricing_title": "Markazingiz hajmiga mos reja tanlang",
        "pricing_page_desc": "3, 6, 9 va 12 oy kesimida qulay to'lov rejimlari. Tariflar admin panel orqali yangilanadi.",
        "pricing_cta": "To'liq narxlarni ko'rish",
        "pricing_pay": "To'lov qilish",
        "pricing_demo": "Demo olish",
        "pricing_empty": "Faol tariflar topilmadi.",
        "pricing_filter_all": "Barcha tariflar",
        "pricing_benefit_1_title": "Tezkor o'rnatish",
        "pricing_benefit_1_desc": "Tizimni qisqa vaqt ichida ishga tushiring.",
        "pricing_benefit_2_title": "Xavfsizlik",
        "pricing_benefit_2_desc": "Ma'lumotlaringiz himoyalangan va nazorat ostida bo'ladi.",
        "pricing_benefit_3_title": "Qo'llab-quvvatlash",
        "pricing_benefit_3_desc": "Jamoangiz uchun tezkor texnik yordam mavjud.",
        "pricing_benefit_4_title": "Bulutli tizim",
        "pricing_benefit_4_desc": "Istalgan joydan platformaga ulaning.",
        "plan_feature_fallback_1": "Asosiy boshqaruv modullari",
        "plan_feature_fallback_2": "Dashboard va statistika",
        "integrations_eyebrow": "Integratsiyalar",
        "integrations_title": "Ish jarayoniga mos ulanadigan xizmatlar",
        "integrations_empty": "Integratsiya bloklarini admin paneldan qo'shing.",
        "testimonials_eyebrow": "Mijozlar fikri",
        "testimonials_title": "Markaz egalari biz haqimizda nima deydi",
        "testimonials_empty": "Sharhlar admin paneldan boshqariladi.",
        "faq_eyebrow": "Savol-javob",
        "faq_title": "Ko'p so'raladigan savollar",
        "faq_empty_q": "Joriy qilish qancha vaqt oladi?",
        "faq_empty_a": "Odatda 1-2 ish kunida markazingiz ishga tushadi.",
        "final_eyebrow": "Boshlash vaqti keldi",
        "final_title": "Bugun demo oling va 7 kun bepul sinab ko'ring",
        "final_text": "Boshqaruvdagi yo'qotishlarni kamaytiring, jamoa samaradorligini oshiring.",
        "final_demo": "Demo olish",
        "final_pricing": "Narxlar",
        "metrics_title": "ChaqmoqApp foydalanuvchilari raqamlarda",
        "metric_centers": "O'quv markazlari",
        "metric_branches": "Filiallar",
        "metric_groups": "Guruhlar",
        "metric_students": "O'quvchilar",
        "benefits_title": "Biz bilan nimalarga ega bo'lasiz?",
        "benefits_desc": "Markaz egasi uchun nazorat, jamoa uchun tezkor ish oqimi va o'quvchilar uchun barqaror xizmat sifati.",
        "testimonial_list_title": "Mijozlarimiz fikrlari",
        "support_page_title": "ChaqmoqApp bo'yicha tezkor yordam",
        "support_page_desc": "Video yo'riqnoma, hujjatlar va support kanallar orqali jamoangizni tez o'rgating.",
        "support_trust_text": "Support jamoamiz ish kunlari 09:00-22:00 oralig'ida javob beradi.",
        "support_metrics_aria": "Support statistikasi",
        "support_metric_value_1": "< 15 daq",
        "support_metric_value_2": "1 kun",
        "support_metric_value_3": "300+",
        "support_metric_1": "Javob vaqti",
        "support_metric_2": "Onboarding boshlanishi",
        "support_metric_3": "Faol markazlar",
        "support_cards_title": "Yordam markazi bo'limlari",
        "support_cards_desc": "Jamoangiz uchun kerakli yo'riqnoma va yordam kanallarini bir joyda oching.",
        "support_empty": "Yordam kartalari hali qo'shilmagan.",
        "support_empty_title": "Yordam kartalari tayyor emas",
        "support_empty_text": "Support bo'limini to'ldirish uchun kartalarni superadmin paneldan qo'shing.",
        "support_empty_hint": "Superadmin: Marketing -> Yordam kartalari",
        "support_steps_title": "Tez ishga tushirish",
        "support_steps_desc": "Yangi markaz uchun 3 qadamli onboarding bilan xodimlarni tez moslashtiring.",
        "support_step_1_title": "1-qadam: Tizimga kirish",
        "support_step_1_text": "Administrator va menejerlarga rol bo'yicha kirish huquqlarini bering.",
        "support_step_2_title": "2-qadam: Ma'lumotlarni yuklash",
        "support_step_2_text": "O'quvchi, guruh, to'lov va davomat ma'lumotlarini bir marta import qiling.",
        "support_step_3_title": "3-qadam: Nazoratni yoqing",
        "support_step_3_text": "Telegram bildirishnomalari va qarzdorlik monitoringini ishga tushiring.",
        "support_faq_title": "Ko'p beriladigan savollar",
        "support_cta_title": "Yordam kerakmi?",
        "support_cta_text": "Mutaxassisimiz markazingizga mos joriy etish rejasi bilan bog'lanadi.",
        "support_cta_primary": "Support bilan bog'lanish",
        "support_cta_secondary": "Demo olish",
        "vacancy_page_title": "Biz bilan birga o'sing",
        "vacancy_page_desc": "ChaqmoqApp jamoasiga qo'shiling va ta'lim texnologiyalarini yangi bosqichga olib chiqing.",
        "vacancy_requirements": "Talablar",
        "vacancy_responsibilities": "Vazifalar",
        "vacancy_empty": "Hozircha faol vakansiyalar mavjud emas.",
        "vacancy_apply": "Ariza topshirish",
        "legal_eyebrow": "Huquqiy ma'lumot",
        "privacy_default_title": "Maxfiylik siyosati",
        "terms_default_title": "Foydalanish shartlari",
        "demo_page_title": "Markazingiz uchun individual demo so'rang",
        "demo_page_desc": "Forma orqali so'rov yuboring, mutaxassisimiz sizga platformani jonli ko'rsatib beradi.",
        "demo_benefits_title": "Demo davomida nimalarni ko'rasiz?",
        "demo_benefit_1": "O'quvchi bazasini boshqarish va segmentlash",
        "demo_benefit_2": "Davomat, to'lov va qarzdorlik nazorati",
        "demo_benefit_3": "Telegram bildirishnomalar ssenariysi",
        "demo_benefit_4": "Filiallar bo'yicha real vaqt statistikasi",
        "demo_benefit_5": "Sotuv va administrator ish jarayonini tezlashtirish",
        "demo_form_title": "Demo so'rovi",
        "demo_submit": "So'rov yuborish",
        "demo_submitting": "Yuborilmoqda...",
        "demo_success": "So'rovingiz qabul qilindi. Mutaxassisimiz siz bilan tez orada bog'lanadi.",
        "demo_error": "Formada xatolik bor. Iltimos, maydonlarni tekshiring.",
        "footer_tagline": "O'quv markazlar uchun premium, tezkor va sotuvga yo'naltirilgan boshqaruv platformasi.",
        "footer_pages": "Sahifalar",
        "footer_legal": "Huquqiy",
        "footer_contact": "Bog'lanish",
        "footer_social": "Ijtimoiy tarmoqlar",
        "footer_cta_title": "Markazingizni raqamlashtirishni bugunoq boshlang",
        "footer_cta_text": "Demo so'rovi yuboring, jamoamiz 24 soat ichida siz bilan bog'lanadi.",
        "copyright": "Barcha huquqlar himoyalangan.",
    },
    "ru": {
        "lang_name": "Русский",
        "seo_default_title": "ChaqmoqApp | Премиальная платформа управления учебным центром",
        "seo_default_description": "Управляйте учениками, группами, посещаемостью, оплатами и задолженностью в одной облачной системе.",
        "menu_pricing": "Тарифы",
        "menu_features": "Возможности",
        "menu_support": "Поддержка",
        "menu_vacancies": "Вакансии",
        "menu_demo": "Получить демо",
        "menu_login": "Войти в платформу",
        "menu_aria_label": "Основное меню",
        "language_switcher_aria": "Переключатель языка",
        "menu_toggle_aria": "Открыть или закрыть меню",
        "messages_label": "Сообщения",
        "month_label": "мес",
        "money_label": "сум",
        "hero_eyebrow": "Облачный SaaS для учебных центров",
        "hero_title": "Переведите управление центром на систему и усилите контроль дохода",
        "hero_subtitle": "ChaqmoqApp объединяет учеников, посещаемость, финансы и филиалы в одной управленческой панели.",
        "hero_benefit_1": "7 дней бесплатного теста",
        "hero_benefit_2": "Быстрое внедрение",
        "hero_benefit_3": "Интеграция с Telegram",
        "hero_metric_1": "Ускорение процессов",
        "hero_metric_2": "Платежная дисциплина",
        "hero_metric_3": "Облачный доступ",
        "partners_eyebrow": "Доверие",
        "partners_title": "Центры, которые уже работают с нами",
        "partners_empty": "Логотипы партнёрских центров пока не добавлены.",
        "features_eyebrow": "Почему ChaqmoqApp?",
        "features_title": "Ключевые функции для владельца и администратора",
        "feature_empty_title": "CRM и посещаемость",
        "feature_empty_text": "Заполните маркетинговые блоки через superadmin.",
        "before_after_eyebrow": "Как платформа помогает",
        "before_after_title": "Вместо хаоса в таблицах — контроль в реальном времени",
        "before_title": "До",
        "after_title": "С ChaqmoqApp",
        "before_1": "Оплаты и посещаемость ведутся в разных файлах",
        "before_2": "Контроль должников делается вручную",
        "before_3": "Сводка по филиалам запаздывает",
        "before_4": "Руководитель не видит чистую аналитику",
        "after_1": "Ученики, группы, посещаемость и финансы в одной системе",
        "after_2": "Список должников и напоминания автоматически",
        "after_3": "Статистика по филиалам в реальном времени",
        "after_4": "Быстрые управленческие решения на основе данных",
        "screens_eyebrow": "Интерфейс",
        "screens_title": "Основные экраны платформы",
        "screens_empty": "Добавьте скриншоты в админ-панели.",
        "pricing_eyebrow": "Тарифы",
        "pricing_title": "Выберите план под размер вашего центра",
        "pricing_page_desc": "Удобные варианты оплаты на 3, 6, 9 и 12 месяцев. Тарифы легко обновляются в панели.",
        "pricing_cta": "Смотреть все тарифы",
        "pricing_pay": "Оплатить",
        "pricing_demo": "Получить демо",
        "pricing_empty": "Активные тарифы не найдены.",
        "pricing_filter_all": "Все тарифы",
        "pricing_benefit_1_title": "Быстрый запуск",
        "pricing_benefit_1_desc": "Запустите систему в короткие сроки.",
        "pricing_benefit_2_title": "Безопасность",
        "pricing_benefit_2_desc": "Ваши данные надежно защищены.",
        "pricing_benefit_3_title": "Поддержка",
        "pricing_benefit_3_desc": "Команда поддержки помогает на каждом этапе.",
        "pricing_benefit_4_title": "Облачная платформа",
        "pricing_benefit_4_desc": "Работайте из любой точки мира.",
        "plan_feature_fallback_1": "Базовые модули управления",
        "plan_feature_fallback_2": "Дашборд и статистика",
        "integrations_eyebrow": "Интеграции",
        "integrations_title": "Сервисы, которые легко подключаются к вашему процессу",
        "integrations_empty": "Добавьте блоки интеграций в админ-панели.",
        "testimonials_eyebrow": "Отзывы",
        "testimonials_title": "Что говорят владельцы учебных центров",
        "testimonials_empty": "Отзывы добавляются в админ-панели.",
        "faq_eyebrow": "FAQ",
        "faq_title": "Часто задаваемые вопросы",
        "faq_empty_q": "Сколько занимает внедрение?",
        "faq_empty_a": "Обычно запуск занимает 1–2 рабочих дня.",
        "final_eyebrow": "Пора начать",
        "final_title": "Получите демо сегодня и попробуйте бесплатно 7 дней",
        "final_text": "Сократите потери в управлении и повысьте эффективность команды.",
        "final_demo": "Получить демо",
        "final_pricing": "Тарифы",
        "metrics_title": "Пользователи ChaqmoqApp в цифрах",
        "metric_centers": "Учебные центры",
        "metric_branches": "Филиалы",
        "metric_groups": "Группы",
        "metric_students": "Ученики",
        "benefits_title": "Что вы получаете с нами?",
        "benefits_desc": "Для владельца — прозрачный контроль, для команды — быстрый рабочий цикл, для учеников — стабильный сервис.",
        "testimonial_list_title": "Отзывы наших клиентов",
        "support_page_title": "Быстрая поддержка по ChaqmoqApp",
        "support_page_desc": "Обучающие видео, документация и каналы поддержки для вашей команды.",
        "support_trust_text": "Команда поддержки отвечает в рабочие дни с 09:00 до 22:00.",
        "support_metrics_aria": "Статистика поддержки",
        "support_metric_value_1": "< 15 мин",
        "support_metric_value_2": "1 день",
        "support_metric_value_3": "300+",
        "support_metric_1": "Время ответа",
        "support_metric_2": "Старт onboarding",
        "support_metric_3": "Активные центры",
        "support_cards_title": "Разделы центра помощи",
        "support_cards_desc": "Откройте нужные материалы и каналы связи для вашей команды в одном месте.",
        "support_empty": "Карточки помощи пока не добавлены.",
        "support_empty_title": "Раздел помощи пока пуст",
        "support_empty_text": "Добавьте карточки помощи через панель superadmin, чтобы заполнить страницу.",
        "support_empty_hint": "Superadmin: Marketing -> Карточки помощи",
        "support_steps_title": "Быстрый старт",
        "support_steps_desc": "Используйте 3 шага onboarding, чтобы команда быстро перешла на платформу.",
        "support_step_1_title": "Шаг 1: Настройте доступы",
        "support_step_1_text": "Выдайте роли директору, администратору и менеджеру с нужными правами.",
        "support_step_2_title": "Шаг 2: Загрузите данные",
        "support_step_2_text": "Импортируйте учеников, группы, платежи и посещаемость одним потоком.",
        "support_step_3_title": "Шаг 3: Включите контроль",
        "support_step_3_text": "Запустите уведомления и мониторинг задолженности в ежедневной работе.",
        "support_faq_title": "Частые вопросы",
        "support_cta_title": "Нужна помощь с внедрением?",
        "support_cta_text": "Наш специалист свяжется с вами и покажет лучший сценарий запуска.",
        "support_cta_primary": "Связаться с поддержкой",
        "support_cta_secondary": "Получить демо",
        "vacancy_page_title": "Растите вместе с нами",
        "vacancy_page_desc": "Присоединяйтесь к команде ChaqmoqApp и развивайте edtech вместе с нами.",
        "vacancy_requirements": "Требования",
        "vacancy_responsibilities": "Обязанности",
        "vacancy_empty": "Сейчас активных вакансий нет.",
        "vacancy_apply": "Откликнуться",
        "legal_eyebrow": "Юридическая информация",
        "privacy_default_title": "Политика конфиденциальности",
        "terms_default_title": "Условия использования",
        "demo_page_title": "Запросите персональное демо для вашего центра",
        "demo_page_desc": "Оставьте заявку, и специалист покажет платформу на живой встрече.",
        "demo_benefits_title": "Что вы увидите на демо?",
        "demo_benefit_1": "Управление базой учеников и сегментация",
        "demo_benefit_2": "Контроль посещаемости, оплат и долгов",
        "demo_benefit_3": "Сценарии уведомлений в Telegram",
        "demo_benefit_4": "Статистика по филиалам в реальном времени",
        "demo_benefit_5": "Как ускорить работу продаж и администраторов",
        "demo_form_title": "Заявка на демо",
        "demo_submit": "Отправить заявку",
        "demo_submitting": "Отправка...",
        "demo_success": "Заявка отправлена. Наш специалист скоро свяжется с вами.",
        "demo_error": "Есть ошибки в форме. Проверьте поля.",
        "footer_tagline": "Премиальная и быстрая платформа управления для учебных центров.",
        "footer_pages": "Страницы",
        "footer_legal": "Юридическое",
        "footer_contact": "Контакты",
        "footer_social": "Соцсети",
        "footer_cta_title": "Начните цифровизацию вашего центра уже сегодня",
        "footer_cta_text": "Оставьте заявку на демо, и наша команда свяжется с вами в течение 24 часов.",
        "copyright": "Все права защищены.",
    },
    "en": {
        "lang_name": "English",
        "seo_default_title": "ChaqmoqApp | Premium Management Platform for Learning Centers",
        "seo_default_description": "Manage students, groups, attendance, payments and debt control in one cloud platform.",
        "menu_pricing": "Pricing",
        "menu_features": "Features",
        "menu_support": "Support",
        "menu_vacancies": "Vacancies",
        "menu_demo": "Get Demo",
        "menu_login": "Login",
        "menu_aria_label": "Main navigation",
        "language_switcher_aria": "Language switcher",
        "menu_toggle_aria": "Open or close menu",
        "messages_label": "Messages",
        "month_label": "mo",
        "money_label": "UZS",
        "hero_eyebrow": "Cloud SaaS for Learning Centers",
        "hero_title": "Move your center from spreadsheets to real system control",
        "hero_subtitle": "ChaqmoqApp unifies students, attendance, finance and branch analytics in one dashboard.",
        "hero_benefit_1": "7-day free trial",
        "hero_benefit_2": "Fast onboarding",
        "hero_benefit_3": "Telegram integration",
        "hero_metric_1": "Faster operations",
        "hero_metric_2": "Payment discipline",
        "hero_metric_3": "Cloud access",
        "partners_eyebrow": "Trust",
        "partners_title": "Centers working with us",
        "partners_empty": "Partner center logos have not been added yet.",
        "features_eyebrow": "Why ChaqmoqApp?",
        "features_title": "Core capabilities for owners and administrators",
        "feature_empty_title": "CRM + Attendance",
        "feature_empty_text": "Fill these marketing blocks from superadmin.",
        "before_after_eyebrow": "How it helps",
        "before_after_title": "From scattered operations to real-time control",
        "before_title": "Before",
        "after_title": "With ChaqmoqApp",
        "before_1": "Payments and attendance tracked in separate sheets",
        "before_2": "Debt control is manual",
        "before_3": "Branch reporting arrives late",
        "before_4": "Leaders lack clean data for decisions",
        "after_1": "Students, groups, attendance and finance in one system",
        "after_2": "Debt list and reminders become structured",
        "after_3": "Real-time branch-level analytics",
        "after_4": "Decision-ready data for directors",
        "screens_eyebrow": "Preview",
        "screens_title": "Key product screens",
        "screens_empty": "Add screenshots in admin panel.",
        "pricing_eyebrow": "Pricing",
        "pricing_title": "Choose the right plan for your center size",
        "pricing_page_desc": "Flexible options for 3, 6, 9, and 12 months. Plans are fully manageable from admin.",
        "pricing_cta": "View full pricing",
        "pricing_pay": "Pay now",
        "pricing_demo": "Get demo",
        "pricing_empty": "No active plans yet.",
        "pricing_filter_all": "All plans",
        "pricing_benefit_1_title": "Fast setup",
        "pricing_benefit_1_desc": "Launch your workspace in a short time.",
        "pricing_benefit_2_title": "Security",
        "pricing_benefit_2_desc": "Your data stays protected and controlled.",
        "pricing_benefit_3_title": "Support",
        "pricing_benefit_3_desc": "Get responsive help when your team needs it.",
        "pricing_benefit_4_title": "Cloud access",
        "pricing_benefit_4_desc": "Work from anywhere with stable access.",
        "plan_feature_fallback_1": "Core management modules",
        "plan_feature_fallback_2": "Dashboard and analytics",
        "integrations_eyebrow": "Integrations",
        "integrations_title": "Services that fit your workflow",
        "integrations_empty": "Add integration blocks in admin panel.",
        "testimonials_eyebrow": "Testimonials",
        "testimonials_title": "What center owners say",
        "testimonials_empty": "Testimonials are managed in admin panel.",
        "faq_eyebrow": "FAQ",
        "faq_title": "Frequently asked questions",
        "faq_empty_q": "How long does onboarding take?",
        "faq_empty_a": "Most centers launch in 1–2 business days.",
        "final_eyebrow": "Start now",
        "final_title": "Get your demo today and try 7 days free",
        "final_text": "Reduce operational loss and increase team performance.",
        "final_demo": "Get Demo",
        "final_pricing": "Pricing",
        "metrics_title": "ChaqmoqApp users in numbers",
        "metric_centers": "Learning centers",
        "metric_branches": "Branches",
        "metric_groups": "Groups",
        "metric_students": "Students",
        "benefits_title": "What do you gain with us?",
        "benefits_desc": "Clear control for owners, fast execution for teams, and reliable service quality for students.",
        "testimonial_list_title": "What our clients say",
        "support_page_title": "Fast help for ChaqmoqApp",
        "support_page_desc": "Video guides, documentation and support channels for your team.",
        "support_trust_text": "Our support team responds on business days from 09:00 to 22:00.",
        "support_metrics_aria": "Support statistics",
        "support_metric_value_1": "< 15 min",
        "support_metric_value_2": "1 day",
        "support_metric_value_3": "300+",
        "support_metric_1": "Response time",
        "support_metric_2": "Onboarding start",
        "support_metric_3": "Active centers",
        "support_cards_title": "Help center sections",
        "support_cards_desc": "Keep training materials and support channels in one professional workspace.",
        "support_empty": "No support cards yet.",
        "support_empty_title": "Support section is not configured yet",
        "support_empty_text": "Add support cards from superadmin to publish this section.",
        "support_empty_hint": "Superadmin: Marketing -> Support cards",
        "support_steps_title": "Quick onboarding",
        "support_steps_desc": "Launch your center in 3 practical steps with a clear rollout flow.",
        "support_step_1_title": "Step 1: Configure access",
        "support_step_1_text": "Assign role-based permissions for directors, admins, and managers.",
        "support_step_2_title": "Step 2: Import records",
        "support_step_2_text": "Upload students, groups, payments, and attendance data in one pass.",
        "support_step_3_title": "Step 3: Enable control",
        "support_step_3_text": "Turn on notifications and debt monitoring for daily operations.",
        "support_faq_title": "Frequent questions",
        "support_cta_title": "Need implementation support?",
        "support_cta_text": "Our specialist will contact you with a rollout plan tailored to your center.",
        "support_cta_primary": "Contact support",
        "support_cta_secondary": "Get demo",
        "vacancy_page_title": "Grow with us",
        "vacancy_page_desc": "Join ChaqmoqApp and build the next level of education technology.",
        "vacancy_requirements": "Requirements",
        "vacancy_responsibilities": "Responsibilities",
        "vacancy_empty": "No active vacancies for now.",
        "vacancy_apply": "Apply now",
        "legal_eyebrow": "Legal information",
        "privacy_default_title": "Privacy Policy",
        "terms_default_title": "Terms of Use",
        "demo_page_title": "Request a tailored demo for your center",
        "demo_page_desc": "Submit the form and our specialist will walk you through the platform.",
        "demo_benefits_title": "What you will see in the demo",
        "demo_benefit_1": "Student management and segmentation",
        "demo_benefit_2": "Attendance, payments and debt control",
        "demo_benefit_3": "Telegram notification scenarios",
        "demo_benefit_4": "Real-time branch analytics",
        "demo_benefit_5": "How to speed up sales and admin workflows",
        "demo_form_title": "Demo request",
        "demo_submit": "Submit request",
        "demo_submitting": "Submitting...",
        "demo_success": "Your request has been submitted. Our specialist will contact you soon.",
        "demo_error": "There are errors in the form. Please review fields.",
        "footer_tagline": "Premium and conversion-focused management platform for learning centers.",
        "footer_pages": "Pages",
        "footer_legal": "Legal",
        "footer_contact": "Contact",
        "footer_social": "Social",
        "footer_cta_title": "Start digitizing your center today",
        "footer_cta_text": "Submit a demo request and our team will contact you within 24 hours.",
        "copyright": "All rights reserved.",
    },
}


def _resolve_language(request, lang_code=None):
    requested = (lang_code or "").lower()[:2]
    prefixed = requested in SUPPORTED_LANGUAGES
    if prefixed:
        lang = requested
    else:
        # Unprefixed marketing URLs are always Uzbek by default.
        # This avoids stale locale cookies forcing RU/EN on `/`.
        lang = "uz"
    translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return lang, prefixed


def _strip_lang_prefix(path: str):
    match = re.match(r"^/(uz|ru|en)(/.*)?$", path or "")
    if not match:
        return path if path else "/"
    suffix = match.group(2)
    return suffix if suffix else "/"


def _build_switch_links(request, current_lang: str):
    pure_path = _strip_lang_prefix(request.path)
    query = request.META.get("QUERY_STRING", "")
    links = []
    for code in SUPPORTED_LANGUAGES:
        if code == "uz":
            url = pure_path
        else:
            suffix = pure_path if pure_path.startswith("/") else f"/{pure_path}"
            url = f"/{code}{suffix}"
        if not url.endswith("/") and pure_path in {"", "/"}:
            url += "/"
        if query:
            url = f"{url}?{query}"
        links.append(
            {
                "code": code,
                "label": LANGUAGE_LABELS[code],
                "url": url,
                "is_current": code == current_lang,
            }
        )
    return links


def _route(name: str, lang: str, prefixed: bool):
    if prefixed:
        return reverse(f"marketing_i18n:{name}", kwargs={"lang_code": lang})
    return reverse(f"marketing:{name}")


def _localize_internal_url(url: str, lang: str, prefixed: bool):
    if not url:
        return url
    if url.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return url
    if not url.startswith("/"):
        return url

    normalized = _strip_lang_prefix(url)
    if prefixed:
        suffix = normalized if normalized.startswith("/") else f"/{normalized}"
        return f"/{lang}{suffix}"
    return normalized


def _get_site_setting():
    site_setting = SiteSetting.objects.filter(is_active=True).order_by("-updated_at", "-id").first()
    if site_setting:
        return site_setting

    return SiteSetting(
        site_name="ChaqmoqApp",
        primary_cta_text="Demo olish",
        primary_cta_url="/demo/",
        secondary_cta_text="Narxlarni ko'rish",
        secondary_cta_url="/pricing/",
    )


def _localize_site(site_setting: SiteSetting, lang: str, prefixed: bool, ui: dict):
    return {
        "meta_title": site_setting.get_localized("meta_title", lang) or ui["seo_default_title"],
        "meta_description": site_setting.get_localized("meta_description", lang) or ui["seo_default_description"],
        "hero_title": site_setting.get_localized("hero_title", lang) or ui["hero_title"],
        "hero_subtitle": site_setting.get_localized("hero_subtitle", lang) or ui["hero_subtitle"],
        "primary_cta_text": site_setting.get_localized("primary_cta_text", lang) or ui["menu_demo"],
        "secondary_cta_text": site_setting.get_localized("secondary_cta_text", lang) or ui["menu_pricing"],
        "primary_cta_url": _localize_internal_url(site_setting.primary_cta_url or "/demo/", lang, prefixed),
        "secondary_cta_url": _localize_internal_url(site_setting.secondary_cta_url or "/pricing/", lang, prefixed),
    }


def _localize_feature(obj: FeatureBlock, lang: str):
    return {
        "id": obj.id,
        "icon": obj.icon,
        "image": obj.image,
        "title": obj.get_localized("title", lang) or obj.title,
        "subtitle": obj.get_localized("subtitle", lang) or obj.subtitle,
        "description": obj.get_localized("description", lang) or obj.description,
    }


def _localize_screenshot(obj: ScreenshotSection, lang: str):
    return {
        "id": obj.id,
        "image": obj.image,
        "title": obj.get_localized("title", lang) or obj.title,
        "description": obj.get_localized("description", lang) or obj.description,
    }


def _normalize_feature_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _group_plan_features(features: list[str], lang: str):
    labels = {
        "uz": {
            "management": "Boshqaruv",
            "attendance": "Davomat",
            "payments": "To'lovlar",
            "reports": "Hisobotlar",
            "notifications": "Telegram / xabarnoma",
            "support": "Support / texnik yordam",
            "extra": "Qo'shimcha imkoniyatlar",
        },
        "ru": {
            "management": "Управление",
            "attendance": "Посещаемость",
            "payments": "Платежи",
            "reports": "Отчеты",
            "notifications": "Telegram / уведомления",
            "support": "Поддержка / техпомощь",
            "extra": "Дополнительные возможности",
        },
        "en": {
            "management": "Management",
            "attendance": "Attendance",
            "payments": "Payments",
            "reports": "Reports",
            "notifications": "Telegram / notifications",
            "support": "Support / technical help",
            "extra": "Additional capabilities",
        },
    }.get(lang, {
        "management": "Boshqaruv",
        "attendance": "Davomat",
        "payments": "To'lovlar",
        "reports": "Hisobotlar",
        "notifications": "Telegram / xabarnoma",
        "support": "Support / texnik yordam",
        "extra": "Qo'shimcha imkoniyatlar",
    })

    group_specs = [
        (
            "management",
            (
                "boshqaruv",
                "admin",
                "administrator",
                "роль",
                "role",
                "ruxsat",
                "permission",
                "markaz",
                "center",
                "filial",
                "branch",
                "guruh",
                "group",
                "crm",
                "student",
                "o'quvchi",
                "ученик",
                "course",
                "kurs",
            ),
        ),
        (
            "attendance",
            (
                "davomat",
                "attendance",
                "посещ",
                "yo'qlama",
                "yoqlama",
                "jurnal",
                "журнал",
            ),
        ),
        (
            "payments",
            (
                "to'lov",
                "to‘lov",
                "tolov",
                "payment",
                "оплат",
                "payme",
                "click",
                "qarz",
                "debt",
                "invoice",
                "billing",
                "moliya",
                "финан",
            ),
        ),
        (
            "reports",
            (
                "hisobot",
                "report",
                "analit",
                "аналит",
                "stat",
                "статист",
                "dashboard",
                "дашборд",
                "kpi",
            ),
        ),
        (
            "notifications",
            (
                "telegram",
                "xabar",
                "xabarnoma",
                "notification",
                "уведом",
                "sms",
                "bot",
                "reminder",
                "eslatma",
            ),
        ),
        (
            "support",
            (
                "support",
                "yordam",
                "texnik",
                "поддерж",
                "тех",
                "onboarding",
                "training",
                "consult",
                "konsult",
                "qo'llab",
                "qo‘llab",
            ),
        ),
    ]

    grouped: dict[str, list[str]] = {key: [] for key, _ in group_specs}
    grouped["extra"] = []

    for raw_feature in features:
        feature_text = (raw_feature or "").strip()
        if not feature_text:
            continue

        normalized = _normalize_feature_text(feature_text)
        matched_group = "extra"
        for key, keywords in group_specs:
            if any(keyword in normalized for keyword in keywords):
                matched_group = key
                break
        grouped[matched_group].append(feature_text)

    ordered_keys = [key for key, _ in group_specs] + ["extra"]
    return [
        {"key": key, "title": labels[key], "items": grouped[key]}
        for key in ordered_keys
        if grouped[key]
    ]


def _localize_plan(plan: PricingPlan, lang: str):
    features = [
        feature.get_localized("text", lang) or feature.text
        for feature in plan.features.all().order_by("order", "id")
    ]
    highlight_limit = 6
    return {
        "id": plan.id,
        "name": plan.get_localized("name", lang) or plan.name,
        "student_range": plan.get_localized("student_range", lang) or plan.student_range,
        "duration_months": plan.duration_months,
        "old_price": plan.old_price,
        "current_price": plan.current_price,
        "discount_label": plan.get_localized("discount_label", lang) or plan.discount_label,
        "badge_text": plan.get_localized("badge_text", lang) or plan.badge_text,
        "is_recommended": plan.is_recommended,
        "features": features,
        "highlight_features": features[:highlight_limit],
        "extra_features_count": max(0, len(features) - highlight_limit),
        "features_count": len(features),
        "feature_groups": _group_plan_features(features, lang),
    }


def _localize_testimonial(obj: Testimonial, lang: str):
    return {
        "id": obj.id,
        "full_name": obj.full_name,
        "center_name": obj.center_name,
        "role": obj.get_localized("role", lang) or obj.role,
        "text": obj.get_localized("text", lang) or obj.text,
        "avatar": obj.avatar,
        "rating": obj.rating,
    }


def _localize_faq(obj: FAQ, lang: str):
    return {
        "id": obj.id,
        "question": obj.get_localized("question", lang) or obj.question,
        "answer": obj.get_localized("answer", lang) or obj.answer,
    }


def _localize_support(obj: SupportCard, lang: str):
    return {
        "id": obj.id,
        "icon": obj.icon,
        "title": obj.get_localized("title", lang) or obj.title,
        "description": obj.get_localized("description", lang) or obj.description,
        "button_text": obj.get_localized("button_text", lang) or obj.button_text,
        "button_url": obj.button_url,
    }


def _localize_vacancy(obj: Vacancy, lang: str):
    employment = obj.get_localized("employment_type", lang) or obj.get_employment_type_display()
    return {
        "id": obj.id,
        "title": obj.get_localized("title", lang) or obj.title,
        "city": obj.city,
        "employment_type": employment,
        "department": obj.get_localized("department", lang) or obj.department,
        "description": obj.get_localized("description", lang) or obj.description,
        "requirements": obj.get_localized("requirements", lang) or obj.requirements,
        "responsibilities": obj.get_localized("responsibilities", lang) or obj.responsibilities,
        "apply_url": obj.apply_url,
        "apply_button_text": obj.apply_button_text,
    }


def _base_context(request, lang_code=None):
    lang, prefixed = _resolve_language(request, lang_code)
    ui = MARKETING_UI.get(lang, MARKETING_UI["uz"])
    site_setting = _get_site_setting()
    site_content = _localize_site(site_setting, lang, prefixed, ui)

    routes = {
        "index": _route("index", lang, prefixed),
        "pricing": _route("pricing", lang, prefixed),
        "demo": _route("demo", lang, prefixed),
        "support": _route("support", lang, prefixed),
        "vacancies": _route("vacancies", lang, prefixed),
        "privacy": _route("privacy", lang, prefixed),
        "terms": _route("terms", lang, prefixed),
    }

    return {
        "site_setting": site_setting,
        "site_content": site_content,
        "current_year": timezone.now().year,
        "meta_title": site_content["meta_title"],
        "meta_description": site_content["meta_description"],
        "canonical_url": request.build_absolute_uri(request.path),
        "ui": ui,
        "current_lang": lang,
        "lang_links": _build_switch_links(request, lang),
        "routes": routes,
        "prefixed_lang": prefixed,
    }


def index(request, lang_code=None):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("platform_global:superadmin_dashboard")

    context = _base_context(request, lang_code)
    lang = context["current_lang"]

    feature_qs = FeatureBlock.objects.filter(is_active=True, section=FeatureBlock.Section.FEATURE)
    integration_qs = FeatureBlock.objects.filter(is_active=True, section=FeatureBlock.Section.INTEGRATION)
    solution_qs = FeatureBlock.objects.filter(is_active=True, section=FeatureBlock.Section.SOLUTION)
    pricing_qs = PricingPlan.objects.filter(is_active=True).prefetch_related("features").order_by("duration_months", "order", "id")

    partner_logos = [logo for logo in PartnerLogo.objects.filter(is_active=True).order_by("order", "id") if logo.image]
    partner_logo_count = len(partner_logos)

    partner_marquee_logos = partner_logos

    context.update(
        {
            "active_menu": "home",
            "partner_logos": partner_logos,
            "partner_logo_count": partner_logo_count,
            "partner_marquee_logos": partner_marquee_logos,
            "feature_blocks": [_localize_feature(obj, lang) for obj in feature_qs],
            "integration_blocks": [_localize_feature(obj, lang) for obj in integration_qs],
            "solution_blocks": [_localize_feature(obj, lang) for obj in solution_qs],
            "screenshots": [
                _localize_screenshot(obj, lang)
                for obj in ScreenshotSection.objects.filter(is_active=True).order_by("order", "id")
            ],
            "testimonials": [
                _localize_testimonial(obj, lang)
                for obj in Testimonial.objects.filter(is_active=True).order_by("order", "id")
            ],
            "faqs": [_localize_faq(obj, lang) for obj in FAQ.objects.filter(is_active=True).order_by("order", "id")],
            "pricing_preview": [_localize_plan(plan, lang) for plan in pricing_qs],
        }
    )
    return render(request, "marketing/index.html", context)


def pricing(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]
    plans = PricingPlan.objects.filter(is_active=True).prefetch_related("features").order_by("duration_months", "order", "id")

    duration_map = OrderedDict()
    for plan in plans:
        duration_map.setdefault(plan.duration_months, []).append(_localize_plan(plan, lang))

    context.update(
        {
            "active_menu": "pricing",
            "duration_map": duration_map,
            "duration_filters": list(duration_map.keys()),
        }
    )
    return render(request, "marketing/pricing.html", context)


def demo(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]

    if request.method == "POST":
        form = DemoLeadForm(request.POST, lang_code=lang)
        if form.is_valid():
            lead = form.save()
            notify_telegram_new_lead(lead)
            messages.success(request, context["ui"]["demo_success"])
            if context["prefixed_lang"]:
                return redirect("marketing_i18n:demo", lang_code=lang)
            return redirect("marketing:demo")
        messages.error(request, context["ui"]["demo_error"])
    else:
        form = DemoLeadForm(lang_code=lang)

    context.update({"active_menu": "demo", "form": form})
    return render(request, "marketing/demo.html", context)


def support(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]
    ui = context["ui"]
    context.update(
        {
            "active_menu": "support",
            "support_cards": [
                _localize_support(obj, lang)
                for obj in SupportCard.objects.filter(is_active=True).order_by("order", "id")
            ],
            "support_faqs": [
                _localize_faq(obj, lang)
                for obj in FAQ.objects.filter(is_active=True).order_by("order", "id")[:4]
            ],
            "support_steps": [
                {"title": ui["support_step_1_title"], "text": ui["support_step_1_text"]},
                {"title": ui["support_step_2_title"], "text": ui["support_step_2_text"]},
                {"title": ui["support_step_3_title"], "text": ui["support_step_3_text"]},
            ],
        }
    )
    return render(request, "marketing/support.html", context)


def vacancies(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]
    context.update(
        {
            "active_menu": "vacancies",
            "vacancies": [
                _localize_vacancy(obj, lang)
                for obj in Vacancy.objects.filter(is_active=True).order_by("order", "id")
            ],
        }
    )
    return render(request, "marketing/vacancies.html", context)


def privacy(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]
    page = StaticPage.objects.filter(key=StaticPage.PageKey.PRIVACY, is_active=True).first()

    if page:
        page_title = page.get_localized("title", lang) or context["ui"]["privacy_default_title"]
        page_content = page.get_localized("content", lang) or ""
    else:
        page_title = context["ui"]["privacy_default_title"]
        page_content = ""

    context.update(
        {
            "active_menu": "privacy",
            "page_title": page_title,
            "page_content": page_content,
            "meta_title": f"{page_title} | {context['site_setting'].site_name}",
        }
    )
    return render(request, "marketing/privacy.html", context)


def terms(request, lang_code=None):
    context = _base_context(request, lang_code)
    lang = context["current_lang"]
    page = StaticPage.objects.filter(key=StaticPage.PageKey.TERMS, is_active=True).first()

    if page:
        page_title = page.get_localized("title", lang) or context["ui"]["terms_default_title"]
        page_content = page.get_localized("content", lang) or ""
    else:
        page_title = context["ui"]["terms_default_title"]
        page_content = ""

    context.update(
        {
            "active_menu": "terms",
            "page_title": page_title,
            "page_content": page_content,
            "meta_title": f"{page_title} | {context['site_setting'].site_name}",
        }
    )
    return render(request, "marketing/terms.html", context)
