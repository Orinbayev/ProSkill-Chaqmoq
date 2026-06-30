"""
English AI Teacher Bot — aiogram 3.x
Faqat /start buyrug'i; qolgan hamma narsa inline tugmalar bilan.
Xususiyatlar:
  • Sanaga asoslangan darslar — istalgan sanani o'rganish mumkin
  • ◀️ Oldingi kun / Keyingi kun ▶️ navigatsiya
  • Dars rejasi: A1→B2 gacha har kun sanasi bilan
  • So'zlar eksporti — .txt fayl sifatida yuborish
  • Barcha test natijalari botda saqlanib qoladi
"""
import asyncio
import io
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

log = logging.getLogger(__name__)
router = Router()
TZ = pytz.timezone("Asia/Tashkent")
HTML = "HTML"

# In-memory sessions
_lesson: dict = {}   # {user_id: {"words": [...], "idx": int, "lesson_date": str}}
_test: dict = {}     # {user_id: {"questions": [...], "idx": int, "score": int,
#                                   "wrong": [], "lesson_date": str}}
_view_date: dict = {}  # {user_id: "YYYY-MM-DD"} — qaysi sanani ko'rmoqda


# ── Date helpers ───────────────────────────────────────────────────────────────

def _fmt_date(d: str) -> str:
    """2026-07-05 → 5 Iyul 2026"""
    months = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
              "Iyul", "Avgust", "Sentabr", "Oktyabr", "Noyabr", "Dekabr"]
    dt = date.fromisoformat(d)
    return f"{dt.day} {months[dt.month]} {dt.year}"


def _day_number(user_id: int, lesson_date: str) -> int:
    """Bu sana necha-kunlik dars (1, 2, 3...)"""
    start = db.get_user_start_date(user_id)
    delta = (date.fromisoformat(lesson_date) - date.fromisoformat(start)).days + 1
    return max(1, delta)


def _current_view_date(user_id: int) -> str:
    """Foydalanuvchi hozir qaysi sanani ko'rmoqda."""
    return _view_date.get(user_id, date.today().isoformat())


def _advance_date(d: str, days: int = 1) -> str:
    return (date.fromisoformat(d) + timedelta(days=days)).isoformat()


def _retreat_date(d: str, days: int = 1) -> str:
    return (date.fromisoformat(d) - timedelta(days=days)).isoformat()


# ── Curriculum plan ────────────────────────────────────────────────────────────

LEVEL_DAYS = {"A1": 20, "A2": 40, "B1": 60, "B2": 80}  # har darajada kunlar soni

def _build_plan(user_id: int) -> str:
    start_str = db.get_user_start_date(user_id)
    start = date.fromisoformat(start_str)
    done_dates = {r["lesson_date"] for r in db.get_all_lesson_dates(user_id)}
    today = date.today()

    months = ["", "Yan", "Fev", "Mar", "Apr", "May", "Iyn",
              "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]

    lines = ["📅 <b>Dars rejasi — A1 dan B2 gacha</b>\n"]

    day = 0
    for level, n_days in LEVEL_DAYS.items():
        level_start = start + timedelta(days=day)
        level_end = start + timedelta(days=day + n_days - 1)
        lines.append(
            f"\n<b>{level} daraja</b> "
            f"({level_start.day} {months[level_start.month]} — "
            f"{level_end.day} {months[level_end.month]} {level_end.year})"
        )
        lines.append(f"{'─' * 28}")

        for i in range(n_days):
            lesson_date = (start + timedelta(days=day + i)).isoformat()
            dt = date.fromisoformat(lesson_date)
            day_num = day + i + 1
            date_str = f"{dt.day:2d} {months[dt.month]}"

            if lesson_date in done_dates:
                icon = "✅"
            elif lesson_date == today.isoformat():
                icon = "📖"
            elif dt < today:
                icon = "⏩"  # o'tib ketgan, o'rganilmagan
            else:
                icon = "⏳"

            lines.append(f"{icon} Kun {day_num:3d} — {date_str}")

        day += n_days

    total_days = sum(LEVEL_DAYS.values())
    finish = start + timedelta(days=total_days - 1)
    lines.append(
        f"\n{'─' * 28}\n"
        f"🎓 <b>B2 tugash:</b> {finish.day} {months[finish.month]} {finish.year}\n"
        f"📊 Jami: <b>{total_days} kun</b> / <b>{total_days * 5} so'z</b>"
    )
    return "\n".join(lines)


# ── Keyboards ──────────────────────────────────────────────────────────────────

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖  Bugungi dars", callback_data="eng_today")],
        [
            InlineKeyboardButton(text="⏭  Keyingi kun dars", callback_data="eng_next_day"),
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


def kb_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
    ])


