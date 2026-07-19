"""
Family bot — 3 tilli (O'zbekcha / Русский / Ўзбекча) markaziy tarjima moduli.

- Til foydalanuvchi bo'yicha xotirada saqlanadi (telegram_id → lang).
  /start har safar tilni qayta so'raydi, shuning uchun bu yetarli.
- Tugma yozuvlari (BTN) ham, ularni ushlaydigan filtrlar ham SHU dictdan olinadi,
  shuning uchun handler har doim to'g'ri mos keladi.
- Xabarlar QISQA (2 og'iz gap).
"""
from __future__ import annotations

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

LANGS = ("uz", "ru", "cy")
DEFAULT_LANG = "uz"

# ── Til xotirasi (telegram_id → 'uz'|'ru'|'cy') ──────────────────────────────
_LANG_CACHE: dict[int, str] = {}


def set_lang(tg_id: int, lang: str) -> None:
    if lang in LANGS:
        _LANG_CACHE[int(tg_id)] = lang


def get_lang(tg_id) -> str:
    return _LANG_CACHE.get(int(tg_id), DEFAULT_LANG)


# ── Reply-menyu tugma yozuvlari (emoji bir xil, so'z tarjima) ────────────────
BTN: dict[str, dict[str, str]] = {
    # Ota-ona
    "p_children":   {"uz": "👶 Bolalarim",       "ru": "👶 Мои дети",        "cy": "👶 Болаларим"},
    "p_attendance": {"uz": "📊 Davomat",          "ru": "📊 Посещаемость",    "cy": "📊 Давомат"},
    "p_payment":    {"uz": "💰 To'lovlar",        "ru": "💰 Оплата",          "cy": "💰 Тўловлар"},
    "p_balance":    {"uz": "⚡ Chaqmoq ballari",  "ru": "⚡ Баллы Chaqmoq",    "cy": "⚡ Чақмоқ баллари"},
    "p_teacher":    {"uz": "📞 O'qituvchi",       "ru": "📞 Учитель",         "cy": "📞 Ўқитувчи"},
    "p_addchild":   {"uz": "➕ Farzand qo'shish", "ru": "➕ Добавить ребёнка", "cy": "➕ Фарзанд қўшиш"},
    # O'quvchi
    "s_status":     {"uz": "📊 Holatim",          "ru": "📊 Моё состояние",   "cy": "📊 Ҳолатим"},
    "s_balance":    {"uz": "⚡ Balans",           "ru": "⚡ Баланс",          "cy": "⚡ Баланс"},
    "s_schedule":   {"uz": "📅 Dars jadvali",     "ru": "📅 Расписание",      "cy": "📅 Дарс жадвали"},
    "s_payment":    {"uz": "💰 To'lovim",         "ru": "💰 Мои оплаты",      "cy": "💰 Тўловим"},
    "s_ranking":    {"uz": "🏆 Reyting",          "ru": "🏆 Рейтинг",         "cy": "🏆 Рейтинг"},
    "s_store":      {"uz": "🛍 Do'kon",           "ru": "🛍 Магазин",         "cy": "🛍 Дўкон"},
    "s_settings":   {"uz": "🔔 Sozlamalar",       "ru": "🔔 Настройки",       "cy": "🔔 Созламалар"},
    # Umumiy
    "c_sitelogin":  {"uz": "🔑 Saytga kirish",    "ru": "🔑 Вход на сайт",    "cy": "🔑 Сайтга кириш"},
    "c_logout":     {"uz": "🚪 Chiqish",          "ru": "🚪 Выход",           "cy": "🚪 Чиқиш"},
}

