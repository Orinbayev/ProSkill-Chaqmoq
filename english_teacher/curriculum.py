"""
A1 → B2 o'quv reja.
Har kun bir mavzu, kamida 15 ta element (alifbo = 26, sonlar = 21, va h.k.)
"""

# (kun, mavzu_uz, mavzu_en, min_son, claude_uchun_ko'rsatma)
A1_CURRICULUM = [
    # ── 1-hafta: Mutlaq asos ─────────────────────────────────────────────────
    (1,  "Ingliz alifbosi (A–Z)",
         "English Alphabet A–Z",
         26,
         "Barcha 26 ta ingliz harfi. Har harf uchun: harf (katta+kichik), "
         "talaffuz (IPA yoki oddiy), o'zbek misoli so'z. "
         "Misol: 'A a — [eɪ] — Apple (olma)'"),

    (2,  "Sonlar: 0 dan 20 gacha",
         "Numbers 0–20",
         21,
         "0 dan 20 gacha barcha sonlar. Har son uchun: raqam, inglizcha yozuv, "
         "o'zbek tarjimasi, misol gap. Misol: '7 — seven — etti — I have seven apples.'"),

    (3,  "Salomlashish va xayrlashish",
         "Greetings & Farewells",
         16,
         "Hello, Hi, Good morning, Good afternoon, Good evening, Good night, "
         "Goodbye, Bye, See you later, See you tomorrow, Nice to meet you, "
         "How are you?, I'm fine thanks, What's your name?, My name is..., "
         "Where are you from?"),

    (4,  "Olmoshlar va 'To Be' fe'li",
         "Pronouns + Verb To Be",
         18,
         "I am, You are, He is, She is, It is, We are, They are — "
         "ijobiy, inkor (I am not), so'roq (Are you?) shakllari bilan. "
         "Har bir shakl uchun misol gap. Qisqa shakl: I'm, You're, He's..."),

    (5,  "Oila a'zolari",
         "Family Members",
         16,
         "Mother, father, sister, brother, son, daughter, grandmother, grandfather, "
         "husband, wife, uncle, aunt, cousin, baby, parents, children — "
         "har biri uchun o'zbek tarjimasi va misol gap"),

    # ── 2-hafta: Grammatika asoslari ─────────────────────────────────────────
    (6,  "Artiklar: 'a', 'an', 'the'",
         "Articles: a / an / the",
         18,
         "MUHIM: Bu grammatik mavzu. Quyidagilarni batafsil o'rgat:\n"
         "1) 'a' — undosh tovush oldidan: a book, a car, a dog\n"
         "2) 'an' — unli tovush (a,e,i,o,u) oldidan: an apple, an egg, an orange\n"
         "3) 'the' — aniq narsa oldidan: the sun, the moon, close the door\n"
         "4) Artikl ishlatilmaydigan holatlar: proper nouns, languages\n"
         "Kamida 18 ta misol gap ber. Har misol uchun nima uchun shu artikl ekanligi tushuntir."),

    (7,  "Ranglar va tavsif",
         "Colors & Description",
         18,
         "Red, blue, green, yellow, black, white, orange, purple, pink, "
         "brown, grey, dark blue, light green, golden, silver, colorful — "
         "har biri uchun misol: 'The sky is blue.' / 'She has red shoes.'"),

    (8,  "Hafta kunlari, oylar va fasllar",
         "Days, Months & Seasons",
         24,
         "7 ta hafta kuni (Monday..Sunday) + 12 oy (January..December) + "
         "4 fasl (Spring, Summer, Autumn/Fall, Winter). "
         "Har biri uchun o'zbek tarjimasi va bitta misol gap."),

    (9,  "Asosiy harakat fe'llari",
         "Common Action Verbs",
         20,
         "Go, come, eat, drink, sleep, wake up, walk, run, read, write, "
         "speak/talk, listen, watch, play, study, work, cook, buy, help, love — "
         "har fe'l uchun: infinitiv, o'zbek tarjimasi, misol gap"),

    (10, "Tananing qismlari",
         "Body Parts",
         20,
         "Head, hair, face, eye, ear, nose, mouth, tooth/teeth, neck, "
         "shoulder, arm, hand, finger, chest, stomach, back, leg, knee, foot/feet, toe — "
         "har biri uchun o'zbek tarjimasi va misol gap"),

    # ── 3-hafta: Kundalik hayot ───────────────────────────────────────────────
    (11, "Ovqat va ichimliklar",
         "Food & Drinks",
         22,
         "Bread, rice, meat, chicken, fish, egg, milk, water, tea, coffee, "
         "juice, apple, banana, orange, tomato, potato, soup, salad, cake, "
         "sugar, salt, oil — har biri o'zbek tarjimasi + misol: 'I eat bread every morning.'"),

    (12, "Hayvonlar",
         "Animals",
         20,
         "Dog, cat, bird, fish, horse, cow, sheep, chicken, lion, tiger, "
         "elephant, monkey, rabbit, snake, frog, butterfly, bee, ant, eagle, whale — "
         "har biri o'zbek tarjimasi + qisqa misol gap"),

    (13, "Uy va xonalar",
         "House & Rooms",
         18,
         "House, flat/apartment, bedroom, living room, bathroom, kitchen, "
         "garden/yard, door, window, wall, floor, ceiling, table, chair, bed, sofa, lamp, fridge — "
         "har biri uchun: o'zbek tarjimasi, misol: 'The kitchen is clean.'"),

    (14, "Kiyim-kechak",
         "Clothes & Accessories",
         18,
         "Shirt, trousers/pants, dress, skirt, jacket, coat, shoes, boots, "
         "socks, hat, scarf, gloves, belt, tie, jeans, sweater, uniform, "
         "sunglasses — o'zbek tarjimasi + misol: 'She wears a red dress.'"),

    (15, "Maktab, ta'lim va kasb-kor",
         "School, Education & Jobs",
         20,
         "School, class, teacher, student, book, pen, pencil, notebook, bag, "
         "desk, board, lesson, homework, exam, grade/mark, university, doctor, "
         "engineer, driver, farmer, police — har biri tarjima + misol gap"),

    # ── 4-hafta: Grammatika + Amaliyot ───────────────────────────────────────
    (16, "Katta sonlar (21–1000)",
         "Larger Numbers 21–1000",
         20,
         "21 (twenty-one), 30 (thirty), 40 (forty), 50 (fifty), 60 (sixty), "
         "70 (seventy), 80 (eighty), 90 (ninety), 100 (one hundred), "
         "200, 300, 500, 1000 (one thousand). "
         "22, 35, 47, 68, 99 kabi qo'shma sonlar ham ber. Misol gaplar bilan."),

    (17, "Sifatlar: qarama-qarshi juftlar",
         "Opposite Adjectives",
         22,
         "Big/Small, Tall/Short, Old/New, Good/Bad, Fast/Slow, Hot/Cold, "
         "Happy/Sad, Beautiful/Ugly, Clean/Dirty, Rich/Poor, Strong/Weak, "
         "Easy/Hard, Near/Far, Loud/Quiet, Light/Heavy, Full/Empty, "
         "Open/Closed, Right/Wrong — har juft uchun misol gaplar"),

    (18, "Ko'rsatish olmoshlari va 'There is/are'",
         "This/That/These/Those + There is/are",
         16,
         "This is a pen. (yaqin, birlik)\n"
         "That is a book. (uzoq, birlik)\n"
         "These are apples. (yaqin, ko'plik)\n"
         "Those are cars. (uzoq, ko'plik)\n"
         "There is a cat on the table. (bor — birlik)\n"
         "There are two dogs in the garden. (bor — ko'plik)\n"
         "Is there a bank near here? — Yes, there is.\n"
         "Kamida 16 ta misol gap qoida bilan ber."),

    (19, "Vaqt: soat, kun qismlari, ravishlar",
         "Time: Clock, Parts of Day & Adverbs",
         18,
         "It's 3 o'clock / half past 2 / quarter to 5 / quarter past 8\n"
         "Morning, afternoon, evening, night, midnight, noon\n"
         "Yesterday, today, tomorrow, now, soon, later, early, late\n"
         "Always, usually, often, sometimes, rarely, never\n"
         "Har biri uchun misol gap ber."),

    (20, "So'roq so'zlari (WH–Questions)",
         "Question Words: WH–Questions",
         16,
         "What (nima), Who (kim), Where (qayerda), When (qachon), "
         "Why (nima uchun), How (qanday), How many (nechta — sanaladigan), "
         "How much (qancha — sanalmaydigan), Which (qaysi), Whose (kimning)\n"
         "Har biri uchun: tarjima + 2 ta misol savol va javob:\n"
         "'Where are you from? — I am from Uzbekistan.'"),
]

