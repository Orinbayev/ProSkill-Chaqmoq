"""Claude-powered AI teacher — topic-based lessons with 15+ items."""
import json
import re

import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ask(prompt: str, max_tokens: int = 4000) -> str:
    r = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group() if m else text)


def generate_lesson(level: str, topic: dict, learned_words: list) -> dict:
    """
    Generate a lesson for a specific curriculum topic.
    topic = {"name_uz", "name_en", "min_items", "instructions"}
    Returns: {"intro", "topic_uz", "topic_en", "items": [...]}
    """
    min_items = topic.get("min_items", 15)
    instructions = topic.get("instructions", "")
    name_en = topic.get("name_en", "")
    name_uz = topic.get("name_uz", "")

    # Avoid already-learned words (for vocabulary topics)
    avoid = learned_words[-50:] if learned_words else []

    prompt = f"""Sen ingliz tili o'qituvchisisisan. O'zbek tilida gapiradigan boshlang'ich talaba uchun {level} darajasida dars tayyorla.

MAVZU: {name_en} ({name_uz})

Ko'rsatma:
{instructions}

Avval o'rganilgan so'zlar (takrorlama): {avoid}

Kamida {min_items} ta element ber. Grammatik mavzular uchun qoidalarni ham tushuntir.

Faqat JSON qaytaring:
{{
    "intro": "Bugungi mavzuga qiziqarli kirish (o'zbek tilida, 1-2 gap, energetik)",
    "topic_uz": "{name_uz}",
    "topic_en": "{name_en}",
    "items": [
        {{
            "word": "inglizcha so'z yoki ibora (kichik harf)",
            "translation": "o'zbek tarjimasi",
            "definition": "inglizcha ta'rif yoki grammatik qoida (oddiy)",
            "example": "misol gap (to'liq inglizcha gap)",
            "memory_tip": "eslab qolish uchun maslahat yoki qoida (o'zbek tilida)",
            "rule": ""
        }}
    ]
}}

MUHIM:
- Artikl mavzusi uchun 'rule' maydoniga nima uchun 'a' yoki 'an' ishlatilishini yoz
- Grammatik mavzularda 'definition' maydoniga qoidani yoz
- Barcha {min_items}+ element bo'lsin, hech birini qoldirma
- Faqat JSON, boshqa matn yo'q"""

    return _json(_ask(prompt, max_tokens=6000))


def generate_test(items: list, topic_name: str = "") -> dict:
    """
    Generate test questions for all items in the lesson.
    Returns: {"questions": [...]}
    """
    items_str = json.dumps(items, ensure_ascii=False, indent=2)
    count = len(items)
    topic_hint = f"Mavzu: {topic_name}. " if topic_name else ""

    prompt = f"""{topic_hint}Quyidagi ingliz tili elementlari uchun {count} ta test savoli yarat:

{items_str}

Har element uchun 1 ta savol. Xilma-xil savol turlari:
- O'zbek tarjimasini inglizchadan tanlash
- Misol gapdagi bo'sh joyni (___ ) to'ldirish
- Ta'rifga/qoidaga mos so'zni topish
- Inglizcha so'zni o'zbekchadan tanlash
- Grammatik mavzularda: to'g'ri shaklni tanlash

Har birida 4 ta variant. Noto'g'ri variantlar mantiqiy va chalg'ituvchi bo'lsin.

Faqat JSON qaytaring:
{{
    "questions": [
        {{
            "word": "test qilinayotgan element",
            "question": "savol matni",
            "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "correct": "A",
            "explanation": "nima uchun shu javob to'g'ri (o'zbek tilida, 1 gap)"
        }}
    ]
}}"""
    return _json(_ask(prompt, max_tokens=8000))


def get_feedback(score: int, total: int, level: str, wrong_words: list) -> str:
    pct = round(score / total * 100)
    wrong_str = ", ".join(wrong_words[:5]) if wrong_words else "yo'q"
    prompt = f"""Talaba ingliz tili testini topshirdi: {score}/{total} ({pct}%). Daraja: {level}.
Xato qilingan elementlar: {wrong_str}

O'zbek tilida 2-3 gap motivatsion xabar yoz:
- 90-100%: zo'r, maqta
- 70-89%: yaxshi, shu elementlarga e'tibor ber
- 50-69%: harakat qil, takrorlash kerak
- <50%: rag'batlantir

Faqat xabar matnini qaytaring."""
    return _ask(prompt, max_tokens=200).strip()


def check_sentence(word: str, user_sentence: str) -> dict:
    """Check if user correctly used the word in a sentence."""
    prompt = f"""Talaba '{word}' so'zini ishlatib gap yozdi:
"{user_sentence}"

Tekshir va JSON qaytار:
{{
    "correct": true/false,
    "feedback": "o'zbek tilida qisqa izoh (1-2 gap) — to'g'ri bo'lsa maqta, xato bo'lsa tuzat",
    "corrected": "agar xato bo'lsa to'g'ri variant, aks holda bo'sh qoldir"
}}"""
    return _json(_ask(prompt, max_tokens=300))


LEVELS = ["A1", "A2", "B1", "B2"]


def next_level(current: str) -> str | None:
    i = LEVELS.index(current) if current in LEVELS else -1
    return LEVELS[i + 1] if 0 <= i < len(LEVELS) - 1 else None