# ── Inline tugma yozuvlari ──────────────────────────────────────────────────
IKB: dict[str, dict[str, str]] = {
    "role_parent":   {"uz": "👨‍👩‍👧 Men ota-ona",  "ru": "👨‍👩‍👧 Я родитель",  "cy": "👨‍👩‍👧 Мен ота-она"},
    "role_student":  {"uz": "🎓 Men o'quvchi",    "ru": "🎓 Я ученик",         "cy": "🎓 Мен ўқувчи"},
    "retry":         {"uz": "🔄 Qayta urinish",   "ru": "🔄 Ещё раз",          "cy": "🔄 Қайта уриниш"},
    "cancel":        {"uz": "🔄 Bekor qilish",    "ru": "🔄 Отмена",           "cy": "🔄 Бекор қилиш"},
    "back":          {"uz": "🔄 Qaytish",         "ru": "🔄 Назад",            "cy": "🔄 Қайтиш"},
    "share_contact": {"uz": "📱 Raqamni ulashish","ru": "📱 Отправить номер",  "cy": "📱 Рақамни улашиш"},
    "confirm_open":  {"uz": "✅ Tasdiqlash",      "ru": "✅ Подтвердить",      "cy": "✅ Тасдиқлаш"},
    "confirm_parent":{"uz": "✅ Tasdiqlab ochish","ru": "✅ Подтвердить",      "cy": "✅ Тасдиқлаб очиш"},
    "add_child":     {"uz": "➕ Farzand qo'shish","ru": "➕ Добавить ребёнка", "cy": "➕ Фарзанд қўшиш"},
    "new_profile":   {"uz": "➕ Yangi profil",    "ru": "➕ Новый профиль",    "cy": "➕ Янги профил"},
    "method_phone":  {"uz": "📱 Telefon orqali",  "ru": "📱 По номеру",        "cy": "📱 Телефон орқали"},
    "method_name":   {"uz": "📝 Ism va sana orqali","ru": "📝 По имени и дате","cy": "📝 Исм ва сана орқали"},
    "magic_login":   {"uz": "🔓 Bir bosishda kirish","ru": "🔓 Войти одним нажатием","cy": "🔓 Бир босишда кириш"},
    "buy_yes":       {"uz": "✅ Ha, tasdiqlayman","ru": "✅ Да, подтверждаю",  "cy": "✅ Ҳа, тасдиқлайман"},
    "buy_no":        {"uz": "❌ Bekor qilish",    "ru": "❌ Отмена",           "cy": "❌ Бекор қилиш"},
    "notif_on":      {"uz": "🔔 Yoqish",          "ru": "🔔 Включить",         "cy": "🔔 Ёқиш"},
    "notif_off":     {"uz": "🔕 O'chirish",       "ru": "🔕 Выключить",        "cy": "🔕 Ўчириш"},
    "lang_uz":       {"uz": "🇺🇿 O'zbekcha",      "ru": "🇺🇿 O'zbekcha",       "cy": "🇺🇿 O'zbekcha"},
    "lang_ru":       {"uz": "🇷🇺 Русский",        "ru": "🇷🇺 Русский",         "cy": "🇷🇺 Русский"},
    "lang_cy":       {"uz": "🇺🇿 Ўзбекча",        "ru": "🇺🇿 Ўзбекча",         "cy": "🇺🇿 Ўзбекча"},
}

