"""
English AI Teacher Bot — aiogram 3.x
Har kuni 5 ta so'z + test + o'tilgan so'zlardan takrorlash.

Ishga tushirish: telegram_bot/bot.py dan english_bot_polling() chaqiriladi.
Token: ENGLISH_BOT_TOKEN env o'zgaruvchisi.
"""
import asyncio
import json
import logging
import os
import random

import pytz
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
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

# in-memory sessions
_lesson: dict = {}  # {user_id: {"words": [...], "idx": int}}
_test: dict = {}    # {user_id: {"questions": [...], "idx": int, "score": int, "wrong": []}}


# ── UI helpers ────────────────────────────────────────────────────────────────

def _bar(done: int, total: int, n: int = 8) -> str:
    filled = round(n * done / total) if total else 0
    return "█" * filled + "░" * (n - filled)


def _word_html(idx: int, total: int, w: dict) -> str:
    return (
        f"📖 <b>So'z {idx}/{total}</b>  {_bar(idx, total)}\n"
        f"{'─' * 28}\n\n"
        f"🔤  <b>{w['word'].upper()}</b>\n\n"
        f"🇺🇿  <b>{w['translation']}</b>\n\n"
        f"📝  <i>{w['definition']}</i>\n\n"
        f"💬  <code>{w['example']}</code>\n\n"
        f"💡  {w['memory_tip']}"
    )