def kb_lesson_nav(lesson_date: str, user_id: int) -> InlineKeyboardMarkup:
    start = db.get_user_start_date(user_id)
    can_go_back = date.fromisoformat(lesson_date) > date.fromisoformat(start)
    prev_date = _retreat_date(lesson_date)
    next_date = _advance_date(lesson_date)
    rows = []
    nav = []
    if can_go_back:
        nav.append(InlineKeyboardButton(
            text=f"◀️  {_fmt_date(prev_date)}",
            callback_data=f"eng_goto_{prev_date}",
        ))
    nav.append(InlineKeyboardButton(
        text=f"{_fmt_date(next_date)}  ▶️",
        callback_data=f"eng_goto_{next_date}",
    ))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="📖  Darsni boshlash", callback_data="eng_word_show")])
    rows.append([InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_word(idx: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if idx > 1:
        nav.append(InlineKeyboardButton(text="◀️  Oldingi", callback_data="eng_word_prev"))
    if idx < total:
        nav.append(InlineKeyboardButton(text="Keyingi  ▶️", callback_data="eng_word_next"))
    if nav:
        rows.append(nav)
    if idx == total:
        rows.append([InlineKeyboardButton(text="✅  Darsni tugatdim!", callback_data="eng_word_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_test_options(options: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"eng_ans_{opt[0]}")]
        for opt in options
    ])


# ── UI text helpers ────────────────────────────────────────────────────────────

def _bar(done: int, total: int, n: int = 8) -> str:
    filled = round(n * done / total) if total else 0
    return "█" * filled + "░" * (n - filled)


def _menu_text(user: dict, stats: dict) -> str:
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya" if streak > 1 else "🌱 Seriyani boshlang!"
    return (
        f"🎓 <b>Ingliz tili o'qituvchingiz</b>\n"
        f"{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{user['level']}</b>\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<i>Quyidagi tugmalardan birini bosing 👇</i>"
    )


def _word_text(idx: int, total: int, w: dict, lesson_date: str, user_id: int) -> str:
    day_num = _day_number(user_id, lesson_date)
    return (
        f"📖 <b>Kun {day_num} · So'z {idx}/{total}</b>  {_bar(idx, total)}\n"
        f"📅 {_fmt_date(lesson_date)}\n"
        f"{'─' * 28}\n\n"
        f"🔤  <b>{w['word'].upper()}</b>\n\n"
        f"🇺🇿  <b>{w['translation']}</b>\n\n"
        f"📝  <i>{w['definition']}</i>\n\n"
        f"💬  <code>{w['example']}</code>\n\n"
        f"💡  {w['memory_tip']}"
    )


def _lesson_header(lesson_date: str, user_id: int, intro: str, done: bool = False) -> str:
    day_num = _day_number(user_id, lesson_date)
    status = "✅ O'rganilgan" if done else "📖 O'rganilmoqda"
    return (
        f"{'─' * 28}\n"
        f"📅 <b>{_fmt_date(lesson_date)}</b>  —  Kun {day_num}  [{status}]\n"
        f"{'─' * 28}\n\n"
        f"✨ {intro}"
    )


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    u = msg.from_user
    db.create_user(u.id, u.username, u.first_name)
    user_data = db.get_user(u.id)
    stats = db.get_stats(u.id)
    await msg.answer(
        f"Salom, <b>{u.first_name}</b>! 👋\n\n" + _menu_text(user_data, stats),
        reply_markup=kb_main_menu(),
        parse_mode=HTML,
    )


@router.callback_query(F.data == "eng_menu")
async def cb_menu(cb: CallbackQuery):
    await cb.answer()
    user_data = db.get_user(cb.from_user.id)
    stats = db.get_stats(cb.from_user.id)
    if not user_data:
        await cb.message.answer("Iltimos /start bosing.")
        return
    try:
        await cb.message.edit_text(
            _menu_text(user_data, stats),
            reply_markup=kb_main_menu(),
            parse_mode=HTML,
        )
    except Exception:
        await cb.message.answer(
            _menu_text(user_data, stats),
            reply_markup=kb_main_menu(),
            parse_mode=HTML,
        )


# ── Lesson (date-based) ────────────────────────────────────────────────────────

async def _open_lesson(target, user_id: int, lesson_date: str):
    """Show lesson for the given date (send or edit message)."""
    existing = db.get_lesson_for_date(user_id, lesson_date)

    send = target.answer if isinstance(target, Message) else target.message.answer
    edit = None if isinstance(target, Message) else target.message.edit_text

    header_text = (
        f"⏳ <b>Dars tayyorlanmoqda...</b>\n"
        f"📅 {_fmt_date(lesson_date)}"
    )
    if edit:
        await edit(header_text, parse_mode=HTML)
    else:
        await send(header_text, parse_mode=HTML)

    if existing:
        words = json.loads(existing["words_json"])
        is_done = bool(existing["completed"])
        intro = "Bu dars allaqachon o'rganilgan. Takrorlaymiz? 🔁" if is_done else "Davom etamiz 📖"
    else:
        user = db.get_user(user_id)
        level = user["level"] if user else "A1"
        learned = db.get_learned_words(user_id)
        try:
            lesson = ai.generate_lesson(level, learned)
            words = lesson["words"]
            intro = lesson.get("intro", "")
            db.save_lesson_for_date(user_id, words, lesson_date)
            if lesson_date == date.today().isoformat():
                db.update_streak(user_id)
        except Exception as e:
            log.error("lesson generate error: %s", e)
            await send("❌ Xatolik yuz berdi. Qayta urinib ko'ring.", reply_markup=kb_back_menu())
            return

    is_done = bool(db.get_lesson_for_date(user_id, lesson_date).get("completed", 0))
    _lesson[user_id] = {"words": words, "idx": 0, "lesson_date": lesson_date}
    _view_date[user_id] = lesson_date

    await send(
        _lesson_header(lesson_date, user_id, intro, is_done),
        reply_markup=kb_lesson_nav(lesson_date, user_id),
        parse_mode=HTML,
    )


@router.callback_query(F.data == "eng_today")
async def cb_today(cb: CallbackQuery):
    await cb.answer()
    await _open_lesson(cb, cb.from_user.id, date.today().isoformat())


@router.callback_query(F.data == "eng_next_day")
async def cb_next_day(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    next_date = db.get_next_lesson_date(user_id)
    await _open_lesson(cb, user_id, next_date)


@router.callback_query(F.data.startswith("eng_goto_"))
async def cb_goto_date(cb: CallbackQuery):
    await cb.answer()
    lesson_date = cb.data.replace("eng_goto_", "")
    await _open_lesson(cb, cb.from_user.id, lesson_date)


@router.callback_query(F.data == "eng_word_show")
async def cb_word_show(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    session = _lesson.get(user_id)
    if not session:
        await cb.message.edit_text("Dars topilmadi.", reply_markup=kb_back_menu())
        return
    words = session["words"]
    idx = session["idx"]
    lesson_date = session["lesson_date"]
    await cb.message.edit_text(
        _word_text(idx + 1, len(words), words[idx], lesson_date, user_id),
        reply_markup=kb_word(idx + 1, len(words)),
        parse_mode=HTML,
    )


@router.callback_query(F.data.in_({"eng_word_prev", "eng_word_next", "eng_word_done"}))
async def cb_word_nav(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    session = _lesson.get(user_id)
    if not session:
        await cb.message.edit_text("Dars tugadi yoki topilmadi.", reply_markup=kb_back_menu())
        return

    words = session["words"]
    lesson_date = session["lesson_date"]

    if cb.data == "eng_word_next":
        session["idx"] = min(session["idx"] + 1, len(words) - 1)
    elif cb.data == "eng_word_prev":
        session["idx"] = max(session["idx"] - 1, 0)
    elif cb.data == "eng_word_done":
        _lesson.pop(user_id, None)
        stats = db.get_stats(user_id)
        next_date = _advance_date(lesson_date)
        day_num = _day_number(user_id, lesson_date)
        await cb.message.edit_text(
            f"🎉 <b>Kun {day_num} darsi tugadi!</b>\n"
            f"📅 {_fmt_date(lesson_date)}\n\n"
            f"Bugun <b>5 ta</b> yangi so'z o'rgandingiz!\n"
            f"Jami: <b>{stats['total_words']}</b> ta so'z 📚\n\n"
            f"Keyingi kun: <b>{_fmt_date(next_date)}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝  Test boshlash", callback_data="eng_test")],
                [InlineKeyboardButton(
                    text=f"⏭  {_fmt_date(next_date)} darsi",
                    callback_data=f"eng_goto_{next_date}",
                )],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    idx = session["idx"]
    await cb.message.edit_text(
        _word_text(idx + 1, len(words), words[idx], lesson_date, user_id),
        reply_markup=kb_word(idx + 1, len(words)),
        parse_mode=HTML,
    )


# ── Test ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_test")
async def cb_test(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id

    if user_id in _test:
        await cb.answer("⚠️ Test davom etmoqda!", show_alert=True)
        return

    # Test qaysi kundagi so'zlar uchun?
    lesson_date = _view_date.get(user_id, date.today().isoformat())
    lesson = db.get_lesson_for_date(user_id, lesson_date)

    if not lesson:
        await cb.message.edit_text(
            f"❗ {_fmt_date(lesson_date)} sanasi uchun dars topilmadi.\n\nAvval darsni oling!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_today")],
            ]),
        )
        return

    if lesson["completed"]:
        s = lesson["test_score"]
        await cb.message.edit_text(
            f"✅ <b>{_fmt_date(lesson_date)} testi topshirilgan!</b>\n\n"
            f"Natija: <b>{s}/5</b>  {_bar(s * 20, 100)}  <b>{s * 20}%</b>\n\n"
            f"Eski so'zlarni mashq qilish: 🔁",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁  Takrorlash", callback_data="eng_review")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    await cb.message.edit_text(
        f"⚡ <b>{_fmt_date(lesson_date)} uchun test tayyorlanmoqda...</b>\n"
        f"Bugungi + eski so'zlardan savollar...",
        parse_mode=HTML,
    )

    today_words = json.loads(lesson["words_json"])
    old_pool = [w for w in db.get_learned_words(user_id, limit=80)
                if w not in {x["word"].lower() for x in today_words}]
    test_words = list(today_words)
    if len(old_pool) >= 3:
        sample = random.sample(old_pool, min(2, len(old_pool)))
        old_dicts = db.get_words_by_list(user_id, sample)
        test_words = test_words[:3] + old_dicts[:2]
    random.shuffle(test_words)

    try:
        result = ai.generate_test(test_words)
        _test[user_id] = {
            "questions": result["questions"],
            "idx": 0, "score": 0, "wrong": [],
            "lesson_date": lesson_date,
        }
        await _show_question(cb.message, user_id)
    except Exception as e:
        log.error("test error: %s", e)
        await cb.message.edit_text("❌ Test yaratishda xatolik. Qayta urinib ko'ring.", reply_markup=kb_back_menu())


async def _show_question(msg: Message, user_id: int):
    session = _test.get(user_id)
    if not session:
        return
    idx = session["idx"]
    qs = session["questions"]
    if idx >= len(qs):
        await _finish_test(msg, user_id)
        return
    q = qs[idx]
    total = len(qs)
    text = (
        f"❓ <b>Savol {idx+1}/{total}</b>  {_bar(idx+1, total)}\n"
        f"{'─' * 28}\n\n{q['question']}"
    )
    # Always send as NEW message so previous questions stay visible in chat
    await msg.answer(text, reply_markup=kb_test_options(q["options"]), parse_mode=HTML)


@router.callback_query(F.data.startswith("eng_ans_"))
async def cb_answer(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    session = _test.get(user_id)
    if not session:
        return

    idx = session["idx"]
    q = session["questions"][idx]
    chosen = cb.data.replace("eng_ans_", "")
    is_ok = chosen == q["correct"]
    word = q.get("word", "")

    db.record_word_result(user_id, word, is_ok)
    if is_ok:
        session["score"] += 1
        icon, result_line = "✅", "✅ <b>To'g'ri!</b>"
    else:
        session["wrong"].append(word)
        icon, result_line = "❌", f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{q['correct']}</b>"

    total = len(session["questions"])

    # Remove buttons from the question (keeps question text visible)
    await cb.message.edit_reply_markup(reply_markup=None)

    # Send result as a NEW message — stays in chat history
    await cb.message.answer(
        f"{icon} <b>Savol {idx+1}/{total}</b>\n{'─'*28}\n\n"
        f"{result_line}\n\n💡 {q.get('explanation', '')}",
        parse_mode=HTML,
    )
    session["idx"] += 1
    await asyncio.sleep(0.5)

    # Next question or finish — always new messages
    if session["idx"] >= total:
        await _finish_test(cb.message, user_id)
    else:
        await _show_question(cb.message, user_id)


async def _finish_test(msg: Message, user_id: int):
    session = _test.pop(user_id, {})
    score = session.get("score", 0)
    wrong = session.get("wrong", [])
    lesson_date = session.get("lesson_date", date.today().isoformat())
    pct = score * 20

    db.save_test_result_for_date(user_id, score, wrong, lesson_date)

    user = db.get_user(user_id)
    level = user["level"] if user else "A1"
    feedback = ai.get_feedback(score, 5, level, wrong)

    emoji = "🌟" if pct == 100 else "🎯" if pct >= 80 else "💪" if pct >= 60 else "📖"
    day_num = _day_number(user_id, lesson_date)

    text = (
        f"{emoji} <b>Kun {day_num} testi yakunlandi!</b>\n"
        f"📅 {_fmt_date(lesson_date)}\n"
        f"{'─' * 28}\n\n"
        f"Natija: <b>{score}/5</b>  {_bar(pct, 100, 10)}  <b>{pct}%</b>\n\n"
        f"{feedback}"
    )

    stats = db.get_stats(user_id)
    if pct >= 80 and stats["total_words"] >= 100:
        nxt = ai.next_level(level)
        if nxt:
            db.update_level(user_id, nxt)
            text += f"\n\n🎉 <b>Tabriklayman! {nxt} darajasiga o'tdingiz!</b>"

    next_lesson_date = db.get_next_lesson_date(user_id)
    buttons = []
    if wrong:
        buttons.append([InlineKeyboardButton(text="🔁  Xato so'zlarni mashq qil", callback_data="eng_review")])
    buttons.append([InlineKeyboardButton(
        text=f"⏭  {_fmt_date(next_lesson_date)} darsi",
        callback_data=f"eng_goto_{next_lesson_date}",
    )])
    buttons.append([InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")])
    # Send final result as NEW message — stays in chat
    await msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=HTML)


# ── Review ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_review")
async def cb_review(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    if user_id in _test:
        await cb.answer("⚠️ Avval joriy testni tugatib oling!", show_alert=True)
        return

    words = db.get_words_for_review(user_id, limit=5)
    if not words:
        await cb.message.edit_text(
            "📭 <b>Hali tekshiriladigan so'zlar yo'q.</b>\n\n"
            "Avval bir nechta dars o'ting!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_today")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    await cb.message.edit_text(
        f"🔁 <b>Takrorlash sessiyasi</b>\n\n"
        f"Eng ko'p xato qilingan <b>{len(words)}</b> ta so'z...\n"
        f"⚡ Savollar tayyorlanmoqda...",
        parse_mode=HTML,
    )
    try:
        result = ai.generate_test(words)
        _test[user_id] = {
            "questions": result["questions"][: len(words)],
            "idx": 0, "score": 0, "wrong": [],
            "lesson_date": date.today().isoformat(),
        }
        await _show_question(cb.message, user_id)
    except Exception as e:
        log.error("review error: %s", e)
        await cb.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=kb_back_menu())


# ── Plan ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_plan")
async def cb_plan(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("⏳ Reja tayyorlanmoqda...", parse_mode=HTML)
    user_id = cb.from_user.id
    plan_text = _build_plan(user_id)
    # Telegram message limit is 4096 chars; split if needed
    if len(plan_text) > 4000:
        plan_text = plan_text[:4000] + "\n..."
    await cb.message.edit_text(
        plan_text,
        reply_markup=kb_back_menu(),
        parse_mode=HTML,
    )


# ── Progress ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_progress")
async def cb_progress(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    user = db.get_user(user_id)
    if not user:
        await cb.message.edit_text("Iltimos /start bosing.")
        return

    stats = db.get_stats(user_id)
    level = user["level"]
    targets = {"A1": 100, "A2": 300, "B1": 600, "B2": 1000}
    target = targets.get(level, 100)
    pct_lvl = min(100, round(stats["total_words"] / target * 100))
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya!" if streak > 1 else "🌱 Seriyani boshlang!"

    cefr = {"A1": "A1 ░░░░░░░ A2 → B1 → B2",
            "A2": "A1 ✅ A2 ░░░░ B1 → B2",
            "B1": "A1 ✅ A2 ✅ B1 ░░ B2",
            "B2": "A1 ✅ A2 ✅ B1 ✅ B2 ░"}

    await cb.message.edit_text(
        f"📊 <b>Sizning statistikangiz</b>\n{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{level}</b>\n"
        f"<code>{cefr.get(level, '')}</code>\n\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"✅  Yakunlangan darslar: <b>{stats['done_lessons']}</b>\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<b>Keyingi darajaga:</b>\n"
        f"{_bar(pct_lvl, 100, 10)}  <b>{pct_lvl}%</b>  ({stats['total_words']}/{target} so'z)",
        reply_markup=kb_back_menu(),
        parse_mode=HTML,
    )


# ── Export ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_export")
async def cb_export(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    words = db.get_all_words_for_export(user_id)

    if not words:
        await cb.message.edit_text(
            "📭 Hali o'rganilgan so'zlar yo'q.\n\nAvval dars oling: 📖",
            reply_markup=kb_back_menu(),
        )
        return

    await cb.message.edit_text("⏳ Fayl tayyorlanmoqda...", parse_mode=HTML)

    lines = [
        "INGLIZCHA SO'ZLAR RO'YXATI",
        f"Jami: {len(words)} ta so'z",
        "=" * 40,
        "",
    ]
    current_date = ""
    for w in words:
        if w["date_added"] != current_date:
            current_date = w["date_added"]
            lines.append(f"\n📅 {_fmt_date(current_date)}")
            lines.append("─" * 30)
        lines.append(f"  {w['word'].upper()}")
        lines.append(f"     🇺🇿  {w['translation']}")
        lines.append(f"     💬  {w['example']}")
        lines.append("")

    content = "\n".join(lines)
    file_bytes = content.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename="ingliz_sozlar.txt")

    await cb.message.answer_document(
        doc,
        caption=(
            f"📥 <b>Barcha o'rganilgan so'zlar</b>\n\n"
            f"📚 Jami: <b>{len(words)}</b> ta so'z\n"
            f"📄 Format: inglizcha → o'zbekcha + misol gap"
        ),
        parse_mode=HTML,
    )
    user_data = db.get_user(user_id)
    stats = db.get_stats(user_id)
    await cb.message.edit_text(
        _menu_text(user_data, stats),
        reply_markup=kb_main_menu(),
        parse_mode=HTML,
    )


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

async def _morning_job(bot: Bot):
    for user in db.get_all_users():
        uid = user["user_id"]
        try:
            if db.get_today_lesson(uid):
                continue
            learned = db.get_learned_words(uid)
            lesson = ai.generate_lesson(user["level"], learned)
            today = date.today().isoformat()
            db.save_lesson_for_date(uid, lesson["words"], today)
            db.update_streak(uid)
            _lesson[uid] = {"words": lesson["words"], "idx": 0, "lesson_date": today}
            _view_date[uid] = today
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"🌅 <b>Xayrli tong!</b>\n\n"
                    f"✨ {lesson.get('intro', 'Bugungi dars tayyor!')}"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📖  Darsni boshlash", callback_data="eng_today")],
                ]),
                parse_mode=HTML,
            )
        except Exception as e:
            log.error("morning job uid=%s: %s", uid, e)


async def _evening_job(bot: Bot):
    for user in db.get_all_users():
        uid = user["user_id"]
        try:
            lesson = db.get_today_lesson(uid)
            if lesson and not lesson["completed"]:
                await bot.send_message(
                    chat_id=uid,
                    text="🌙 <b>Test vaqti!</b>\n\nBugungi so'zlarni sinab ko'rish vaqti 💪",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝  Testni boshlash", callback_data="eng_test")],
                    ]),
                    parse_mode=HTML,
                )
        except Exception as e:
            log.error("evening job uid=%s: %s", uid, e)


# ── Entry point ─────────────────────────────────────────────────────────────────

async def english_bot_polling():
    """Called from telegram_bot/bot.py — runs as 3rd parallel task."""
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