# ── Xabarlar (QISQA) ────────────────────────────────────────────────────────
M: dict[str, dict[str, str]] = {
    "linked_one":   {"uz": "👋 Assalomu alaykum, {name}!\nMenyudan foydalaning 👇",
                     "ru": "👋 Здравствуйте, {name}!\nВыберите пункт меню 👇",
                     "cy": "👋 Ассалому алайкум, {name}!\nМенюдан фойдаланинг 👇"},
    "linked_many":  {"uz": "👋 Assalomu alaykum!\nProfilingizni tanlang 👇",
                     "ru": "👋 Здравствуйте!\nВыберите профиль 👇",
                     "cy": "👋 Ассалому алайкум!\nПрофилингизни танланг 👇"},
    "onboard_who":  {"uz": "👋 Xush kelibsiz!\nKim ekaningizni tanlang 👇",
                     "ru": "👋 Добро пожаловать!\nВыберите, кто вы 👇",
                     "cy": "👋 Хуш келибсиз!\nКим эканингизни танланг 👇"},
    "pick_who":     {"uz": "Kim ekaningizni tanlang 👇",
                     "ru": "Выберите, кто вы 👇",
                     "cy": "Ким эканингизни танланг 👇"},
    "student_method":{"uz": "🎓 O'quvchi sifatida kirasiz.\nSizni qanday topamiz? 👇",
                     "ru": "🎓 Вход как ученик.\nКак вас найти? 👇",
                     "cy": "🎓 Ўқувчи сифатида кирасиз.\nСизни қандай топамиз? 👇"},
    "ask_phone":    {"uz": "📱 Telefon raqamingizni yuboring.\nTugmani bosing yoki yozing: <code>+998901234567</code>",
                     "ru": "📱 Отправьте свой номер.\nНажмите кнопку или напишите: <code>+998901234567</code>",
                     "cy": "📱 Телефон рақамингизни юборинг.\nТугмани босинг ёки ёзинг: <code>+998901234567</code>"},
    "ask_name":     {"uz": "📝 To'liq ismingizni yozing (masalan: <code>Aliyev Akmal</code>).",
                     "ru": "📝 Напишите полное имя (например: <code>Aliyev Akmal</code>).",
                     "cy": "📝 Тўлиқ исмингизни ёзинг (масалан: <code>Aliyev Akmal</code>)."},
    "ask_birthdate":{"uz": "📅 Tug'ilgan sanangizni yozing: <code>15.03.2010</code>.",
                     "ru": "📅 Напишите дату рождения: <code>15.03.2010</code>.",
                     "cy": "📅 Туғилган санангизни ёзинг: <code>15.03.2010</code>."},
    "min3":         {"uz": "Kamida 3 harf yozing.",
                     "ru": "Введите минимум 3 буквы.",
                     "cy": "Камида 3 ҳарф ёзинг."},
    "checking":     {"uz": "🔍 Tekshirilmoqda...",
                     "ru": "🔍 Проверяем...",
                     "cy": "🔍 Текширилмоқда..."},
    "too_many":     {"uz": "⏱ Juda ko'p urinish. Biroz kuting.",
                     "ru": "⏱ Слишком много попыток. Подождите немного.",
                     "cy": "⏱ Жуда кўп уриниш. Бироз кутинг."},
    "not_found_phone":{"uz": "❌ Raqamingiz topilmadi.\nMarkazga murojaat qiling.",
                     "ru": "❌ Номер не найден.\nОбратитесь в центр.",
                     "cy": "❌ Рақамингиз топилмади.\nМарказга мурожаат қилинг."},
    "phone_bad":    {"uz": "📱 Raqam noto'g'ri.\nMasalan: <code>+998901234567</code>",
                     "ru": "📱 Неверный номер.\nНапример: <code>+998901234567</code>",
                     "cy": "📱 Рақам нотўғри.\nМасалан: <code>+998901234567</code>"},
    "not_found_name":{"uz": "❌ Ma'lumotlaringiz topilmadi.\nSanani qayta yozing yoki bekor qiling.",
                     "ru": "❌ Данные не найдены.\nВведите дату снова или отмените.",
                     "cy": "❌ Маълумотларингиз топилмади.\nСанани қайта ёзинг ёки бекор қилинг."},
    "found_one":    {"uz": "✅ Topildi: <b>{name}</b> · {center}.\nTasdiqlang 👇",
                     "ru": "✅ Найдено: <b>{name}</b> · {center}.\nПодтвердите 👇",
                     "cy": "✅ Топилди: <b>{name}</b> · {center}.\nТасдиқланг 👇"},
    "found_many":   {"uz": "🔎 {n} ta topildi.\nO'zingizni tanlang 👇",
                     "ru": "🔎 Найдено {n}.\nВыберите себя 👇",
                     "cy": "🔎 {n} та топилди.\nЎзингизни танланг 👇"},
    "parent_no_child":{"uz": "👨‍👩‍👧 Ota-ona profili topildi, farzand yo'q.\nTasdiqlab, farzand qo'shing 👇",
                     "ru": "👨‍👩‍👧 Профиль родителя найден, детей нет.\nПодтвердите и добавьте ребёнка 👇",
                     "cy": "👨‍👩‍👧 Ота-она профили топилди, фарзанд йўқ.\nТасдиқлаб, фарзанд қўшинг 👇"},
    "parent_children_found":{"uz": "👨‍👩‍👧 {n} ta farzand topildi.\nFarzandingizni tanlab tasdiqlang 👇",
                     "ru": "👨‍👩‍👧 Найдено детей: {n}.\nВыберите ребёнка и подтвердите 👇",
                     "cy": "👨‍👩‍👧 {n} та фарзанд топилди.\nФарзандингизни танлаб тасдиқланг 👇"},
    "panel_open":   {"uz": "✅ {role} paneli ochildi, {name}.\nMenyudan foydalaning 👇",
                     "ru": "✅ Панель ({role}) открыта, {name}.\nВыберите пункт меню 👇",
                     "cy": "✅ {role} панели очилди, {name}.\nМенюдан фойдаланинг 👇"},
    "role_parent":  {"uz": "Ota-ona", "ru": "родитель", "cy": "Ота-она"},
    "role_student": {"uz": "O'quvchi", "ru": "ученик", "cy": "Ўқувчи"},
    "share_own":    {"uz": "❌ Iltimos, <b>o'zingizning</b> raqamingizni ulashing.",
                     "ru": "❌ Пожалуйста, отправьте <b>свой</b> номер.",
                     "cy": "❌ Илтимос, <b>ўзингизнинг</b> рақамингизни улашинг."},
    "add_child_ask":{"uz": "🔍 Farzandingiz ismini yozing (masalan: <code>Aliyev Akmal</code>).",
                     "ru": "🔍 Напишите имя ребёнка (например: <code>Aliyev Akmal</code>).",
                     "cy": "🔍 Фарзандингиз исмини ёзинг (масалан: <code>Aliyev Akmal</code>)."},
    "child_found_many":{"uz": "🔎 {n} ta topildi.\nFarzandingizni tanlang 👇",
                     "ru": "🔎 Найдено {n}.\nВыберите ребёнка 👇",
                     "cy": "🔎 {n} та топилди.\nФарзандингизни танланг 👇"},
    "child_not_found":{"uz": "❌ Farzand topilmadi.\nIsmni boshqacha yozing yoki bekor qiling.",
                     "ru": "❌ Ребёнок не найден.\nНапишите имя иначе или отмените.",
                     "cy": "❌ Фарзанд топилмади.\nИсмни бошқача ёзинг ёки бекор қилинг."},
    "ask_child_birthdate":{"uz": "📅 Farzandingiz tug'ilgan sanasini yozing: <code>15.03.2010</code>.",
                     "ru": "📅 Напишите дату рождения ребёнка: <code>15.03.2010</code>.",
                     "cy": "📅 Фарзандингиз туғилган санасини ёзинг: <code>15.03.2010</code>."},
    "child_added":  {"uz": "✅ {name} qo'shildi!\nMenyudan foydalaning 👇",
                     "ru": "✅ {name} добавлен(а)!\nВыберите пункт меню 👇",
                     "cy": "✅ {name} қўшилди!\nМенюдан фойдаланинг 👇"},
    "session_expired":{"uz": "⏳ Sessiya tugadi. /start bosing.",
                     "ru": "⏳ Сессия истекла. Нажмите /start.",
                     "cy": "⏳ Сессия тугади. /start босинг."},
    "confirm_fail": {"uz": "❌ Tasdiqlab bo'lmadi.",
                     "ru": "❌ Не удалось подтвердить.",
                     "cy": "❌ Тасдиқлаб бўлмади."},
    "back_to_menu": {"uz": "↩️ Menyuga qaytdingiz.\nBo'lim tanlang 👇",
                     "ru": "↩️ Вы вернулись в меню.\nВыберите раздел 👇",
                     "cy": "↩️ Менюга қайтдингиз.\nБўлим танланг 👇"},
    "only_parents": {"uz": "❌ Bu tugma faqat ota-onalar uchun.",
                     "ru": "❌ Эта кнопка только для родителей.",
                     "cy": "❌ Бу тугма фақат ота-оналар учун."},
    "pick_child_first":{"uz": "ℹ️ Avval bolani tanlang.",
                     "ru": "ℹ️ Сначала выберите ребёнка.",
                     "cy": "ℹ️ Аввал болани танланг."},
    "no_children":  {"uz": "ℹ️ Bog'langan bola yo'q.",
                     "ru": "ℹ️ Привязанных детей нет.",
                     "cy": "ℹ️ Боғланган бола йўқ."},
    "generic_error":{"uz": "❌ Xatolik yuz berdi.",
                     "ru": "❌ Произошла ошибка.",
                     "cy": "❌ Хатолик юз берди."},
    "logout_done":  {"uz": "🚪 Chiqdingiz. Qayta kirish uchun /start bosing.",
                     "ru": "🚪 Вы вышли. Для входа нажмите /start.",
                     "cy": "🚪 Чиқдингиз. Қайта кириш учун /start босинг."},
    "logout_pick":  {"uz": "🚪 Qaysi profildan chiqmoqchisiz? 👇",
                     "ru": "🚪 Из какого профиля выйти? 👇",
                     "cy": "🚪 Қайси профилдан чиқмоқчисиз? 👇"},
    "unlink_q":     {"uz": "❓ Ishonchingiz komilmi?",
                     "ru": "❓ Вы уверены?",
                     "cy": "❓ Ишончингиз комилми?"},
    "unlink_all_btn":{"uz": "❌ Hammasini uzish",
                     "ru": "❌ Отвязать все",
                     "cy": "❌ Ҳаммасини узиш"},
    "unlink_done":  {"uz": "✅ Profil uzildi.",
                     "ru": "✅ Профиль отвязан.",
                     "cy": "✅ Профил узилди."},
    # Saytga kirish (magic link)
    "creds_title":  {"uz": "🔑 <b>{name}</b> — saytga kirish.\nBir bosishda kiring 👇",
                     "ru": "🔑 <b>{name}</b> — вход на сайт.\nВойдите одним нажатием 👇",
                     "cy": "🔑 <b>{name}</b> — сайтга кириш.\nБир босишда киринг 👇"},
    "creds_manual": {"uz": "<i>Yoki qo'lda:</i>\nLogin: <code>{email}</code>\nParol: <code>{password}</code>",
                     "ru": "<i>Или вручную:</i>\nЛогин: <code>{email}</code>\nПароль: <code>{password}</code>",
                     "cy": "<i>Ёки қўлда:</i>\nЛогин: <code>{email}</code>\nПарол: <code>{password}</code>"},
    "creds_fail":   {"uz": "❌ Login berib bo'lmadi.",
                     "ru": "❌ Не удалось выдать доступ.",
                     "cy": "❌ Логин бериб бўлмади."},
    # Ota-ona panel
    "p_children_title":{"uz": "👶 Bolalarim.\nBolani tanlang 👇",
                     "ru": "👶 Мои дети.\nВыберите ребёнка 👇",
                     "cy": "👶 Болаларим.\nБолани танланг 👇"},
    "p_child_selected":{"uz": "✅ <b>{name}</b> tanlandi.",
                     "ru": "✅ <b>{name}</b> выбран(а).",
                     "cy": "✅ <b>{name}</b> танланди."},
    "p_attendance": {"uz": "📊 <b>{name}</b> — davomat: <b>{rate}%</b> ({present}/{total}).",
                     "ru": "📊 <b>{name}</b> — посещаемость: <b>{rate}%</b> ({present}/{total}).",
                     "cy": "📊 <b>{name}</b> — давомат: <b>{rate}%</b> ({present}/{total})."},
    "p_payment":    {"uz": "💰 <b>{name}</b> — qarz: <b>{debt} so'm</b>. Oxirgi to'lov: {last}.",
                     "ru": "💰 <b>{name}</b> — долг: <b>{debt} сум</b>. Последняя оплата: {last}.",
                     "cy": "💰 <b>{name}</b> — қарз: <b>{debt} сўм</b>. Охирги тўлов: {last}."},
    "p_balance":    {"uz": "⚡ <b>{name}</b> — <b>{balance}</b> chaqmoq. Reyting: {rank}.",
                     "ru": "⚡ <b>{name}</b> — <b>{balance}</b> Chaqmoq. Рейтинг: {rank}.",
                     "cy": "⚡ <b>{name}</b> — <b>{balance}</b> чақмоқ. Рейтинг: {rank}."},
    "p_teacher":    {"uz": "📞 <b>{name}</b> · {group}.\nUstoz: {teacher} ({phone}).",
                     "ru": "📞 <b>{name}</b> · {group}.\nУчитель: {teacher} ({phone}).",
                     "cy": "📞 <b>{name}</b> · {group}.\nУстоз: {teacher} ({phone})."},
    # O'quvchi panel
    "s_status":     {"uz": "📊 Davomat: <b>{rate}%</b> ({present}/{total}). Qarz: <b>{debt} so'm</b>.",
                     "ru": "📊 Посещаемость: <b>{rate}%</b> ({present}/{total}). Долг: <b>{debt} сум</b>.",
                     "cy": "📊 Давомат: <b>{rate}%</b> ({present}/{total}). Қарз: <b>{debt} сўм</b>."},
    "s_balance":    {"uz": "⚡ Balans: <b>{balance}</b>. O'rningiz: <b>{rank}</b>/{total}.",
                     "ru": "⚡ Баланс: <b>{balance}</b>. Ваше место: <b>{rank}</b>/{total}.",
                     "cy": "⚡ Баланс: <b>{balance}</b>. Ўрнингиз: <b>{rank}</b>/{total}."},
    "s_schedule_title":{"uz": "📅 Shu haftadagi darslaringiz:",
                     "ru": "📅 Ваши занятия на этой неделе:",
                     "cy": "📅 Шу ҳафтадаги дарсларингиз:"},
    "s_no_schedule":{"uz": "ℹ️ Dars jadvali topilmadi.",
                     "ru": "ℹ️ Расписание не найдено.",
                     "cy": "ℹ️ Дарс жадвали топилмади."},
    "s_payment":    {"uz": "💰 Qarz: <b>{debt} so'm</b>. Oxirgi to'lov: {last}.",
                     "ru": "💰 Долг: <b>{debt} сум</b>. Последняя оплата: {last}.",
                     "cy": "💰 Қарз: <b>{debt} сўм</b>. Охирги тўлов: {last}."},
    "s_ranking":    {"uz": "🏆 <b>Umumiy reyting</b>\n⚡ Balans: <b>{balance}</b> · O'rningiz: <b>{rank}</b>/{total}",
                     "ru": "🏆 <b>Общий рейтинг</b>\n⚡ Баланс: <b>{balance}</b> · Место: <b>{rank}</b>/{total}",
                     "cy": "🏆 <b>Умумий рейтинг</b>\n⚡ Баланс: <b>{balance}</b> · Ўрнингиз: <b>{rank}</b>/{total}"},
    "s_store_title":{"uz": "🛍 Do'kon.\nMahsulotni tanlang 👇",
                     "ru": "🛍 Магазин.\nВыберите товар 👇",
                     "cy": "🛍 Дўкон.\nМаҳсулотни танланг 👇"},
    "s_no_products":{"uz": "ℹ️ Do'konda mahsulot yo'q.",
                     "ru": "ℹ️ В магазине пока нет товаров.",
                     "cy": "ℹ️ Дўконда маҳсулот йўқ."},
    "s_buy_ask":    {"uz": "🛍 <b>{name}</b> — {price} chaqmoq.\nTasdiqlaysizmi?",
                     "ru": "🛍 <b>{name}</b> — {price} Chaqmoq.\nПодтвердить?",
                     "cy": "🛍 <b>{name}</b> — {price} чақмоқ.\nТасдиқлайсизми?"},
    "s_buy_sent":   {"uz": "✅ So'rov yuborildi: <b>{name}</b>.\nTasdiqlansa balansdan yechiladi.",
                     "ru": "✅ Заявка отправлена: <b>{name}</b>.\nПосле подтверждения спишется с баланса.",
                     "cy": "✅ Сўров юборилди: <b>{name}</b>.\nТасдиқланса баланcдан ечилади."},
    "s_buy_cancel": {"uz": "❌ Bekor qilindi.",
                     "ru": "❌ Отменено.",
                     "cy": "❌ Бекор қилинди."},
    "s_settings":   {"uz": "🔔 Bildirishnoma: <b>{status}</b>.\nTugma orqali o'zgartiring 👇",
                     "ru": "🔔 Уведомления: <b>{status}</b>.\nИзмените кнопкой 👇",
                     "cy": "🔔 Билдиришнома: <b>{status}</b>.\nТугма орқали ўзгартиринг 👇"},
    "s_notif_toggled":{"uz": "✅ Bildirishnoma {status}.",
                     "ru": "✅ Уведомления {status}.",
                     "cy": "✅ Билдиришнома {status}."},
    "on":  {"uz": "yoqilgan", "ru": "включены", "cy": "ёқилган"},
    "off": {"uz": "o'chirilgan", "ru": "выключены", "cy": "ўчирилган"},
    "on_v":  {"uz": "yoqildi", "ru": "включены", "cy": "ёқилди"},
    "off_v": {"uz": "o'chirildi", "ru": "выключены", "cy": "ўчирилди"},
    # ── To'lov (oyma-oy) — batafsil ──
    "pay_title_p":  {"uz": "💰 <b>{name}</b> — to'lovlar",
                     "ru": "💰 <b>{name}</b> — оплаты",
                     "cy": "💰 <b>{name}</b> — тўловлар"},
    "pay_title_s":  {"uz": "💰 <b>To'lovlarim</b>",
                     "ru": "💰 <b>Мои оплаты</b>",
                     "cy": "💰 <b>Тўловларим</b>"},
    "pay_total_debt":{"uz": "Umumiy qarz: <b>{debt} so'm</b>",
                     "ru": "Общий долг: <b>{debt} сум</b>",
                     "cy": "Умумий қарз: <b>{debt} сўм</b>"},
    "pay_no_debt":  {"uz": "✅ Qarzdorlik yo'q.",
                     "ru": "✅ Задолженности нет.",
                     "cy": "✅ Қарздорлик йўқ."},
    "pay_months_h": {"uz": "🗓 <b>Oyma-oy:</b>",
                     "ru": "🗓 <b>По месяцам:</b>",
                     "cy": "🗓 <b>Ойма-ой:</b>"},
    "pay_line_paid":{"uz": "• {month}: {paid} so'm ✅",
                     "ru": "• {month}: {paid} сум ✅",
                     "cy": "• {month}: {paid} сўм ✅"},
    "pay_line_debt":{"uz": "• {month}: {paid}/{fee} — qarz {debt} ❌",
                     "ru": "• {month}: {paid}/{fee} — долг {debt} ❌",
                     "cy": "• {month}: {paid}/{fee} — қарз {debt} ❌"},
    "pay_last2":    {"uz": "Oxirgi to'lov: {last}",
                     "ru": "Последняя оплата: {last}",
                     "cy": "Охирги тўлов: {last}"},
    "pay_none":     {"uz": "To'lov yozuvlari topilmadi.",
                     "ru": "Записей об оплате нет.",
                     "cy": "Тўлов ёзувлари топилмади."},
    # ── Davomat — batafsil ──
    "att_title":    {"uz": "📊 <b>{name}</b> — davomat",
                     "ru": "📊 <b>{name}</b> — посещаемость",
                     "cy": "📊 <b>{name}</b> — давомат"},
    "att_rate":     {"uz": "So'nggi 30 kun: <b>{rate}%</b> ({present}/{total})",
                     "ru": "За 30 дней: <b>{rate}%</b> ({present}/{total})",
                     "cy": "Сўнгги 30 кун: <b>{rate}%</b> ({present}/{total})"},
    "att_recent_h": {"uz": "🗓 <b>So'nggi darslar:</b>",
                     "ru": "🗓 <b>Последние занятия:</b>",
                     "cy": "🗓 <b>Сўнгги дарслар:</b>"},
    "att_none":     {"uz": "Davomat yozuvlari topilmadi.",
                     "ru": "Записей о посещаемости нет.",
                     "cy": "Давомат ёзувлари топилмади."},
    "att_present":  {"uz": "Keldi", "ru": "Пришёл", "cy": "Келди"},
    "att_late":     {"uz": "Kech", "ru": "Опоздал", "cy": "Кеч"},
    "att_excused":  {"uz": "Sababli", "ru": "Ув. причина", "cy": "Сабабли"},
    "att_unexcused":{"uz": "Sababsiz", "ru": "Без причины", "cy": "Сабабсиз"},
    # Til tanlash (barcha tillar birga ko'rsatiladi)
    "pick_lang": {"uz": "👋 Assalomu alaykum! / Здравствуйте! / Ассалому алайкум!\n\n"
                        "Tilni tanlang / Выберите язык / Тилни танланг 👇",
                  "ru": "👋 Assalomu alaykum! / Здравствуйте! / Ассалому алайкум!\n\n"
                        "Tilni tanlang / Выберите язык / Тилни танланг 👇",
                  "cy": "👋 Assalomu alaykum! / Здравствуйте! / Ассалому алайкум!\n\n"
                        "Tilni tanlang / Выберите язык / Тилни танланг 👇"},
}


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    entry = M.get(key) or {}
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kw:
        try:
            text = text.format(**kw)
        except (KeyError, IndexError):
            pass
    return text