A2_CURRICULUM = [
    (1,  "Present Simple: ijobiy gaplar",       "Present Simple: Affirmative",    16,
         "I work, You work, He works (3rd person +s/es qoidasi) — "
         "16 ta turli fe'l bilan misol gaplar"),
    (2,  "Present Simple: inkor va so'roq",     "Present Simple: Negative & Questions", 15,
         "I don't work, He doesn't work. Do you work? Does she work? — qoida + 15 misol"),
    (3,  "Present Continuous",                  "Present Continuous (am/is/are + ing)", 16,
         "I am working now. She is reading. They are playing. "
         "Qoida: -ing qo'shish (sit→sitting, run→running) + 16 misol"),
    (4,  "Tartib sonlar va sanalar",             "Ordinal Numbers & Dates", 20,
         "1st (first), 2nd, 3rd, 4th..20th, 21st, 30th, 100th — "
         "sanani o'qish: 'July 5th, 2026'"),
    (5,  "Prepositions of place",               "Prepositions: in/on/at/under/next to", 16,
         "The book is on the table. The cat is under the chair. "
         "I live in Tashkent. She is at school. — 16 misol gap"),
    (6,  "Prepositions of time",                "Prepositions: in/on/at for Time", 15,
         "at 3 o'clock / on Monday / in July / in 2026 / at night / on the weekend — 15 misol"),
    (7,  "Past Simple: muntazam fe'llar",       "Past Simple: Regular Verbs (-ed)", 18,
         "work→worked, play→played, walk→walked. "
         "I worked yesterday. Did you play? I didn't work. — 18 misol"),
    (8,  "Past Simple: notartibli fe'llar 1",   "Irregular Verbs Part 1", 20,
         "go→went, come→came, eat→ate, drink→drank, sleep→slept, "
         "see→saw, say→said, take→took, give→gave, get→got, know→knew, "
         "think→thought, make→made, do→did, have→had, be→was/were, "
         "run→ran, buy→bought, write→wrote, read→read"),
    (9,  "Past Simple: notartibli fe'llar 2",   "Irregular Verbs Part 2", 20,
         "speak→spoke, find→found, tell→told, leave→left, feel→felt, "
         "meet→met, begin→began, break→broke, bring→brought, build→built, "
         "choose→chose, drive→drove, fall→fell, fly→flew, grow→grew, "
         "hear→heard, keep→kept, lose→lost, mean→meant, send→sent"),
    (10, "Future: will va going to",             "Future: will / going to", 16,
         "I will call you tomorrow. (qaror hozir qabul qilingan)\n"
         "I am going to study tonight. (oldindan rejalashtirilgan)\n"
         "Will you help me? / Are you going to travel? — 16 misol"),
    (11, "Can, can't, could, couldn't",         "Modal Verbs: can / could", 15,
         "I can swim. She can't drive. Can you help? "
         "I could run fast when I was young. — 15 misol + qoida"),
    (12, "Must, have to, should",               "Modal Verbs: must / have to / should", 15,
         "You must stop. (qat'iy majburiyat)\n"
         "I have to work. (tashqi majburiyat)\n"
         "You should sleep early. (maslahat) — 15 misol + farqlar"),
    (13, "Savol gaplari (Question tags)",       "Question Tags & Short Answers", 15,
         "It's hot, isn't it? / You like tea, don't you? / "
         "She didn't come, did she? — qoida + 15 misol"),
    (14, "Ko'plik: murakkab shakllar",          "Plural Forms: Irregular & Rules", 16,
         "Regular: book→books, bus→buses\n"
         "Irregular: child→children, man→men, woman→women, "
         "tooth→teeth, foot→feet, mouse→mice, ox→oxen, sheep→sheep, fish→fish — 16 ta"),
    (15, "Sifat darajalari",                    "Comparative & Superlative Adjectives", 18,
         "tall→taller→tallest / big→bigger→biggest / "
         "beautiful→more beautiful→most beautiful / good→better→best / "
         "bad→worse→worst / far→farther→farthest — 18 misol gap"),
    (16, "Ravishlar (Adverbs)",                 "Adverbs of Manner & Frequency", 16,
         "Slowly, quickly, carefully, easily, well, badly, hard, fast, "
         "always, usually, often, sometimes, rarely, never — qoida + 16 misol"),
    (17, "Makon va yo'nalish",                  "Places in Town & Directions", 20,
         "Bank, hospital, school, shop, restaurant, park, station, airport, "
         "hotel, post office, pharmacy, library, museum, church, mosque.\n"
         "Turn left/right, go straight, cross, next to, opposite — 20 element"),
    (18, "Telefon, sovg'a, xarid",              "Shopping, Gifts & Phone", 16,
         "How much is it? / I'd like... / Can I have...? / "
         "It costs... / Expensive, cheap, discount, receipt, cash, card — 16 element"),
    (19, "His/her/their — Possessives",         "Possessive Adjectives & Pronouns", 16,
         "My/mine, your/yours, his, her/hers, its, our/ours, their/theirs — "
         "qoida + 16 misol gap"),
    (20, "A1 takrorlash va A2 kirish",          "A1 Review + A2 Preview", 16,
         "Eng muhim A1 qoidalar takrorlash: to be, articles, present simple basics. "
         "A2 da nima o'rganiladi: past simple, future, modal verbs — 16 misol"),
]