def _word_kb(idx: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if idx > 1:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data="eng_word_prev"))
    if idx < total:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data="eng_word_next"))
    if nav:
        rows.append(nav)
    if idx == total:
        rows.append([InlineKeyboardButton(text="✅ Darsni tugatdim!", callback_data="eng_word_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _test_kb(options: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"eng_ans_{opt[0]}")]
            for opt in options
        ]
    )


# ── /english_start ────────────────────────────────────────────────────────────

@router.message(Command("english_start"))
async def cmd_start(msg: Message):
    db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    await msg.answer(
        f"Salom, <b>{msg.from_user.first_name}</b>! 👋\n\n"
        "Men sizning shaxsiy ingliz tili o'qituvchingizman 🎓\n\n"
        "<b>Har kuni:</b>\n"
        "🌅  <b>09:00</b> — 5 ta yangi so'z dars\n"
        "🌙  <b>21:00</b> — Test eslatmasi\n\n"
        "<b>Buyruqlar:</b>\n"
        "/english_lesson     — Bugungi yangi so'zlar\n"
        "/english_test        — Kunlik test\n"
        "/english_review     — Xato so'zlarni mashq\n"
        "/english_progress — Statistikam\n\n"
        "🚀 Boshlash uchun /english_lesson bosing!",
        parse_mode=HTML,
    )


# ── /english_lesson ───────────────────────────────────────────────────────────

@router.message(Command("english_lesson"))
async def cmd_lesson(msg: Message):
    user_id = msg.from_user.id
    existing = db.get_today_lesson(user_id)

    if existing:
        words = json.loads(existing["words_json"])
        _lesson[user_id] = {"words": words, "idx": 0}
        await msg.answer("🔁 Bugungi dars takrorlanmoqda...")
        await _show_word(msg, user_id)
        return

    await msg.answer("⏳ Dars tayyorlanmoqda...")
    user = db.get_user(user_id)
    level = user["level"] if user else "A1"
    learned = db.get_learned_words(user_id)

    try:
        lesson = ai.generate_lesson(level, learned)
        words = lesson["words"]
        db.save_lesson(user_id, words)
        db.update_streak(user_id)
        _lesson[user_id] = {"words": words, "idx": 0}
        await msg.answer(
            f"📚 <b>Bugungi dars — {level} darajasi</b>\n\n✨ {lesson.get('intro', '')}",
            parse_mode=HTML,
        )
        await asyncio.sleep(0.3)
        await _show_word(msg, user_id)
    except Exception as e:
        log.error("lesson error: %s", e)
        await msg.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")


async def _show_word(msg: Message, user_id: int):
    session = _lesson.get(user_id)
    if not session:
        return
    idx = session["idx"]
    words = session["words"]
    await msg.answer(
        _word_html(idx + 1, len(words), words[idx]),
        reply_markup=_word_kb(idx + 1, len(words)),
        parse_mode=HTML,
    )


@router.callback_query(F.data.in_({"eng_word_prev", "eng_word_next", "eng_word_done"}))
async def cb_word_nav(cb: CallbackQuery):
    await cb.answer()
    user_id = cb.from_user.id
    session = _lesson.get(user_id)
    if not session:
        await cb.answer("Dars topilmadi. /english_lesson bosing.", show_alert=True)
        return

    action = cb.data
    words = session["words"]

    if action == "eng_word_next":
        session["idx"] = min(session["idx"] + 1, len(words) - 1)
    elif action == "eng_word_prev":
        session["idx"] = max(session["idx"] - 1, 0)
    elif action == "eng_word_done":
        _lesson.pop(user_id, None)
        stats = db.get_stats(user_id)
        await cb.message.edit_text(
            f"🎉 <b>Dars tugadi!</b>\n\n"
            f"Bugun 5 ta yangi so'z o'rgandingiz!\n"
            f"Jami: <b>{stats['total_words']}</b> ta so'z 📚\n\n"
            f"Test qilib ko'ramizmi? 👉 /english_test",
            parse_mode=HTML,
        )
        return

    idx = session["idx"]
    await cb.message.edit_text(
        _word_html(idx + 1, len(words), words[idx]),
        reply_markup=_word_kb(idx + 1, len(words)),
        parse_mode=HTML,
    )


# ── /english_test ─────────────────────────────────────────────────────────────

@router.message(Command("english_test"))
async def cmd_test(msg: Message):
    user_id = msg.from_user.id

    if user_id in _test:
        await msg.answer("⚠️ Test davom etmoqda. Savollarga javob bering.")
        return

    today = db.get_today_lesson(user_id)
    if not today:
        await msg.answer("❗ Avval bugungi darsni oling: /english_lesson")
        return

    if today["completed"]:
        s = today["test_score"]
        await msg.answer(
            f"✅ Bugungi test topshirilgan!\n\n"
            f"Natija: <b>{s}/5</b>  ({s * 20}%)\n\n"
            f"Eski so'zlarni mashq qilish: /english_review",
            parse_mode=HTML,
        )
        return

    today_words = json.loads(today["words_json"])
    old_pool = [w for w in db.get_learned_words(user_id, limit=80)
                if w not in {x["word"].lower() for x in today_words}]

    test_words = list(today_words)
    if len(old_pool) >= 3:
        sample = random.sample(old_pool, min(2, len(old_pool)))
        old_dicts = db.get_words_by_list(user_id, sample)
        test_words = test_words[:3] + old_dicts[:2]

    random.shuffle(test_words)

    await msg.answer(
        "📝 <b>Test boshlanmoqda...</b>\n⚡ Savollar tayyorlanmoqda...",
        parse_mode=HTML,
    )

    try:
        result = ai.generate_test(test_words)
        _test[user_id] = {
            "questions": result["questions"],
            "idx": 0,
            "score": 0,
            "wrong": [],
        }
        await _send_question(msg, user_id)
    except Exception as e:
        log.error("test error: %s", e)
        await msg.answer("❌ Test yaratishda xatolik. Qayta urinib ko'ring.")


async def _send_question(target, user_id: int):
    session = _test.get(user_id)
    if not session:
        return
    idx = session["idx"]
    qs = session["questions"]
    if idx >= len(qs):
        await _finish_test(target, user_id)
        return
    q = qs[idx]
    total = len(qs)
    text = (
        f"❓ <b>Savol {idx + 1}/{total}</b>  {_bar(idx + 1, total)}\n"
        f"{'─' * 28}\n\n{q['question']}"
    )
    send = target.answer if isinstance(target, Message) else target.message.answer
    await send(text, reply_markup=_test_kb(q["options"]), parse_mode=HTML)


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
        result_line = "✅ <b>To'g'ri!</b>"
    else:
        session["wrong"].append(word)
        result_line = f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{q['correct']}</b>"

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        f"{result_line}\n\n💡 {q.get('explanation', '')}",
        parse_mode=HTML,
    )

    session["idx"] += 1
    await asyncio.sleep(0.8)
    await _send_question(cb, user_id)


