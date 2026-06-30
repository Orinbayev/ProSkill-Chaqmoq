"""
English AI Teacher Bot — aiogram 3.x
• Curriculum-based lessons (A1→B2) — mavzuga qarab 15-26+ element
• Date navigation — istalgan sanaga o'tish
• A2/B1/B2 ga necha kun qolganligini ko'rish
• Chat orqali amaliyot — so'zni gapda ishlat, bot tekshiradi
• Test: barcha bugungi so'zlar — chatda saqlanib qoladi
"""
import asyncio
import json
import logging
import os
import random
from datetime import date, timedelta

import pytz
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import english_teacher.database as db
import english_teacher.teacher as ai
from english_teacher.curriculum import (
    get_topic_for_day,
    days_remaining_to_next_level,
    LEVEL_DAY_COUNT,
)

log = logging.getLogger(__name__)
router = Router()
TZ = pytz.timezone("Asia/Tashkent")
HTML = "HTML"

# In-memory sessions
_lesson: dict = {}   # {uid: {"items": [...], "idx": int, "lesson_date": str, "topic": dict}}
_test: dict = {}     # {uid: {"questions": [...], "idx": int, "score": int, "wrong": [], "lesson_date": str}}
_practice: dict = {}  # {uid: {"word": str, "awaiting": bool}} — chat amaliyot
_view_date: dict = {}  # {uid: "YYYY-MM-DD"}


# ── Date helpers ───────────────────────────────────────────────────────────────

MONTHS_UZ = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
              "Iyul", "Avgust", "Sentabr", "Oktyabr", "Noyabr", "Dekabr"]
MONTHS_SHORT = ["", "Yan", "Fev", "Mar", "Apr", "May", "Iyn",
                "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]


def _fmt(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.day} {MONTHS_UZ[dt.month]}"


def _day_num(user_id: int, lesson_date: str) -> int:
    start = db.get_user_start_date(user_id)
    return max(1, (date.fromisoformat(lesson_date) - date.fromisoformat(start)).days + 1)


def _view(user_id: int) -> str:
    return _view_date.get(user_id, date.today().isoformat())


def _next_date(d: str) -> str:
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def _prev_date(d: str) -> str:
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _bar(done: int, total: int, n: int = 10) -> str:
    f = round(n * done / total) if total else 0
    return "█" * f + "░" * (n - f)


def _menu_text(user: dict, stats: dict) -> str:
    level = user["level"]
    completed = db.get_completed_lesson_count(user["user_id"])
    remaining = days_remaining_to_next_level(level, completed)
    total = LEVEL_DAY_COUNT.get(level, 20)
    next_lvl = ai.next_level(level) or "🎓 B2 tamom!"
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya" if streak > 1 else "🌱 Seriyani boshlang!"

    return (
        f"🎓 <b>Ingliz tili o'qituvchingiz</b>\n"
        f"{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{level}</b>  →  {next_lvl}\n"
        f"{_bar(completed, total)}  <b>{completed}/{total} kun</b>\n"
        f"⏳  {next_lvl} ga: <b>{remaining} kun</b> qoldi\n\n"
        f"📚  O'rganilgan: <b>{stats['total_words']}</b> ta\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<i>Quyidagi tugmalardan birini bosing 👇</i>"
    )


def _item_text(idx: int, total: int, item: dict, lesson_date: str, user_id: int) -> str:
    day = _day_num(user_id, lesson_date)
    rule = f"\n📌  <b>{item['rule']}</b>" if item.get("rule") else ""
    return (
        f"📖 <b>Kun {day} · Element {idx}/{total}</b>  {_bar(idx, total)}\n"
        f"📅 {_fmt(lesson_date)}\n"
        f"{'─' * 28}\n\n"
        f"🔤  <b>{item['word'].upper()}</b>\n\n"
        f"🇺🇿  <b>{item['translation']}</b>\n\n"
        f"📝  <i>{item['definition']}</i>\n\n"
        f"💬  <code>{item['example']}</code>\n\n"
        f"💡  {item['memory_tip']}"
        f"{rule}"
    )


# ── Keyboards ──────────────────────────────────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖  Bugungi dars", callback_data="eng_today")],
        [
            InlineKeyboardButton(text="⏭  Keyingi kun", callback_data="eng_next_day"),
            InlineKeyboardButton(text="📅  Dars rejasi", callback_data="eng_plan"),
        ],
        [
            InlineKeyboardButton(text="📝  Test", callback_data="eng_test"),
            InlineKeyboardButton(text="🔁  Takrorlash", callback_data="eng_review"),
        ],
        [
            InlineKeyboardButton(text="📊  Statistikam", callback_data="eng_progress"),
            InlineKeyboardButton(text="📥  So'zlar (.txt)", callback_data="eng_export"),
        ],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
    ])


