"""
English AI Teacher Bot — aiogram 3.x
Faqat /start buyrug'i; qolgan hamma narsa inline tugmalar bilan.
Token: ENGLISH_BOT_TOKEN  |  Claude: ANTHROPIC_API_KEY
"""
import asyncio
import json
import logging
import os
import random

import pytz
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
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
_lesson: dict = {}  # {user_id: {"words": [...], "idx": int}}
_test: dict = {}    # {user_id: {"questions": [...], "idx": int, "score": int, "wrong": []}}


# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖  Bugungi dars", callback_data="eng_lesson")],
        [
            InlineKeyboardButton(text="📝  Test", callback_data="eng_test"),
            InlineKeyboardButton(text="🔁  Takrorlash", callback_data="eng_review"),
        ],
        [InlineKeyboardButton(text="📊  Statistikam", callback_data="eng_progress")],
    ])


def kb_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
    ])


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


# ── UI helpers ────────────────────────────────────────────────────────────────

def _bar(done: int, total: int, n: int = 8) -> str:
    filled = round(n * done / total) if total else 0
    return "█" * filled + "░" * (n - filled)


def _menu_text(user: dict, stats: dict) -> str:
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya" if streak > 1 else "🌱 Seriyani boshlang"
    return (
        f"🎓 <b>Ingliz tili o'qituvchingiz</b>\n"
        f"{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{user['level']}</b>\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<i>Quyidagi tugmalardan birini bosing 👇</i>"
    )


def _word_text(idx: int, total: int, w: dict) -> str:
    return (
        f"📖 <b>So'z {idx}/{total}</b>  {_bar(idx, total)}\n"
        f"{'─' * 28}\n\n"
        f"🔤  <b>{w['word'].upper()}</b>\n\n"
        f"🇺🇿  <b>{w['translation']}</b>\n\n"
        f"📝  <i>{w['definition']}</i>\n\n"
        f"💬  <code>{w['example']}</code>\n\n"
        f"💡  {w['memory_tip']}"
    )


def _question_text(idx: int, total: int, question: str) -> str:
    return (
        f"❓ <b>Savol {idx}/{total}</b>  {_bar(idx, total)}\n"
        f"{'─' * 28}\n\n"
        f"{question}"
    )


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    user = msg.from_user
    db.create_user(user.id, user.username, user.first_name)
    user_data = db.get_user(user.id)
    stats = db.get_stats(user.id)

    await msg.answer(
        f"Salom, <b>{user.first_name}</b>! 👋\n\n" + _menu_text(user_data, stats),
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
    await cb.message.edit_text(
        _menu_text(user_data, stats),
        reply_markup=kb_main_menu(),
        parse_mode=HTML,
    )


# ── Lesson ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_lesson")
async def cb_lesson(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    existing = db.get_today_lesson(user_id)

    if existing:
        words = json.loads(existing["words_json"])
        _lesson[user_id] = {"words": words, "idx": 0}
        await cb.message.edit_text(
            _word_text(1, len(words), words[0]),
            reply_markup=kb_word(1, len(words)),
            parse_mode=HTML,
        )
        return

    await cb.message.edit_text("⏳ <b>Dars tayyorlanmoqda...</b>", parse_mode=HTML)
    user = db.get_user(user_id)
    level = user["level"] if user else "A1"
    learned = db.get_learned_words(user_id)

    try:
        lesson = ai.generate_lesson(level, learned)
        words = lesson["words"]
        db.save_lesson(user_id, words)
        db.update_streak(user_id)
        _lesson[user_id] = {"words": words, "idx": 0}

        await cb.message.edit_text(
            f"📚 <b>Bugungi dars — {level} darajasi</b>\n\n"
            f"✨ {lesson.get('intro', '')}\n\n"
            f"<i>So'zlarni ko'rish uchun tugmani bosing 👇</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Boshlash", callback_data="eng_word_show")]
            ]),
            parse_mode=HTML,
        )
    except Exception as e:
        log.error("lesson error: %s", e)
        await cb.message.edit_text(
            "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
            reply_markup=kb_back_menu(),
        )