def b(key: str, lang: str = DEFAULT_LANG) -> str:
    entry = BTN.get(key) or {}
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key


def ik(key: str, lang: str = DEFAULT_LANG) -> str:
    entry = IKB.get(key) or {}
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key


def btn_variants(*keys: str) -> frozenset[str]:
    """Berilgan tugma kalitlarining barcha tildagi yozuvlari (filtr uchun)."""
    out: set[str] = set()
    for key in keys:
        for v in (BTN.get(key) or {}).values():
            out.add(v)
    return frozenset(out)


def btn_is(*keys: str):
    """Handler filtri: matn shu tugma(lar)ning istalgan tildagi yozuvimi."""
    return F.text.in_(btn_variants(*keys))


MONTHS: dict[int, dict[str, str]] = {
    1:  {"uz": "Yanvar",   "ru": "Январь",   "cy": "Январ"},
    2:  {"uz": "Fevral",   "ru": "Февраль",  "cy": "Феврал"},
    3:  {"uz": "Mart",     "ru": "Март",     "cy": "Март"},
    4:  {"uz": "Aprel",    "ru": "Апрель",   "cy": "Апрел"},
    5:  {"uz": "May",      "ru": "Май",      "cy": "Май"},
    6:  {"uz": "Iyun",     "ru": "Июнь",     "cy": "Июн"},
    7:  {"uz": "Iyul",     "ru": "Июль",     "cy": "Июл"},
    8:  {"uz": "Avgust",   "ru": "Август",   "cy": "Август"},
    9:  {"uz": "Sentabr",  "ru": "Сентябрь", "cy": "Сентабр"},
    10: {"uz": "Oktabr",   "ru": "Октябрь",  "cy": "Октабр"},
    11: {"uz": "Noyabr",   "ru": "Ноябрь",   "cy": "Ноябр"},
    12: {"uz": "Dekabr",   "ru": "Декабрь",  "cy": "Декабр"},
}