B1_CURRICULUM = [
    (1,  "Present Perfect asoslari",           "Present Perfect: have/has + V3",    16,
         "I have visited London. She has eaten. Have you ever...? — 16 misol"),
    (2,  "Present Perfect vs Past Simple",     "Present Perfect vs Past Simple",     15,
         "I have lost my key. (hali ham yo'q) vs I lost my key yesterday. — 15 misol + farq"),
    (3,  "Past Continuous",                    "Past Continuous",                     15,
         "I was sleeping when he called. — 15 misol + present vs past continuous farqi"),
    (4,  "Conditional 0 va 1",                 "Zero & First Conditional",            16,
         "If you heat water, it boils. (0-tip, haqiqat)\n"
         "If I study hard, I will pass. (1-tip, real imkoniyat) — 16 misol"),
    (5,  "Conditional 2",                      "Second Conditional",                  15,
         "If I had more money, I would travel. (xayoliy holat) — 15 misol + qoida"),
    (6,  "Passive Voice asoslari",             "Passive Voice: Present & Past",       16,
         "The book is written by the author. / The car was stolen. — 16 misol"),
    (7,  "Reported Speech asoslari",           "Reported Speech",                     15,
         "She said, 'I am tired.' → She said she was tired. — 15 misol + backshift"),
    (8,  "Infinitive vs Gerund",               "Infinitive vs Gerund (-ing)",         16,
         "I want to go. (infinitive) / I enjoy swimming. (gerund) — 16 misol + qoidalar"),
    (9,  "Relative Clauses",                   "Relative Clauses: who/which/that",    15,
         "The man who called is my uncle. / The book that I read is interesting. — 15 misol"),
    (10, "Bog'lovchilar",                      "Linking Words & Connectors",          18,
         "However, although, because, therefore, moreover, furthermore, "
         "in addition, on the other hand, as a result, for example — 18 misol gap"),
]

