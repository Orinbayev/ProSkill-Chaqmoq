"""Claude-powered AI teacher for English vocabulary lessons and tests."""
import json
import re

import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ask(prompt: str, max_tokens: int = 2500) -> str:
    r = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group() if m else text)


def generate_lesson(level: str, learned_words: list) -> dict:
    avoid = learned_words[-40:] if learned_words else []
    prompt = f"""Sen ingliz tili o'qituvchisisiz. O'zbek tilida gapiradigan talaba uchun {level} darajasida dars tayyorla.

Bu so'zlarni TAKRORLAMA (allaqachon o'rganilgan): {avoid}

{level} darajasiga mos, kundalik hayotda tez-tez ishlatiladigan 5 ta yangi so'z tanlang.

Faqat JSON qaytaring:
{{
    "intro": "Bugungi darsga energetik motivatsion kirish (o'zbek tilida, 1-2 gap)",
    "words": [
        {{
            "word": "so'z (kichik harf)",
            "translation": "o'zbek tarjimasi",
            "definition": "{level} darajasiga mos inglizcha ta'rif (oddiy va qisqa)",
            "example": "tabiiy inglizcha misol gap",
            "memory_tip": "eslab qolish uchun qiziqarli yoki kulgili maslahat (o'zbek tilida)"
        }}
    ]
}}"""
    return _json(_ask(prompt))


def generate_test(words: list) -> dict:
    words_str = json.dumps(words, ensure_ascii=False, indent=2)
    prompt = f"""Quyidagi ingliz so'zlari uchun test yarating:

{words_str}

5 ta savol (har bir so'z uchun 1 ta). Xilma-xil savol turlari ishlating:
- O'zbek tarjimasini inglizchadan tanlash
- Misol gapdagi bo'sh joyni (___ ) to'ldirish
- Ta'rifga mos so'zni topish
- Inglizcha so'zni o'zbekchadan tanlash

Har birida 4 ta variant. Noto'g'ri variantlar mantiqiy va chalg'ituvchi bo'lsin.

Faqat JSON qaytaring:
{{
    "questions": [
        {{
            "word": "test qilinayotgan so'z",
            "question": "savol matni",
            "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "correct": "A",
            "explanation": "nima uchun shu javob to'g'ri (o'zbek tilida, 1 gap)"
        }}
    ]
}}"""
    return _json(_ask(prompt))


def get_feedback(score: int, total: int, level: str, wrong_words: list) -> str:
    pct = round(score / total * 100)
    wrong_str = ", ".join(wrong_words) if wrong_words else "yo'q"
    prompt = f"""Talaba ingliz tili testini topshirdi: {score}/{total} ({pct}%). Daraja: {level}.
Xato qilingan so'zlar: {wrong_str}

O'zbek tilida 2-3 gap motivatsion xabar yoz:
- 100%: ajoyib, maqta!
- 80-99%: yaxshi, lekin shu so'zlarga e'tibor ber
- 60-79%: yaxshi harakat, takrorlash kerak
- <60%: rag'batlantir, bot ertaga yana o'rgatishini ayt

Faqat xabar matnini qaytaring."""
    return _ask(prompt, max_tokens=250).strip()


LEVELS = ["A1", "A2", "B1", "B2"]


def next_level(current: str) -> str | None:
    i = LEVELS.index(current) if current in LEVELS else -1
    return LEVELS[i + 1] if 0 <= i < len(LEVELS) - 1 else None