def month_name(num: int, year: int, lang: str = DEFAULT_LANG) -> str:
    mn = (MONTHS.get(int(num)) or {}).get(lang) or str(num)
    return f"{mn} {year}"


def att_status_label(status: str, lang: str = DEFAULT_LANG) -> str:
    key = {
        "present": "att_present",
        "late": "att_late",
        "absent_excused": "att_excused",
        "absent_unexcused": "att_unexcused",
    }.get(status or "", "att_unexcused")
    return t(key, lang)


def money(value) -> str:
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return str(value or 0)


def render_payment(payment: dict, lang: str, title: str) -> str:
    """To'lovlar — umumiy qarz + oyma-oy (batafsil)."""
    payment = payment or {}
    debt = int(payment.get("debt", 0) or 0)
    lines = [title, ""]
    lines.append(t("pay_no_debt", lang) if debt <= 0 else t("pay_total_debt", lang, debt=money(debt)))

    monthly = payment.get("monthly") or []
    if monthly:
        lines.append("")
        lines.append(t("pay_months_h", lang))
        for r in monthly:
            m = month_name(r.get("month", 1), r.get("year", ""), lang)
            if int(r.get("debt", 0) or 0) <= 0:
                lines.append(t("pay_line_paid", lang, month=m, paid=money(r.get("paid"))))
            else:
                lines.append(t("pay_line_debt", lang, month=m,
                              paid=money(r.get("paid")), fee=money(r.get("fee")), debt=money(r.get("debt"))))
    elif debt <= 0:
        pass
    else:
        lines.append(t("pay_none", lang))

    last = payment.get("last_payment_date") or "—"
    lines.append("")
    lines.append(t("pay_last2", lang, last=last))
    return "\n".join(lines)


def render_attendance(att: dict, lang: str, title: str, recent_limit: int = 12) -> str:
    """Davomat — 30 kunlik foiz + so'nggi darslar ro'yxati (batafsil)."""
    att = att or {}
    lines = [
        title, "",
        t("att_rate", lang, rate=att.get("recent_rate", 0),
          present=att.get("recent_present", 0), total=att.get("recent_total", 0)),
    ]
    items = att.get("items") or []
    if items:
        lines.append("")
        lines.append(t("att_recent_h", lang))
        for it in items[:recent_limit]:
            lines.append(f"• {it.get('date', '—')} — {att_status_label(it.get('status', ''), lang)}")
    else:
        lines.append("")
        lines.append(t("att_none", lang))
    return "\n".join(lines)


def lang_picker_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=IKB["lang_uz"]["uz"], callback_data="family:lang:uz")],
        [InlineKeyboardButton(text=IKB["lang_ru"]["ru"], callback_data="family:lang:ru")],
        [InlineKeyboardButton(text=IKB["lang_cy"]["cy"], callback_data="family:lang:cy")],
    ])