B2_CURRICULUM = [
    (1,  "Advanced Conditionals",              "Mixed & Third Conditional",           15,
         "If I had studied harder, I would have passed. (3-tip) — 15 misol"),
    (2,  "Advanced Passive",                   "Passive Voice: All Tenses",           15,
         "The project is being reviewed. / It has been decided. — 15 misol"),
    (3,  "Sof akademik lug'at",                "Academic Vocabulary Set 1",           20,
         "Analyse, evaluate, demonstrate, significant, contrast, approach, "
         "concept, context, data, evidence, identify, indicate, interpret, "
         "method, obtain, positive, potential, process, require, source — 20 ta"),
    (4,  "Idiomalar 1",                        "Common English Idioms Set 1",         16,
         "Break a leg, hit the nail on the head, under the weather, "
         "piece of cake, bite the bullet, cost an arm and a leg, "
         "burn the midnight oil, let the cat out of the bag, "
         "once in a blue moon, kill two birds with one stone — 16 ta idioma"),
    (5,  "Kolokatsiyalar",                     "Common Collocations",                 18,
         "Make a decision/mistake/effort / Do homework/research/damage / "
         "Take a photo/break/risk / Have a meeting/dream/headache — 18 ta"),
]

ALL_CURRICULUM = {
    "A1": A1_CURRICULUM,
    "A2": A2_CURRICULUM,
    "B1": B1_CURRICULUM,
    "B2": B2_CURRICULUM,
}

LEVEL_DAY_COUNT = {lvl: len(cur) for lvl, cur in ALL_CURRICULUM.items()}


def get_topic_for_day(level: str, day_number: int) -> dict | None:
    curriculum = ALL_CURRICULUM.get(level, [])
    if not curriculum:
        return None
    # day_number is 1-based; repeat last topic if beyond curriculum
    idx = min(day_number - 1, len(curriculum) - 1)
    day, name_uz, name_en, min_items, instructions = curriculum[idx]
    return {
        "day": day,
        "name_uz": name_uz,
        "name_en": name_en,
        "min_items": min_items,
        "instructions": instructions,
    }


def days_remaining_to_next_level(level: str, completed_days: int) -> int:
    total = LEVEL_DAY_COUNT.get(level, 20)
    return max(0, total - completed_days)