async def _finish_test(target, user_id: int):
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
        f"{emoji} <b>Test yakunlandi!</b>\n\n"
        f"Natija: <b>{score}/5</b>  {_bar(pct, 100, 10)}  <b>{pct}%</b>\n\n"
        f"{feedback}"
    )

    stats = db.get_stats(user_id)
    if pct >= 80 and stats["total_words"] >= 100:
        nxt = ai.next_level(level)
        if nxt:
            db.update_level(user_id, nxt)
            text += f"\n\n🎉 <b>Tabriklayman! Siz {nxt} darajasiga o'tdingiz!</b>"

    if wrong:
        text += "\n\n🔁 Xato so'zlarni mashq: /english_review"

    send = target.answer if isinstance(target, Message) else target.message.answer
    await send(text, parse_mode=HTML)


# ── /english_review ───────────────────────────────────────────────────────────

@router.message(Command("english_review"))
async def cmd_review(msg: Message):
    user_id = msg.from_user.id
    if user_id in _test:
        await msg.answer("⚠️ Avval joriy testni tugatib oling.")
        return

    words = db.get_words_for_review(user_id, limit=5)
    if not words:
        await msg.answer(
            "📭 Hali tekshiriladigan so'zlar yo'q.\n\n"
            "Avval bir nechta dars o'ting: /english_lesson"
        )
        return

    await msg.answer(
        f"🔁 <b>Takrorlash sessiyasi</b>\n\n"
        f"Eng ko'p xato qilingan <b>{len(words)}</b> ta so'z...",
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
        await _send_question(msg, user_id)
    except Exception as e:
        log.error("review error: %s", e)
        await msg.answer("❌ Xatolik. Qayta urinib ko'ring.")


# ── /english_progress ─────────────────────────────────────────────────────────

@router.message(Command("english_progress"))
async def cmd_progress(msg: Message):
    user_id = msg.from_user.id
    user = db.get_user(user_id)
    if not user:
        await msg.answer("Avval /english_start bosing!")
        return

    stats = db.get_stats(user_id)
    level = user["level"]
    targets = {"A1": 100, "A2": 300, "B1": 600, "B2": 1000}
    target = targets.get(level, 100)
    pct_lvl = min(100, round(stats["total_words"] / target * 100))
    streak = stats["streak"]
    streak_txt = f"🔥 {streak} kunlik seriya!" if streak > 1 else "🌱 Seriyani boshlang!"

    await msg.answer(
        f"📊 <b>Sizning statistikangiz</b>\n{'─' * 28}\n\n"
        f"🏆  Daraja: <b>{level}</b>\n"
        f"📚  O'rganilgan so'zlar: <b>{stats['total_words']}</b>\n"
        f"✅  Yakunlangan darslar: <b>{stats['done_lessons']}</b>\n"
        f"🎯  O'rtacha ball: <b>{stats['avg_score']}%</b>\n"
        f"{streak_txt}\n\n"
        f"<b>Keyingi darajaga:</b>\n"
        f"{_bar(pct_lvl, 100, 10)}  {pct_lvl}%  ({stats['total_words']}/{target})",
        parse_mode=HTML,
    )


# ── Scheduler jobs ────────────────────────────────────────────────────────────

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
                    f"✨ {lesson.get('intro', 'Bugungi dars tayyor!')}\n\n"
                    f"👉 /english_lesson"
                ),
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
                    text=(
                        "🌙 <b>Test vaqti!</b>\n\n"
                        "Bugungi so'zlarni sinab ko'rish: /english_test"
                    ),
                    parse_mode=HTML,
                )
        except Exception as e:
            log.error("evening job uid=%s: %s", uid, e)


# ── Entry point (called from telegram_bot/bot.py) ────────────────────────────

async def english_bot_polling():
    """Run the English Teacher bot. Imported and called by telegram_bot/bot.py."""
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
            log.error("English Teacher Bot polling error: %s", err)
            await asyncio.sleep(10)