@router.callback_query(F.data == "eng_word_show")
async def cb_word_show(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    session = _lesson.get(user_id)
    if not session:
        await cb.message.edit_text("Dars topilmadi.", reply_markup=kb_back_menu())
        return
    idx = session["idx"]
    words = session["words"]
    await cb.message.edit_text(
        _word_text(idx + 1, len(words), words[idx]),
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
    if cb.data == "eng_word_next":
        session["idx"] = min(session["idx"] + 1, len(words) - 1)
    elif cb.data == "eng_word_prev":
        session["idx"] = max(session["idx"] - 1, 0)
    elif cb.data == "eng_word_done":
        _lesson.pop(user_id, None)
        stats = db.get_stats(user_id)
        await cb.message.edit_text(
            f"🎉 <b>Dars tugadi!</b>\n\n"
            f"Bugun <b>5 ta</b> yangi so'z o'rgandingiz!\n"
            f"Jami: <b>{stats['total_words']}</b> ta so'z 📚\n\n"
            f"Endi o'rgangan so'zlarni sinab ko'ramizmi?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝  Test boshlash", callback_data="eng_test")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    idx = session["idx"]
    await cb.message.edit_text(
        _word_text(idx + 1, len(words), words[idx]),
        reply_markup=kb_word(idx + 1, len(words)),
        parse_mode=HTML,
    )


# ── Test ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "eng_test")
async def cb_test(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id

    if user_id in _test:
        await cb.answer("⚠️ Test davom etmoqda!", show_alert=True)
        return

    today = db.get_today_lesson(user_id)
    if not today:
        await cb.message.edit_text(
            "❗ Avval bugungi darsni oling!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_lesson")],
            ]),
        )
        return

    if today["completed"]:
        s = today["test_score"]
        await cb.message.edit_text(
            f"✅ <b>Bugungi test topshirilgan!</b>\n\n"
            f"Natija: <b>{s}/5</b>  {_bar(s * 20, 100)}  <b>{s * 20}%</b>\n\n"
            f"Eski so'zlarni mashq qilishni xohlaysizmi?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁  Takrorlash", callback_data="eng_review")],
                [InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")],
            ]),
            parse_mode=HTML,
        )
        return

    await cb.message.edit_text(
        "⚡ <b>Test tayyorlanmoqda...</b>\n\nBugungi + eski so'zlardan savollar...",
        parse_mode=HTML,
    )

    today_words = json.loads(today["words_json"])
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
            "idx": 0,
            "score": 0,
            "wrong": [],
            "msg_id": cb.message.message_id,
        }
        await _show_question(cb.message, user_id, edit=True)
    except Exception as e:
        log.error("test error: %s", e)
        await cb.message.edit_text(
            "❌ Test yaratishda xatolik. Qayta urinib ko'ring.",
            reply_markup=kb_back_menu(),
        )


async def _show_question(msg: Message, user_id: int, edit: bool = False):
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
    text = _question_text(idx + 1, total, q["question"])
    kb = kb_test_options(q["options"])
    if edit:
        await msg.edit_text(text, reply_markup=kb, parse_mode=HTML)
    else:
        await msg.answer(text, reply_markup=kb, parse_mode=HTML)


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
        icon = "✅"
        result_line = f"✅ <b>To'g'ri!</b>"
    else:
        session["wrong"].append(word)
        icon = "❌"
        result_line = f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{q['correct']}</b>"

    # Show result in the same message, then after short delay show next question
    total = len(session["questions"])
    result_text = (
        f"{icon} <b>Savol {idx + 1}/{total}</b>\n"
        f"{'─' * 28}\n\n"
        f"{result_line}\n\n"
        f"💡 {q.get('explanation', '')}"
    )
    await cb.message.edit_text(result_text, parse_mode=HTML)

    session["idx"] += 1
    await asyncio.sleep(1.2)

    if session["idx"] >= total:
        await _finish_test(cb.message, user_id)
    else:
        await _show_question(cb.message, user_id, edit=True)