def kb_item(idx: int, total: int, word: str) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if idx > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data="eng_word_prev"))
    nav.append(InlineKeyboardButton(text=f"{idx}/{total}", callback_data="eng_noop"))
    if idx < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data="eng_word_next"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(
        text="💬  Gapda ishlat (amaliyot)",
        callback_data=f"eng_practice_{word[:30]}",
    )])
    if idx == total:
        rows.append([InlineKeyboardButton(text="✅  Darsni tugatdim!", callback_data="eng_word_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_test_opts(options: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"eng_ans_{opt[0]}")]
        for opt in options
    ])


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    u = msg.from_user
    db.create_user(u.id, u.username, u.first_name)
    user_data = db.get_user(u.id)
    stats = db.get_stats(u.id)
    await msg.answer(
        f"Salom, <b>{u.first_name}</b>! 👋\n\n" + _menu_text(user_data, stats),
        reply_markup=kb_main(),
        parse_mode=HTML,
    )


@router.callback_query(F.data == "eng_menu")
async def cb_menu(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    user_data = db.get_user(uid)
    stats = db.get_stats(uid)
    try:
        await cb.message.edit_text(_menu_text(user_data, stats), reply_markup=kb_main(), parse_mode=HTML)
    except Exception:
        await cb.message.answer(_menu_text(user_data, stats), reply_markup=kb_main(), parse_mode=HTML)


@router.callback_query(F.data == "eng_noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


# ── Lesson (curriculum-based, date-based) ─────────────────────────────────────

async def _open_lesson(cb: CallbackQuery, uid: int, lesson_date: str):
    existing = db.get_lesson_for_date(uid, lesson_date)
    day = _day_num(uid, lesson_date)
    user = db.get_user(uid)
    level = user["level"] if user else "A1"
    topic = get_topic_for_day(level, day)

    await cb.message.edit_text(
        f"⏳ <b>Dars tayyorlanmoqda...</b>\n"
        f"📅 {_fmt(lesson_date)} · Kun {day}"
        + (f"\n📚 Mavzu: <b>{topic['name_uz']}</b>" if topic else ""),
        parse_mode=HTML,
    )

    if existing:
        items = json.loads(existing["words_json"])
        intro = "Bu dars allaqachon o'rganilgan. Takrorlaymiz? 🔁"
        topic_uz = existing.get("topic_uz", "")
        topic_en = existing.get("topic_en", "")
    else:
        learned = db.get_learned_words(uid, limit=100)
        try:
            lesson = ai.generate_lesson(level, topic or {}, learned)
            items = lesson.get("items") or lesson.get("words", [])
            intro = lesson.get("intro", "")
            topic_uz = lesson.get("topic_uz", topic["name_uz"] if topic else "")
            topic_en = lesson.get("topic_en", topic["name_en"] if topic else "")
            db.save_lesson_for_date(uid, items, lesson_date, topic_uz, topic_en)
            if lesson_date == date.today().isoformat():
                db.update_streak(uid)
        except Exception as e:
            log.error("lesson generate error: %s", e)
            await cb.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=kb_back())
            return

    _lesson[uid] = {"items": items, "idx": 0, "lesson_date": lesson_date,
                    "topic": {"name_uz": topic_uz, "name_en": topic_en}}
    _view_date[uid] = lesson_date

    existing2 = db.get_lesson_for_date(uid, lesson_date)
    is_done = bool(existing2 and existing2.get("completed"))
    status = "✅ O'rganilgan" if is_done else "📖 O'rganilmoqda"
    next_d = _next_date(lesson_date)

    await cb.message.edit_text(
        f"{'─' * 28}\n"
        f"📅 <b>{_fmt(lesson_date)}</b> · Kun {day}  [{status}]\n"
        f"📚 <b>{topic_uz}</b>\n"
        f"{'─' * 28}\n\n"
        f"✨ {intro}\n\n"
        f"<i>Jami <b>{len(items)}</b> ta element. Bosing 👇</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖  Darsni boshlash", callback_data="eng_word_show")],
            [
                InlineKeyboardButton(text=f"◀️  {_fmt(_prev_date(lesson_date))}", callback_data=f"eng_goto_{_prev_date(lesson_date)}") if day > 1 else InlineKeyboardButton(text=" ", callback_data="eng_noop"),
                InlineKeyboardButton(text=f"{_fmt(next_d)}  ▶️", callback_data=f"eng_goto_{next_d}"),
            ],
            [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
        ]),
        parse_mode=HTML,
    )


