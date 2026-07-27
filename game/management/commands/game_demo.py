"""Chaqmoq Game uchun boshlang'ich ma'lumot: robotlar, tariflar, do'kon, savollar.

Ishlatish:
    python manage.py game_demo

Mavjud yozuvlarni ikkilantirmaydi — qayta ishga tushirsa ham xavfsiz.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Center
from game.models import (
    GameProfile,
    NewsPost,
    Question,
    QuestionCategory,
    ShopItem,
    Tarif,
)

User = get_user_model()


# ─── Tariflar (foydalanuvchi bergan narxlar) ───────────────────
# (nom, narx, kun, jon_soni, jon_soat, oyin_qulf_soat, bonus_foiz, izoh)
#
# Bepul reja: 3 jon / 8 soat, o'yin 24 soatda ochiladi.
# Tarif ikkala kutishni ham qisqartiradi — faqat jonni tezlashtirish
# o'quvchiga deyarli hech narsa bermaydi (o'yinlar soni cheklangan).
TARIFLAR = [
    ("Tezkor", 10_000, 7, 3, 5, 12, 0,
     "Jonlar 5 soatda, o'yinlar 12 soatda ochiladi"),
    ("Pro", 15_000, 7, 3, 2, 6, 25,
     "Jonlar 2 soatda, o'yinlar 6 soatda + 25% chaqmoq"),
    ("Pro oylik", 45_000, 30, 3, 2, 6, 25,
     "Pro bilan bir xil, lekin bir oy — arzonroq chiqadi"),
    ("Chempion", 30_000, 7, 5, 2, 4, 50,
     "5 jon, o'yinlar 4 soatda + 50% chaqmoq"),
]

# ─── 50 ta robot ───────────────────────────────────────────────
ROBOT_ISMLARI = [
    "Diyorbek", "Malika", "Jasur", "Kamola", "Sardor", "Nodira", "Aziz",
    "Shahnoza", "Bekzod", "Zilola", "Otabek", "Madina", "Javohir", "Sevara",
    "Ulug'bek", "Dilnoza", "Sanjar", "Gulnora", "Temur", "Feruza",
    "Islom", "Nilufar", "Doniyor", "Shaxzoda", "Rustam", "Oysha", "Farrux",
    "Mohira", "Akmal", "Zarina", "Bobur", "Lola", "Shohruh", "Umida",
    "Alisher", "Nargiza", "Davron", "Sabina", "Muhammad", "Dilfuza",
    "Anvar", "Kamila", "Sherzod", "Aziza", "Ilhom", "Ruxshona",
    "Jahongir", "Munisa", "Sohib", "Charos",
]

# ─── Do'kon (admin keyin o'zgartiradi) ─────────────────────────
DOKON = [
    ("Qo'shimcha jon (3 ta)", "Darhol 3 ta jon qo'shiladi", ShopItem.TUR_JON, "5.0", 3, -1),
    ("Oltin ramka", "Profilingiz atrofida oltin ramka", ShopItem.TUR_RAMKA, "20.0", 0, -1),
    ("Olmos ramka", "Eng nufuzli ramka", ShopItem.TUR_RAMKA, "50.0", 0, -1),
    ("Chaqmoq avatar", "Maxsus chaqmoq avatari", ShopItem.TUR_AVATAR, "15.0", 0, -1),
    ("Chaqmoq ruchka", "Markazdan olib ketiladigan ruchka", ShopItem.TUR_ASSESUAR, "30.0", 0, 20),
    ("Chaqmoq bloknot", "Markazdan olib ketiladigan bloknot", ShopItem.TUR_ASSESUAR, "45.0", 0, 15),
    ("Chaqmoq futbolka", "Brendlangan futbolka", ShopItem.TUR_ASSESUAR, "150.0", 0, 5),
]

# ─── Savollar (duelda 10 ta kerak, shuning uchun zaxira ko'p) ──
SAVOLLAR = {
    "Mevalar (A1)": [
        ("apple", "olma", ["nok", "uzum", "shaftoli"]),
        ("grape", "uzum", ["olma", "banan", "anor"]),
        ("peach", "shaftoli", ["nok", "olcha", "qulupnay"]),
        ("watermelon", "tarvuz", ["qovun", "qovoq", "bodring"]),
        ("cherry", "olcha", ["anor", "behi", "o'rik"]),
        ("pear", "nok", ["olma", "uzum", "limon"]),
        ("strawberry", "qulupnay", ["malina", "olcha", "anjir"]),
        ("lemon", "limon", ["apelsin", "mandarin", "anor"]),
        ("apricot", "o'rik", ["shaftoli", "olcha", "behi"]),
        ("melon", "qovun", ["tarvuz", "qovoq", "sabzi"]),
    ],
    "Ranglar (A1)": [
        ("red", "qizil", ["ko'k", "yashil", "sariq"]),
        ("blue", "ko'k", ["qizil", "oq", "qora"]),
        ("green", "yashil", ["sariq", "jigarrang", "kulrang"]),
        ("yellow", "sariq", ["qizil", "pushti", "binafsha"]),
        ("black", "qora", ["oq", "kulrang", "ko'k"]),
        ("white", "oq", ["qora", "sariq", "yashil"]),
        ("orange", "to'q sariq", ["qizil", "pushti", "ko'k"]),
        ("purple", "binafsha", ["pushti", "ko'k", "jigarrang"]),
    ],
    "Fe'llar (A2)": [
        ("to run", "yugurmoq", ["yurmoq", "sakramoq", "uxlamoq"]),
        ("to eat", "yemoq", ["ichmoq", "pishirmoq", "sotmoq"]),
        ("to write", "yozmoq", ["o'qimoq", "chizmoq", "gapirmoq"]),
        ("to buy", "sotib olmoq", ["sotmoq", "bermoq", "olmoq"]),
        ("to sleep", "uxlamoq", ["uyg'onmoq", "dam olmoq", "o'tirmoq"]),
        ("to listen", "tinglamoq", ["ko'rmoq", "aytmoq", "eshitmoq"]),
        ("to swim", "suzmoq", ["yugurmoq", "uchmoq", "sakramoq"]),
        ("to teach", "o'rgatmoq", ["o'rganmoq", "so'ramoq", "javob bermoq"]),
    ],
    "Oila (A1)": [
        ("mother", "ona", ["ota", "opa", "buvi"]),
        ("father", "ota", ["ona", "aka", "bobo"]),
        ("brother", "aka", ["opa", "singil", "amaki"]),
        ("sister", "opa", ["aka", "uka", "xola"]),
        ("grandmother", "buvi", ["bobo", "ona", "xola"]),
        ("son", "o'g'il", ["qiz", "ota", "nabira"]),
    ],
    "Hayvonlar (A1)": [
        ("cat", "mushuk", ["it", "sichqon", "quyon"]),
        ("dog", "it", ["mushuk", "bo'ri", "tulki"]),
        ("horse", "ot", ["eshak", "sigir", "tuya"]),
        ("cow", "sigir", ["qo'y", "echki", "ot"]),
        ("sheep", "qo'y", ["echki", "sigir", "tovuq"]),
        ("bird", "qush", ["baliq", "ari", "kapalak"]),
        ("fish", "baliq", ["qush", "ilon", "qurbaqa"]),
        ("bear", "ayiq", ["bo'ri", "sher", "tulki"]),
        ("wolf", "bo'ri", ["ayiq", "it", "tulki"]),
        ("rabbit", "quyon", ["sichqon", "mushuk", "olmaxon"]),
        ("chicken", "tovuq", ["o'rdak", "g'oz", "kurka"]),
        ("mouse", "sichqon", ["quyon", "mushuk", "kalamush"]),
    ],
    "Uy-ro'zg'or (A1)": [
        ("table", "stol", ["stul", "shkaf", "karavot"]),
        ("chair", "stul", ["stol", "divan", "eshik"]),
        ("door", "eshik", ["deraza", "devor", "shift"]),
        ("window", "deraza", ["eshik", "pol", "tom"]),
        ("bed", "karavot", ["divan", "stol", "gilam"]),
        ("kitchen", "oshxona", ["yotoqxona", "hammom", "zal"]),
        ("spoon", "qoshiq", ["vilka", "pichoq", "likopcha"]),
        ("knife", "pichoq", ["qoshiq", "vilka", "chelak"]),
        ("plate", "likopcha", ["stakan", "qozon", "choynak"]),
        ("cup", "piyola", ["likopcha", "qozon", "tovoq"]),
    ],
    "Maktab (A1)": [
        ("book", "kitob", ["daftar", "ruchka", "sumka"]),
        ("pen", "ruchka", ["qalam", "daftar", "kitob"]),
        ("pencil", "qalam", ["ruchka", "o'chirg'ich", "chizg'ich"]),
        ("teacher", "o'qituvchi", ["o'quvchi", "direktor", "ota-ona"]),
        ("student", "o'quvchi", ["o'qituvchi", "do'st", "qo'shni"]),
        ("lesson", "dars", ["tanaffus", "imtihon", "uy vazifa"]),
        ("homework", "uy vazifasi", ["dars", "imtihon", "kitob"]),
        ("school", "maktab", ["universitet", "bog'cha", "kutubxona"]),
        ("blackboard", "doska", ["devor", "deraza", "stol"]),
        ("exam", "imtihon", ["dars", "tanaffus", "bayram"]),
    ],
    "Ovqat (A1)": [
        ("bread", "non", ["guruch", "sut", "go'sht"]),
        ("water", "suv", ["sut", "choy", "sharbat"]),
        ("milk", "sut", ["suv", "qatiq", "asal"]),
        ("meat", "go'sht", ["baliq", "tuxum", "non"]),
        ("rice", "guruch", ["un", "makkajo'xori", "no'xat"]),
        ("egg", "tuxum", ["sut", "pishloq", "sariyog'"]),
        ("salt", "tuz", ["shakar", "qalampir", "sirka"]),
        ("sugar", "shakar", ["tuz", "asal", "un"]),
        ("tea", "choy", ["qahva", "suv", "sut"]),
        ("soup", "sho'rva", ["palov", "manti", "somsa"]),
    ],
    "Vaqt va kunlar (A2)": [
        ("Monday", "dushanba", ["seshanba", "yakshanba", "juma"]),
        ("Friday", "juma", ["shanba", "payshanba", "dushanba"]),
        ("Sunday", "yakshanba", ["shanba", "juma", "seshanba"]),
        ("morning", "ertalab", ["kechqurun", "tush", "kecha"]),
        ("evening", "kechqurun", ["ertalab", "tush", "yarim tun"]),
        ("yesterday", "kecha", ["bugun", "ertaga", "hozir"]),
        ("tomorrow", "ertaga", ["kecha", "bugun", "keyin"]),
        ("week", "hafta", ["oy", "yil", "kun"]),
        ("month", "oy", ["hafta", "yil", "kun"]),
        ("year", "yil", ["oy", "hafta", "asr"]),
    ],
    "Sifatlar (A2)": [
        ("big", "katta", ["kichik", "uzun", "og'ir"]),
        ("small", "kichik", ["katta", "keng", "baland"]),
        ("fast", "tez", ["sekin", "og'ir", "yengil"]),
        ("slow", "sekin", ["tez", "kuchli", "past"]),
        ("hot", "issiq", ["sovuq", "iliq", "quruq"]),
        ("cold", "sovuq", ["issiq", "iliq", "ho'l"]),
        ("easy", "oson", ["qiyin", "og'ir", "uzoq"]),
        ("difficult", "qiyin", ["oson", "yengil", "yaqin"]),
        ("beautiful", "chiroyli", ["xunuk", "katta", "eski"]),
        ("expensive", "qimmat", ["arzon", "yangi", "eski"]),
        ("strong", "kuchli", ["kuchsiz", "uzun", "yumshoq"]),
        ("clean", "toza", ["iflos", "quruq", "yangi"]),
    ],
    "Fe'llar (B1)": [
        ("achieve", "erishmoq", ["yo'qotmoq", "qidirmoq", "kutmoq"]),
        ("improve", "yaxshilamoq", ["buzmoq", "to'xtatmoq", "boshlamoq"]),
        ("decide", "qaror qilmoq", ["shubhalanmoq", "unutmoq", "so'ramoq"]),
        ("explain", "tushuntirmoq", ["so'ramoq", "yashirmoq", "eshitmoq"]),
        ("suggest", "taklif qilmoq", ["rad etmoq", "buyurmoq", "so'ramoq"]),
        ("prevent", "oldini olmoq", ["ruxsat bermoq", "yordam bermoq", "eslatmoq"]),
        ("increase", "oshirmoq", ["kamaytirmoq", "saqlamoq", "yopmoq"]),
        ("reduce", "kamaytirmoq", ["oshirmoq", "boshlamoq", "tugatmoq"]),
        ("describe", "tasvirlamoq", ["yashirmoq", "so'ramoq", "hisoblamoq"]),
        ("compare", "solishtirmoq", ["birlashtirmoq", "ajratmoq", "yopmoq"]),
    ],
    "Bo'shliqni to'ldiring (A2)": [
        ("I ___ a student.", "am", ["is", "are", "be"]),
        ("She ___ to school every day.", "goes", ["go", "going", "gone"]),
        ("They ___ playing football now.", "are", ["is", "am", "be"]),
        ("He ___ finished his homework.", "has", ["have", "had", "having"]),
        ("We ___ TV yesterday.", "watched", ["watch", "watches", "watching"]),
        ("There ___ many books here.", "are", ["is", "am", "was"]),
        ("I ___ never been to London.", "have", ["has", "had", "am"]),
        ("If it rains, I ___ stay home.", "will", ["would", "was", "am"]),
        ("She is taller ___ me.", "than", ["then", "that", "as"]),
        ("This book is ___ interesting.", "very", ["much", "many", "too much"]),
    ],
}

YANGILIKLAR = [
    (
        "Chaqmoq Game ishga tushdi! ⚡",
        "Endi ingliz tilini duel orqali o'rganing. Har kuni 3 ta bepul duel, "
        "streak yig'ing va guruhingizda birinchi bo'ling.",
        NewsPost.TUR_YANGILIK,
        True,
    ),
    (
        "Chaqmoq yig'ing va do'kondan xarid qiling",
        "Har duelda aniqligingizga qarab chaqmoq olasiz: 10/10 — 3 chaqmoq, "
        "8-9 ta — 2 chaqmoq, 5-7 ta — 1 chaqmoq. Do'konda ularni sovg'alarga almashtiring.",
        NewsPost.TUR_ELON,
        False,
    ),
]


class Command(BaseCommand):
    help = "Chaqmoq Game uchun boshlang'ich ma'lumot yaratadi"

    def handle(self, *args, **options):
        center = Center.objects.first()
        if center is None:
            center = Center.objects.create(name="Demo markaz", slug="demo")
            self.stdout.write(self.style.SUCCESS(f"Markaz yaratildi: {center}"))

        # ─── Demo o'quvchi ───────────────────────────────────────
        student, created = User.objects.get_or_create(
            email="oquvchi@chaqmoq.uz",
            defaults={"ism": "Diyorbek", "familya": "Test", "role": "student", "center": center},
        )
        if created:
            student.set_password("chaqmoq123")
            student.save()
            self.stdout.write(self.style.SUCCESS("O'quvchi: oquvchi@chaqmoq.uz / chaqmoq123"))

        # ─── Tariflar ────────────────────────────────────────────
        for tartib, (
            nom, narx, kun, jon, soat, qulf, bonus, izoh
        ) in enumerate(TARIFLAR):
            Tarif.objects.get_or_create(
                nom=nom,
                defaults={
                    "narx_som": narx, "kun": kun, "jon_soni": jon,
                    "soat": soat, "oyin_qulf_soat": qulf,
                    "chaqmoq_bonus_foiz": bonus,
                    "izoh": izoh, "tartib": tartib,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Tariflar: {Tarif.objects.count()} ta"))

        # ─── 50 ta robot ─────────────────────────────────────────
        # Har robotning mahorati har xil (0.50–0.90) — shunda ular
        # 10 ta savoldan o'rtacha 5–9 tasiga to'g'ri javob beradi.
        #
        # Muhim: har robotga login qila OLMAYDIGAN hisob (User) biriktiramiz.
        # Sababi — foydalanuvchi robotga ham do'stlik yubora olishi kerak,
        # do'stlik esa User orasida bo'ladi. Robot foydalanuvchiga oddiy
        # o'yinchi kabi ko'rinadi (ilovada "robot" belgisi ko'rsatilmaydi).
        yangi_robot = 0
        for i, ism in enumerate(ROBOT_ISMLARI):
            robot, created = GameProfile.objects.get_or_create(
                robot=True,
                robot_ism=ism,
                defaults={
                    "center": None,  # umumiy — barcha markazlarga raqib bo'ladi
                    "maxorat": round(random.uniform(0.50, 0.90), 2),
                    "xp": random.randint(0, 400),
                    "hafta_xp": random.randint(0, 250),
                    "chaqmoq": Decimal(str(round(random.uniform(0, 40), 1))),
                },
            )
            yangi_robot += int(created)

            # Robotga login qila olmaydigan hisob biriktiramiz.
            if robot.user_id is None:
                bot_user, _ = User.objects.get_or_create(
                    email=f"bot{i + 1}@chaqmoq.game",
                    defaults={
                        "ism": ism,
                        "familya": "",
                        "role": "student",
                        "is_active": False,  # login qila olmaydi
                    },
                )
                robot.user = bot_user
                robot.save(update_fields=["user"])

        for robot in GameProfile.objects.filter(robot=True):
            robot.liga_yangila()
            robot.save(update_fields=["liga"])

        self.stdout.write(self.style.SUCCESS(
            f"Robotlar: {GameProfile.objects.filter(robot=True).count()} ta "
            f"({yangi_robot} ta yangi, hisob bilan)"
        ))

        # ─── Do'kon ──────────────────────────────────────────────
        for tartib, (nom, izoh, tur, narx, jon, zaxira) in enumerate(DOKON):
            ShopItem.objects.get_or_create(
                nom=nom,
                defaults={
                    "izoh": izoh, "tur": tur, "narx_chaqmoq": Decimal(narx),
                    "beradigan_jon": jon, "zaxira": zaxira, "tartib": tartib,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Do'kon: {ShopItem.objects.count()} ta mahsulot"))

        # ─── Savollar ────────────────────────────────────────────
        yangi_savol = 0
        for kategoriya_nomi, savollar in SAVOLLAR.items():
            daraja = kategoriya_nomi[-3:-1]
            kategoriya, _ = QuestionCategory.objects.get_or_create(
                nom=kategoriya_nomi,
                defaults={"daraja": daraja, "center": None},
            )
            for savol, togri, notogrilar in savollar:
                # Gap ichida "___" bo'lsa — bu bo'shliqni to'ldirish savoli.
                tur = Question.TUR_BOSHLIQ if "___" in savol else Question.TUR_TARJIMA
                _, created = Question.objects.get_or_create(
                    savol=savol,
                    kategoriya=kategoriya,
                    defaults={
                        "tur": tur,
                        "togri_javob": togri,
                        "notogri_1": notogrilar[0],
                        "notogri_2": notogrilar[1],
                        "notogri_3": notogrilar[2],
                        "center": None,
                    },
                )
                yangi_savol += int(created)

        self.stdout.write(self.style.SUCCESS(
            f"Savollar: {Question.objects.count()} ta ({yangi_savol} ta yangi)"
        ))

        # ─── Yangiliklar ─────────────────────────────────────────
        for sarlavha, matn, tur, muhim in YANGILIKLAR:
            NewsPost.objects.get_or_create(
                sarlavha=sarlavha,
                defaults={"matn": matn, "tur": tur, "muhim": muhim, "center": None},
            )

        self.stdout.write(self.style.SUCCESS("Tayyor."))