async def _finish_test(msg: Message, user_id: int):
    session = _test.pop(user_id, {})
    score = session.get("score", 0)
    wrong = session.get("wrong", [])
    pct = score * 20

    db.save_test_result(user_id, score, wrong)

    user = db.get_user(user_id)
    level = user["level"] if user else "A1"
    feedback = ai.get_feedback(score, 5, level, wrong)

    emoji = "🌟" if pct == 100 else "🎯" if pct >= 80 else "💪" if pct >= 60 else "📖"
    text = (
        f"{emoji} <b>Test yakunlandi!</b>\n"
        f"{'─' * 28}\n\n"
        f"Natija: <b>{score}/5</b>\n"
        f"{_bar(pct, 100, 10)}  <b>{pct}%</b>\n\n"
        f"{feedback}"
    )

    stats = db.get_stats(user_id)
    if pct >= 80 and stats["total_words"] >= 100:
        nxt = ai.next_level(level)
        if nxt:
            db.update_level(user_id, nxt)
            text += f"\n\n🎉 <b>Tabriklayman! {nxt} darajasiga o'tdingiz!</b>"

    buttons = []
    if wrong:
        buttons.append([InlineKeyboardButton(text="🔁  Xato so'zlarni mashq qil", callback_data="eng_review")])
    buttons.append([InlineKeyboardButton(text="🏠  Bosh menu", callback_data="eng_menu")])

    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=HTML)


# ── Review ────────────────────────────────────────────────────────────────────

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
                [InlineKeyboardButton(text="📖  Darsga o'tish", callback_data="eng_lesson")],
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
            "idx": 0,
            "score": 0,
            "wrong": [],
        }
        await _show_question(cb.message, user_id, edit=True)
    except Exception as e:
        log.error("review error: %s", e)
        await cb.message.edit_text(
            "❌ Xatolik. Qayta urinib ko'ring.",
            reply_markup=kb_back_menu(),
        )


# ── Progress ──────────────────────────────────────────────────────────────────

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

    cefr_progress = {
        "A1": "░░░░░░░░ → A2 → B1 → B2",
        "A2": "███░░░░░ → B1 → B2",
        "B1": "█████░░░ → B2",
        "B2": "████████ Maqsadga erishdingiz! 🎓",
    }

    await cb.message.edit_text(
        f"📊 <b>Sizning statistikangiz</b>\n"
        f"{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{level}</b>\n"
        f"<code>{cefr_progress.get(level, '')}</code>\n\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"✅  Yakunlangan darslar: <b>{stats['done_lessons']}</b>\n"
        f"🎯  O'rtacha test bali: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<b>Keyingi darajaga progress:</b>\n"
        f"{_bar(pct_lvl, 100, 10)}  <b>{pct_lvl}%</b>\n"
        f"({stats['total_words']}/{target} so'z)",
        reply_markup=kb_back_menu(),
        parse_mode=HTML,
    )


# ── Scheduled jobs ────────────────────────────────────────────────────────────

async def _morning_job(bot: Bot):
    for user in db.get_all_users():
        uid = user["user_id"]
        try:
            if db.get_today_lesson(uid):
                continue
            learned = db.get_learned_words(uid)
            lesson = ai.generate_lesson(user["level"], learned)
            db.save_lesson(uid, lesson["words"])
            db.update_streak(uid)
            _lesson[uid] = {"words": lesson["words"], "idx": 0}
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"🌅 <b>Xayrli tong!</b>\n\n"
                    f"✨ {lesson.get('intro', 'Bugungi dars tayyor!')}"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📖  Darsni boshlash", callback_data="eng_lesson")],
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
                    text="🌙 <b>Test vaqti!</b>\n\nBugungi so'zlarni sinab ko'rish vaqti keldi 💪",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝  Testni boshlash", callback_data="eng_test")],
                    ]),
                    parse_mode=HTML,
                )
        except Exception as e:
            log.error("evening job uid=%s: %s", uid, e)


# ── Entry point ───────────────────────────────────────────────────────────────

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