@router.callback_query(F.data == "eng_today")
async def cb_today(cb: CallbackQuery):
    await cb.answer()
    await _open_lesson(cb, cb.from_user.id, date.today().isoformat())


@router.callback_query(F.data == "eng_next_day")
async def cb_next_day(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    next_d = db.get_next_lesson_date(uid)
    await _open_lesson(cb, uid, next_d)


@router.callback_query(F.data.startswith("eng_goto_"))
async def cb_goto(cb: CallbackQuery):
    await cb.answer()
    lesson_date = cb.data.replace("eng_goto_", "")
    await _open_lesson(cb, cb.from_user.id, lesson_date)


@router.callback_query(F.data == "eng_word_show")
async def cb_word_show(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    s = _lesson.get(uid)
    if not s:
        await cb.message.edit_text("Dars topilmadi.", reply_markup=kb_back())
        return
    items, idx, ld = s["items"], s["idx"], s["lesson_date"]
    await cb.message.edit_text(
        _item_text(idx + 1, len(items), items[idx], ld, uid),
        reply_markup=kb_item(idx + 1, len(items), items[idx]["word"]),
        parse_mode=HTML,
    )


@router.callback_query(F.data.in_({"eng_word_prev", "eng_word_next", "eng_word_done"}))
async def cb_word_nav(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    s = _lesson.get(uid)
    if not s:
        await cb.message.edit_text("Dars tugadi yoki topilmadi.", reply_markup=kb_back())
        return

    items, ld = s["items"], s["lesson_date"]
    if cb.data == "eng_word_next":
        s["idx"] = min(s["idx"] + 1, len(items) - 1)
    elif cb.data == "eng_word_prev":
        s["idx"] = max(s["idx"] - 1, 0)
    elif cb.data == "eng_word_done":
        _lesson.pop(uid, None)
        stats = db.get_stats(uid)
        next_d = _next_date(ld)
        day = _day_num(uid, ld)
        topic_name = s.get("topic", {}).get("name_uz", "")
        await cb.message.edit_text(
            f"🎉 <b>Kun {day} darsi tugadi!</b>\n"
            f"📚 {topic_name}\n\n"
            f"Bugun <b>{len(items)}</b> ta element o'rgandingiz!\n"
            f"Jami: <b>{stats['total_words']}</b> ta\n\n"
            f"Endi test qilib ko'ramizmi?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝  Test boshlash", callback_data="eng_test")],
                [InlineKeyboardButton(text=f"⏭  {_fmt(next_d)} darsi", callback_data=f"eng_goto_{next_d}")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    idx = s["idx"]
    await cb.message.edit_text(
        _item_text(idx + 1, len(items), items[idx], ld, uid),
        reply_markup=kb_item(idx + 1, len(items), items[idx]["word"]),
        parse_mode=HTML,
    )


# ── Chat amaliyot ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("eng_practice_"))
async def cb_practice(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    word = cb.data.replace("eng_practice_", "")
    _practice[uid] = {"word": word, "awaiting": True}
    await cb.message.answer(
        f"✏️ <b>Amaliyot!</b>\n\n"
        f"<b>'{word}'</b> so'zini ishlatib inglizcha gap yozing:\n\n"
        f"<i>(Masalan: 'I have a book on my desk.')</i>",
        parse_mode=HTML,
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat_practice(msg: Message):
    uid = msg.from_user.id
    practice = _practice.get(uid)

    if not practice or not practice.get("awaiting"):
        # Bot tegishli bo'lmagan xabarni e'tiborsiz qoldiradi
        return

    word = practice["word"]
    _practice.pop(uid, None)

    await msg.answer("🔍 Tekshirilmoqda...", parse_mode=HTML)
    try:
        result = ai.check_sentence(word, msg.text)
        if result.get("correct"):
            icon = "✅"
            text = f"{icon} <b>Zo'r!</b>\n\n{result.get('feedback', '')}"
        else:
            icon = "❌"
            corrected = result.get("corrected", "")
            text = f"{icon} <b>Xato.</b>\n\n{result.get('feedback', '')}"
            if corrected:
                text += f"\n\n✏️ To'g'ri variant:\n<code>{corrected}</code>"
        await msg.answer(text, parse_mode=HTML)
    except Exception as e:
        log.error("practice check error: %s", e)
        await msg.answer("❌ Tekshirishda xatolik. Qayta urinib ko'ring.")


# ── Test ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_test")
async def cb_test(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid in _test:
        await cb.answer("⚠️ Test davom etmoqda!", show_alert=True)
        return

    lesson_date = _view_date.get(uid, date.today().isoformat())
    lesson = db.get_lesson_for_date(uid, lesson_date)
    if not lesson:
        await cb.message.edit_text(
            f"❗ {_fmt(lesson_date)} uchun dars topilmadi. Avval darsni oling!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_today")]]),
        )
        return

    if lesson["completed"]:
        s = lesson["test_score"]
        total_q = json.loads(lesson["words_json"])
        total_q = len(total_q)
        await cb.message.edit_text(
            f"✅ <b>{_fmt(lesson_date)} testi topshirilgan!</b>\n\n"
            f"Natija: <b>{s}/{total_q}</b>  {_bar(round(s/total_q*100), 100)}  <b>{round(s/total_q*100)}%</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁  Takrorlash", callback_data="eng_review")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    items = json.loads(lesson["words_json"])
    topic_name = lesson.get("topic_uz", "")

    await cb.message.edit_text(
        f"⚡ <b>Test tayyorlanmoqda...</b>\n"
        f"📚 {topic_name}\n"
        f"🔢 {len(items)} ta savol...",
        parse_mode=HTML,
    )
    try:
        result = ai.generate_test(items, topic_name)
        _test[uid] = {
            "questions": result["questions"],
            "idx": 0, "score": 0, "wrong": [],
            "lesson_date": lesson_date,
            "total": len(result["questions"]),
        }
        await _send_q(cb.message, uid)
    except Exception as e:
        log.error("test error: %s", e)
        await cb.message.edit_text("❌ Test yaratishda xatolik.", reply_markup=kb_back())


async def _send_q(msg: Message, uid: int):
    s = _test.get(uid)
    if not s:
        return
    idx, qs = s["idx"], s["questions"]
    if idx >= len(qs):
        await _finish_test(msg, uid)
        return
    q = qs[idx]
    total = s["total"]
    text = (
        f"❓ <b>Savol {idx+1}/{total}</b>  {_bar(idx+1, total)}\n"
        f"{'─' * 28}\n\n{q['question']}"
    )
    await msg.answer(text, reply_markup=kb_test_opts(q["options"]), parse_mode=HTML)


@router.callback_query(F.data.startswith("eng_ans_"))
async def cb_answer(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    s = _test.get(uid)
    if not s:
        return
    idx = s["idx"]
    q = s["questions"][idx]
    chosen = cb.data.replace("eng_ans_", "")
    is_ok = chosen == q["correct"]
    word = q.get("word", "")

    db.record_word_result(uid, word, is_ok)
    if is_ok:
        s["score"] += 1
        icon, line = "✅", "✅ <b>To'g'ri!</b>"
    else:
        s["wrong"].append(word)
        icon, line = "❌", f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{q['correct']}</b>"

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        f"{icon} <b>Savol {idx+1}/{s['total']}</b>\n{'─'*28}\n\n{line}\n\n💡 {q.get('explanation','')}",
        parse_mode=HTML,
    )
    s["idx"] += 1
    await asyncio.sleep(0.5)
    if s["idx"] >= len(s["questions"]):
        await _finish_test(cb.message, uid)
    else:
        await _send_q(cb.message, uid)


async def _finish_test(msg: Message, uid: int):
    s = _test.pop(uid, {})
    score, wrong = s.get("score", 0), s.get("wrong", [])
    ld = s.get("lesson_date", date.today().isoformat())
    total = s.get("total", 5)
    pct = round(score / total * 100)

    db.save_test_result_for_date(uid, score, wrong, ld, total)
    user = db.get_user(uid)
    level = user["level"] if user else "A1"
    feedback = ai.get_feedback(score, total, level, wrong)

    emoji = "🌟" if pct == 100 else "🎯" if pct >= 80 else "💪" if pct >= 60 else "📖"
    day = _day_num(uid, ld)
    text = (
        f"{emoji} <b>Kun {day} testi yakunlandi!</b>\n"
        f"{'─'*28}\n\n"
        f"Natija: <b>{score}/{total}</b>  {_bar(pct, 100)}  <b>{pct}%</b>\n\n"
        f"{feedback}"
    )
    stats = db.get_stats(uid)
    if pct >= 80 and stats["total_words"] >= 50:
        nxt = ai.next_level(level)
        if nxt:
            completed = db.get_completed_lesson_count(uid)
            if completed >= 20:
                db.update_level(uid, nxt)
                text += f"\n\n🎉 <b>Tabriklayman! {nxt} darajasiga o'tdingiz!</b>"

    next_d = db.get_next_lesson_date(uid)
    buttons = []
    if wrong:
        buttons.append([InlineKeyboardButton(text="🔁  Xato so'zlarni mashq qil", callback_data="eng_review")])
    buttons.append([InlineKeyboardButton(text=f"⏭  {_fmt(next_d)} darsi", callback_data=f"eng_goto_{next_d}")])
    buttons.append([InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")])
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=HTML)


# ── Review ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_review")
async def cb_review(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    if uid in _test:
        await cb.answer("⚠️ Avval joriy testni tugatib oling!", show_alert=True)
        return
    words = db.get_words_for_review(uid, limit=15)
    if not words:
        await cb.message.edit_text(
            "📭 Hali tekshiriladigan so'zlar yo'q.\nAvval bir nechta dars o'ting!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_today")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
        )
        return
    await cb.message.edit_text(
        f"🔁 <b>Takrorlash</b> — eng ko'p xato qilingan <b>{len(words)}</b> ta element...",
        parse_mode=HTML,
    )
    try:
        result = ai.generate_test(words)
        _test[uid] = {
            "questions": result["questions"],
            "idx": 0, "score": 0, "wrong": [],
            "lesson_date": date.today().isoformat(),
            "total": len(result["questions"]),
        }
        await _send_q(cb.message, uid)
    except Exception as e:
        log.error("review error: %s", e)
        await cb.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=kb_back())


# ── Plan ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_plan")
async def cb_plan(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    user = db.get_user(uid)
    level = user["level"] if user else "A1"
    start_str = db.get_user_start_date(uid)
    start = date.fromisoformat(start_str)
    done_dates = {r["lesson_date"] for r in db.get_all_lesson_dates(uid)}
    today = date.today()

    from english_teacher.curriculum import ALL_CURRICULUM

    lines = [f"📅 <b>Dars rejasi — {level} darajasi</b>\n"]
    curriculum = ALL_CURRICULUM.get(level, [])
    total_days = len(curriculum)
    completed = db.get_completed_lesson_count(uid)

    for i, (day_n, name_uz, name_en, min_items, _) in enumerate(curriculum):
        lesson_date = (start + timedelta(days=i)).isoformat()
        dt = date.fromisoformat(lesson_date)
        date_str = f"{dt.day:2d} {MONTHS_SHORT[dt.month]}"

        if lesson_date in done_dates:
            icon = "✅"
        elif lesson_date == today.isoformat():
            icon = "📖"
        elif dt < today:
            icon = "⏩"
        else:
            icon = "⏳"

        lines.append(f"{icon} <b>Kun {day_n:2d}</b> · {date_str} — {name_uz}")

    # Level transition dates
    level_order = ["A1", "A2", "B1", "B2"]
    day_offset = 0
    lines.append(f"\n{'─'*28}")
    for lvl in level_order:
        n = LEVEL_DAY_COUNT.get(lvl, 20)
        d = start + timedelta(days=day_offset + n - 1)
        lines.append(f"🎯 <b>{lvl}</b> tugash: {d.day} {MONTHS_SHORT[d.month]} {d.year}")
        day_offset += n

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await cb.message.edit_text(text, reply_markup=kb_back(), parse_mode=HTML)


# ── Progress ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_progress")
async def cb_progress(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    user = db.get_user(uid)
    if not user:
        await cb.message.edit_text("Iltimos /start bosing.")
        return
    stats = db.get_stats(uid)
    level = user["level"]
    completed = db.get_completed_lesson_count(uid)
    total_days = LEVEL_DAY_COUNT.get(level, 20)
    remaining = days_remaining_to_next_level(level, completed)
    next_lvl = ai.next_level(level) or "🎓 B2 tamom!"
    pct = min(100, round(completed / total_days * 100))
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya!" if streak > 1 else "🌱 Seriyani boshlang!"

    await cb.message.edit_text(
        f"📊 <b>Sizning statistikangiz</b>\n{'─'*28}\n\n"
        f"🏆  Daraja: <b>{level}</b>  →  {next_lvl}\n"
        f"{_bar(pct, 100)}  <b>{pct}%</b>  ({completed}/{total_days} kun)\n"
        f"⏳  {next_lvl} ga: <b>{remaining} kun</b> qoldi\n\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"✅  Yakunlangan darslar: <b>{stats['done_lessons']}</b>\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}",
        reply_markup=kb_back(),
        parse_mode=HTML,
    )


# ── Export ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_export")
async def cb_export(cb: CallbackQuery):
    await cb.answer()
    uid = cb.from_user.id
    words = db.get_all_words_for_export(uid)
    if not words:
        await cb.message.edit_text("📭 Hali o'rganilgan so'zlar yo'q.", reply_markup=kb_back())
        return
    await cb.message.edit_text("⏳ Fayl tayyorlanmoqda...", parse_mode=HTML)
    lines = ["INGLIZCHA SO'ZLAR RO'YXATI", f"Jami: {len(words)} ta so'z", "=" * 40, ""]
    cur_date = ""
    for w in words:
        if w["date_added"] != cur_date:
            cur_date = w["date_added"]
            lines += ["", f"📅 {_fmt(cur_date)}", "─" * 30]
        lines += [f"  {w['word'].upper()}", f"     🇺🇿  {w['translation']}", f"     💬  {w['example']}", ""]
    doc = BufferedInputFile("\n".join(lines).encode("utf-8"), filename="ingliz_sozlar.txt")
    await cb.message.answer_document(
        doc,
        caption=f"📥 <b>Barcha so'zlar</b> — {len(words)} ta\nFormat: inglizcha → tarjima + misol",
        parse_mode=HTML,
    )
    user_data = db.get_user(uid)
    stats = db.get_stats(uid)
    await cb.message.edit_text(_menu_text(user_data, stats), reply_markup=kb_main(), parse_mode=HTML)


# ── Scheduled ─────────────────────────────────────────────────────────────────

async def _morning_job(bot: Bot):
    for user in db.get_all_users():
        uid = user["user_id"]
        try:
            if db.get_today_lesson(uid):
                continue
            today = date.today().isoformat()
            day = _day_num(uid, today)
            level = user["level"]
            topic = get_topic_for_day(level, day)
            learned = db.get_learned_words(uid, limit=100)
            lesson = ai.generate_lesson(level, topic or {}, learned)
            items = lesson.get("items") or lesson.get("words", [])
            topic_uz = lesson.get("topic_uz", topic["name_uz"] if topic else "")
            topic_en = lesson.get("topic_en", topic["name_en"] if topic else "")
            db.save_lesson_for_date(uid, items, today, topic_uz, topic_en)
            db.update_streak(uid)
            _lesson[uid] = {"items": items, "idx": 0, "lesson_date": today,
                            "topic": {"name_uz": topic_uz}}
            _view_date[uid] = today
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"🌅 <b>Xayrli tong!</b>\n\n"
                    f"📚 Bugungi mavzu: <b>{topic_uz}</b>\n"
                    f"🔢 {len(items)} ta element\n\n"
                    f"✨ {lesson.get('intro', '')}"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📖  Darsni boshlash", callback_data="eng_today")],
                ]),
                parse_mode=HTML,
            )
        except Exception as e:
            log.error("morning uid=%s: %s", uid, e)


async def _evening_job(bot: Bot):
    for user in db.get_all_users():
        uid = user["user_id"]
        try:
            lesson = db.get_today_lesson(uid)
            if lesson and not lesson["completed"]:
                total = len(json.loads(lesson["words_json"]))
                await bot.send_message(
                    chat_id=uid,
                    text=f"🌙 <b>Test vaqti!</b>\n\n{total} ta savol tayyor 💪",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝  Testni boshlash", callback_data="eng_test")],
                    ]),
                    parse_mode=HTML,
                )
        except Exception as e:
            log.error("evening uid=%s: %s", uid, e)


# ── Entry point ────────────────────────────────────────────────────────────────

async def english_bot_polling():
    token = os.getenv("ENGLISH_BOT_TOKEN")
    if not token:
        log.info("ENGLISH_BOT_TOKEN topilmadi — English Teacher bot o'chirildi.")
        return

    db.init_db()
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(_morning_job, "cron", hour=9, minute=0, args=[bot])
    scheduler.add_job(_evening_job, "cron", hour=21, minute=0, args=[bot])
    scheduler.start()

    log.info("📚 English Teacher Bot ishga tushdi!")
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
        except Exception as err:
            log.error("English Teacher Bot error: %s", err)
            await asyncio.sleep(10)
