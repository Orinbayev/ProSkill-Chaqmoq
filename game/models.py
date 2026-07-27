"""Chaqmoq Game — o'quvchilar uchun ingliz tili so'z dueli o'yini.

Ma'lumot (savollar, yangiliklar, do'kon, tariflar) ChaqmoqApp admin panelidan
kiritiladi, mobil ilova esa `/api/mobile/game/` endpointlari orqali o'qiydi.

Muhim: o'yin **chaqmog'i** ChaqmoqApp'ning chaqmoq/Ledger balansidan
BUTUNLAY ALOHIDA. ChaqmoqApp o'quvchisi ham o'yinda 0 dan boshlaydi.
Bu ataylab — o'yin iqtisodiyoti markaz iqtisodiyotiga tegmasligi kerak.

Tenant izolyatsiyasi: `center=None` — barcha markazlarga ko'rinadi.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.soft_delete import SoftDeleteMixin

from .engines import MOTOR_CHOICES, Motor, motor_ol


DARAJA_CHOICES = [
    ("A1", "A1 — Boshlang'ich"),
    ("A2", "A2 — Elementar"),
    ("B1", "B1 — O'rta"),
    ("B2", "B2 — O'rtadan yuqori"),
    ("C1", "C1 — Ilg'or"),
]

# ═══════════════════════════════════════════════════════════════
# O'YIN QOIDALARI — barcha raqamlar shu yerda, bitta joyda
# ═══════════════════════════════════════════════════════════════

# Bitta duelda nechta savol.
SAVOLLAR_SONI = 10

# Bitta savolga beriladigan vaqt (mobil ilovadagi taymer bilan bir xil).
SAVOL_SONIYA = 10

# ─── Bepul reja ────────────────────────────────────────────────
#
# Jonlar har `BEPUL_JON_SOAT` soatda `BEPUL_JON` taga tiklanadi.
# Har jon — bitta o'yin. O'ynalgan o'yin `BEPUL_OYIN_QULF_SOAT` soatga
# qulflanadi, ya'ni o'quvchi bitta o'yinni takrorlab chaqmoq yig'a olmaydi —
# jonlarini turli o'yinlarga sarflashi kerak.

BEPUL_JON = 3
BEPUL_JON_SOAT = 8
BEPUL_OYIN_QULF_SOAT = 24


# ─── Chaqmoq mukofoti ──────────────────────────────────────────
#
# Mukofot **aniqlik foizidan** hisoblanadi, shuning uchun 5 savolli o'yin ham,
# 40 savolli o'yin ham bir xil adolat bilan baholanadi.
#
#   100%      → +5
#   75–99%    → +3
#   50–74%    → +2
#   30–49%    →  0
#   30% dan past → −1 (jarima: tavakkaliga bosishning ma'nosi qolmaydi)

CHAQMOQ_NARVONI: list[tuple[float, Decimal]] = [
    (1.00, Decimal("5")),
    (0.75, Decimal("3")),
    (0.50, Decimal("2")),
    (0.30, Decimal("0")),
]
CHAQMOQ_JARIMA = Decimal("-1")


def chaqmoq_aniqlik_boyicha(aniqlik: float) -> Decimal:
    """Aniqlik ulushi (0..1) → chaqmoq. Manfiy qiymat — jarima."""
    for chegara, mukofot in CHAQMOQ_NARVONI:
        if aniqlik >= chegara:
            return mukofot
    return CHAQMOQ_JARIMA


def mukofotni_olchash(baza: Decimal, koef: Decimal) -> Decimal:
    """O'yinning chaqmoq koeffitsiyentini qo'llaydi.

    Koeffitsiyent faqat **mukofotga** ta'sir qiladi. Jarima har doim aniq
    −1 bo'lib qoladi: jazo o'quvchi qaysi o'yinni tanlaganiga bog'liq
    bo'lmasligi kerak.
    """
    if baza < 0:
        return baza
    return (baza * koef).quantize(Decimal("0.1"))


def chaqmoq_mukofoti(togri_javoblar: int, jami: int = SAVOLLAR_SONI) -> Decimal:
    """To'g'ri javoblar soniga qarab chaqmoq (narvonning qulay ko'rinishi)."""
    if jami <= 0:
        return Decimal("0")
    return chaqmoq_aniqlik_boyicha(togri_javoblar / jami)


# ═══════════════════════════════════════════════════════════════
# KONTENT — admin paneldan kiritiladi
# ═══════════════════════════════════════════════════════════════

class QuestionCategory(SoftDeleteMixin, models.Model):
    """Savollar to'plami, masalan "Mevalar (A1)"."""

    nom = models.CharField("Nomi", max_length=120)
    daraja = models.CharField("Daraja", max_length=2, choices=DARAJA_CHOICES, default="A1")
    izoh = models.TextField("Izoh", blank=True)
    tartib = models.PositiveIntegerField("Tartib", default=0)
    faol = models.BooleanField("Faol", default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz (bo'sh = umumiy)",
    )

    class Meta:
        verbose_name = "Savollar to'plami"
        verbose_name_plural = "Savollar to'plamlari"
        ordering = ["tartib", "daraja", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.daraja})"

    @property
    def savollar_soni(self) -> int:
        return self.questions.filter(faol=True).count()


class Question(SoftDeleteMixin, models.Model):
    """Bitta duel savoli. To'g'ri javob + 3 ta chalg'ituvchi variant."""

    TUR_TARJIMA = "tarjima"
    TUR_ESHITISH = "eshitish"
    TUR_BOSHLIQ = "boshliq"
    TUR_RASM = "rasm"

    TUR_CHOICES = [
        (TUR_TARJIMA, "Tarjima — so'zning ma'nosini toping"),
        (TUR_ESHITISH, "Eshitish — audioni tinglang"),
        (TUR_BOSHLIQ, "Bo'shliq — gapni to'ldiring"),
        (TUR_RASM, "Rasm — rasmdagi narsani toping"),
    ]

    kategoriya = models.ForeignKey(
        QuestionCategory,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="To'plam",
    )
    tur = models.CharField("Savol turi", max_length=16, choices=TUR_CHOICES, default=TUR_TARJIMA)

    savol = models.CharField(
        "Savol matni",
        max_length=255,
        help_text="Masalan: «apple» yoki «I ___ a student»",
    )
    togri_javob = models.CharField("To'g'ri javob", max_length=120)
    notogri_1 = models.CharField("Noto'g'ri variant 1", max_length=120)
    notogri_2 = models.CharField("Noto'g'ri variant 2", max_length=120)
    notogri_3 = models.CharField("Noto'g'ri variant 3", max_length=120)

    audio = models.FileField("Audio (eshitish savoli uchun)", upload_to="game/audio/", blank=True, null=True)
    rasm = models.ImageField("Rasm (rasm savoli uchun)", upload_to="game/rasm/", blank=True, null=True)

    izoh = models.CharField(
        "Qoida / izoh",
        max_length=255,
        blank=True,
        help_text="Javobdan keyin o'quvchiga ko'rsatiladi",
    )
    faol = models.BooleanField("Faol", default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz (bo'sh = umumiy)",
    )

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["-yaratilgan"]
        indexes = [models.Index(fields=["faol", "center"])]

    def __str__(self):
        return f"{self.savol} → {self.togri_javob}"

    def variantlar(self) -> list[str]:
        """4 ta variant, aralashtirilgan holda."""
        options = [self.togri_javob, self.notogri_1, self.notogri_2, self.notogri_3]
        random.shuffle(options)
        return options


class NewsPost(SoftDeleteMixin, models.Model):
    """O'yin ichidagi yangiliklar / e'lonlar."""

    TUR_YANGILIK = "yangilik"
    TUR_ELON = "elon"
    TUR_YANGILANISH = "yangilanish"
    TUR_TURNIR = "turnir"

    TUR_CHOICES = [
        (TUR_YANGILIK, "Yangilik"),
        (TUR_ELON, "E'lon"),
        (TUR_YANGILANISH, "Ilova yangilanishi"),
        (TUR_TURNIR, "Turnir"),
    ]

    sarlavha = models.CharField("Sarlavha", max_length=160)
    matn = models.TextField("Matn")
    tur = models.CharField("Turi", max_length=16, choices=TUR_CHOICES, default=TUR_YANGILIK)
    rasm = models.ImageField("Rasm", upload_to="game/yangiliklar/", blank=True, null=True)

    muhim = models.BooleanField("Muhim", default=False, help_text="Bosh ekranda tepada ko'rsatiladi")
    faol = models.BooleanField("Faol", default=True)
    chop_etilgan = models.DateTimeField("Chop etilgan sana", default=timezone.now)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz (bo'sh = umumiy)",
    )

    class Meta:
        verbose_name = "Yangilik"
        verbose_name_plural = "Yangiliklar"
        ordering = ["-muhim", "-chop_etilgan"]

    def __str__(self):
        return self.sarlavha


# ═══════════════════════════════════════════════════════════════
# TARIFLAR — admin paneldan boshqariladi
# ═══════════════════════════════════════════════════════════════

class Tarif(models.Model):
    """Pullik reja — o'yinni tezlashtiradi.

    Ikkita mustaqil kutish bor va tarif ikkalasini ham qisqartira oladi:

      • `soat`            — jonlar necha soatda `jon_soni` taga tiklanadi
                            (bepulda 8 soat / 3 jon),
      • `oyin_qulf_soat`  — o'ynalgan o'yin qayta ochilishi
                            (bepulda 24 soat).

    Ikkinchisi muhim: 6 ta o'yin bo'lsa, 24 soatlik qulf kuniga 6 ta o'yin bilan
    cheklaydi — faqat jonni tezlashtirish deyarli hech narsa bermaydi.
    """

    nom = models.CharField("Nomi", max_length=80)
    narx_som = models.PositiveIntegerField("Narxi (so'm)")
    kun = models.PositiveSmallIntegerField("Muddati (kun)")

    jon_soni = models.PositiveSmallIntegerField("Bir tiklanishda nechta jon", default=3)
    soat = models.PositiveSmallIntegerField(
        "Jonlar necha soatda tiklanadi",
        help_text=f"Bepul rejada {BEPUL_JON_SOAT} soat.",
    )
    oyin_qulf_soat = models.PositiveSmallIntegerField(
        "O'ynalgan o'yin necha soatdan keyin ochiladi",
        default=BEPUL_OYIN_QULF_SOAT,
        help_text=f"Bepul rejada {BEPUL_OYIN_QULF_SOAT} soat. 0 = qulflanmaydi.",
    )
    chaqmoq_bonus_foiz = models.PositiveSmallIntegerField(
        "Chaqmoq bonusi (%)",
        default=0,
        help_text="Har o'yindan olinadigan chaqmoq shuncha foizga ko'payadi. "
        "Masalan 50 → 4 chaqmoq o'rniga 6. Jarima bonussiz qoladi.",
    )

    izoh = models.CharField("Izoh", max_length=160, blank=True)
    tartib = models.PositiveSmallIntegerField("Tartib", default=0)
    faol = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Tariflar"
        ordering = ["tartib", "narx_som"]

    def __str__(self):
        return f"{self.nom} — {self.narx_som:,} so'm / {self.kun} kun".replace(",", " ")

    @property
    def tavsif(self) -> str:
        qismlar = [f"Har {self.soat} soatda {self.jon_soni} ta jon"]
        if self.oyin_qulf_soat != BEPUL_OYIN_QULF_SOAT:
            qismlar.append(f"o'yin {self.oyin_qulf_soat} soatda ochiladi")
        if self.chaqmoq_bonus_foiz:
            qismlar.append(f"+{self.chaqmoq_bonus_foiz}% chaqmoq")
        return " · ".join(qismlar)

    @property
    def haftalik_narx(self) -> int:
        """Taqqoslash uchun haftaga keltirilgan narx."""
        if self.kun <= 0:
            return self.narx_som
        return round(self.narx_som * 7 / self.kun)


class Obuna(models.Model):
    """O'quvchining faol tarifi."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_obunalar",
        verbose_name="O'quvchi",
    )
    tarif = models.ForeignKey(Tarif, on_delete=models.PROTECT, verbose_name="Tarif")

    boshlangan = models.DateTimeField("Boshlangan", default=timezone.now)
    tugaydi = models.DateTimeField("Tugaydi")

    # To'lov hali ulanmagan — admin qo'lda tasdiqlaydi yoki markaz sotib oladi.
    tolangan = models.BooleanField("To'langan", default=False)
    izoh = models.CharField("Izoh", max_length=160, blank=True)

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"
        ordering = ["-boshlangan"]

    def __str__(self):
        return f"{self.user} — {self.tarif.nom}"

    @property
    def faol(self) -> bool:
        return self.tolangan and self.tugaydi > timezone.now()


class TarifSorovi(models.Model):
    """Tarif sotib olish so'rovi.

    Ikki yo'l bor: Click orqali avtomatik (to'lov tasdiqlanishi bilan obuna
    yoqiladi) yoki naqd — o'quvchi markazga to'laydi, admin panelda tasdiqlaydi.
    """

    USUL_CLICK = "click"
    USUL_NAQD = "naqd"

    USUL_CHOICES = [
        (USUL_CLICK, "Click (onlayn)"),
        (USUL_NAQD, "Naqd / qo'lda tasdiqlash"),
    ]

    HOLAT_KUTILMOQDA = "kutilmoqda"
    HOLAT_TOLANGAN = "tolangan"
    HOLAT_BEKOR = "bekor"

    HOLAT_CHOICES = [
        (HOLAT_KUTILMOQDA, "To'lov kutilmoqda"),
        (HOLAT_TOLANGAN, "To'landi"),
        (HOLAT_BEKOR, "Bekor qilindi"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_tarif_sorovlari",
        verbose_name="O'quvchi",
    )
    tarif = models.ForeignKey(Tarif, on_delete=models.PROTECT, verbose_name="Tarif")
    center = models.ForeignKey(
        "accounts.Center", on_delete=models.SET_NULL, null=True, blank=True
    )

    usul = models.CharField("To'lov usuli", max_length=8, choices=USUL_CHOICES)
    holat = models.CharField(
        "Holat", max_length=12, choices=HOLAT_CHOICES, default=HOLAT_KUTILMOQDA
    )
    # Narx so'rov yaratilgan lahzada muzlatiladi — keyin tarif narxi
    # o'zgarsa ham o'quvchi ko'rgan summa o'zgarmaydi.
    narx_som = models.PositiveIntegerField("Summa (so'm)")

    # Click to'lovi bilan bog'lash uchun (billing.PaymentTransaction.transaction_id).
    transaction_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    izoh = models.CharField("Izoh", max_length=200, blank=True)
    obuna = models.ForeignKey(
        Obuna,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sorovlar",
        verbose_name="Yoqilgan obuna",
    )

    yaratilgan = models.DateTimeField(auto_now_add=True)
    tasdiqlangan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Tarif so'rovi"
        verbose_name_plural = "Tarif so'rovlari"
        ordering = ["-yaratilgan"]
        indexes = [models.Index(fields=["holat", "-yaratilgan"])]

    def __str__(self):
        return f"{self.user} → {self.tarif.nom} ({self.holat})"


# ═══════════════════════════════════════════════════════════════
# O'YINCHI (odam ham, robot ham)
# ═══════════════════════════════════════════════════════════════

LIGA_CHOICES = [
    ("bronza", "Bronza"),
    ("kumush", "Kumush"),
    ("oltin", "Oltin"),
    ("olmos", "Olmos"),
]


class GameProfile(models.Model):
    """O'yinchi: jon, XP, chaqmoq, streak, liga.

    Robotlar ham shu jadvalda yashaydi (`robot=True`, `user=None`) — shuning
    uchun ular reytingda odamlar bilan bir qatorda ko'rinadi va chaqmoq yig'adi.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_profile",
        null=True,
        blank=True,
        verbose_name="Foydalanuvchi (robot uchun bo'sh)",
    )

    # ─── Robot ──────────────────────────────────────────────────
    robot = models.BooleanField("Robot", default=False)
    robot_ism = models.CharField("Robot ismi", max_length=60, blank=True, default="")
    maxorat = models.FloatField(
        "Mahorat (0.5–0.9)",
        default=0.7,
        help_text="Robot 10 ta savoldan o'rtacha shuncha ulushiga to'g'ri javob beradi",
    )

    avatar = models.ImageField("Avatar", upload_to="game/avatar/", blank=True, null=True)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz",
    )

    xp = models.PositiveIntegerField("Jami XP", default=0)
    hafta_xp = models.PositiveIntegerField("Shu haftadagi XP", default=0)

    chaqmoq = models.DecimalField(
        "Chaqmoq",
        max_digits=9,
        decimal_places=1,
        default=Decimal("0.0"),
        help_text="O'yin valyutasi. ChaqmoqApp balansidan alohida.",
    )

    jon = models.PositiveSmallIntegerField("Jon", default=BEPUL_JON)
    jon_yangilangan = models.DateTimeField("Jon oxirgi tiklangan vaqt", default=timezone.now)
    jon_kuni = models.DateField("Jon oxirgi tiklangan kun", null=True, blank=True)

    streak_kun = models.PositiveIntegerField("Streak (kun)", default=0)
    oxirgi_oyin_kuni = models.DateField("Oxirgi o'ynagan kun", null=True, blank=True)

    liga = models.CharField("Liga", max_length=10, choices=LIGA_CHOICES, default="bronza")

    # Onlayn holatni aniqlash uchun — har API so'rovda yangilanadi.
    oxirgi_faol = models.DateTimeField("Oxirgi faollik", null=True, blank=True)

    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O'yinchi"
        verbose_name_plural = "O'yinchilar"
        ordering = ["-hafta_xp"]
        indexes = [
            models.Index(fields=["robot", "hafta_xp"]),
            models.Index(fields=["oxirgi_faol"]),
        ]

    # Foydalanuvchi oxirgi shuncha daqiqa ichida faol bo'lsa — onlayn.
    ONLAYN_DAQIQA = 5

    @property
    def onlayn(self) -> bool:
        # Robotlar doim "onlayn" ko'rinadi — o'yin jonli tuyulishi uchun.
        if self.robot:
            return True
        if self.oxirgi_faol is None:
            return False
        return self.oxirgi_faol > timezone.now() - timezone.timedelta(minutes=self.ONLAYN_DAQIQA)

    def __str__(self):
        return f"{self.nomi} — {self.xp} XP"

    @property
    def nomi(self) -> str:
        if self.robot:
            return self.robot_ism or "Robot"
        if self.user is None:
            return "?"
        return self.user.ism or self.user.get_full_name() or self.user.email

    # ─── Obuna ──────────────────────────────────────────────────

    @property
    def obuna(self) -> Obuna | None:
        """Faol obuna, bo'lmasa None.

        Natija shu obyekt umri davomida keshlanadi. Sababi: `pro`, `max_jon`,
        `joriy_jon` va `keyingi_jon_soniya` — hammasi shu yerga murojaat qiladi,
        keshsiz esa bitta katalog so'rovida har o'yin uchun bir necha marta
        bazaga borilardi (N+1). Obuna so'rov o'rtasida o'zgarmaydi; agar
        o'zgartirsangiz `keshni_tozala()` chaqiring.
        """
        if self.user is None:
            return None
        if not hasattr(self, "_obuna_kesh"):
            self._obuna_kesh = (
                Obuna.objects
                .filter(user=self.user, tolangan=True, tugaydi__gt=timezone.now())
                .select_related("tarif")
                .order_by("-tugaydi")
                .first()
            )
        return self._obuna_kesh

    def keshni_tozala(self) -> None:
        """Obuna o'zgargandan keyin chaqiriladi."""
        if hasattr(self, "_obuna_kesh"):
            del self._obuna_kesh

    @property
    def pro(self) -> bool:
        return self.obuna is not None

    @property
    def max_jon(self) -> int:
        obuna = self.obuna
        return obuna.tarif.jon_soni if obuna else BEPUL_JON

    @property
    def jon_soat(self) -> int:
        """Jonlar necha soatda tiklanadi."""
        obuna = self.obuna
        return obuna.tarif.soat if obuna else BEPUL_JON_SOAT

    @property
    def oyin_qulf_soat(self) -> int:
        """O'ynalgan o'yin necha soatdan keyin qayta ochiladi."""
        obuna = self.obuna
        return obuna.tarif.oyin_qulf_soat if obuna else BEPUL_OYIN_QULF_SOAT

    @property
    def chaqmoq_bonus_foiz(self) -> int:
        obuna = self.obuna
        return obuna.tarif.chaqmoq_bonus_foiz if obuna else 0

    # ─── Jonlar ─────────────────────────────────────────────────
    #
    # Jonlar "yotgan" holatda saqlanadi va faqat o'qilganda tiklanadi
    # (lazy regeneration) — cron yoki fon vazifasi kerak emas.
    #
    # Bepul reja ham, pullik ham bir xil qoida bo'yicha ishlaydi:
    # har `jon_soat` soatda `max_jon` taga tiklanadi. Farq faqat raqamlarda.

    def _tikla(self) -> None:
        maks = self.max_jon
        if self.jon >= maks:
            # To'la turganda taymer yurmaydi — sarflangan lahzadan boshlanadi.
            self.jon_yangilangan = timezone.now()
            return

        oraliq = timezone.timedelta(hours=self.jon_soat)
        if oraliq <= timezone.timedelta(0):
            self.jon = maks
            self.jon_yangilangan = timezone.now()
            return

        o_tgan = timezone.now() - self.jon_yangilangan
        marta = int(o_tgan / oraliq)
        if marta <= 0:
            return

        # Har tiklanishda jonlar to'liq to'ladi — "har 8 soatda 3 ta jon".
        self.jon = maks
        self.jon_yangilangan = timezone.now()

    @property
    def joriy_jon(self) -> int:
        self._tikla()
        return self.jon

    def keyingi_jon_soniya(self) -> int:
        """Keyingi tiklanishgacha necha soniya. 0 = kutish shart emas."""
        if self.joriy_jon >= self.max_jon:
            return 0
        keyingi = self.jon_yangilangan + timezone.timedelta(hours=self.jon_soat)
        return max(0, int((keyingi - timezone.now()).total_seconds()))

    def jon_sarfla(self) -> bool:
        """Bitta jonni sarflaydi. Jon yetmasa False."""
        if self.joriy_jon <= 0:
            self.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
            return False
        if self.jon >= self.max_jon:
            # To'la holatdan pastga tushdik — taymer shu lahzadan boshlanadi.
            self.jon_yangilangan = timezone.now()
        self.jon -= 1
        self.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])
        return True

    # ─── Chaqmoq ────────────────────────────────────────────────

    def chaqmoq_qosh(self, miqdor: Decimal) -> Decimal:
        """Chaqmoq qo'shadi (yoki jarima yechadi) va haqiqiy o'zgarishni qaytaradi.

        • Musbat mukofotga tarif bonusi qo'shiladi.
        • Jarima bonussiz qoladi — aks holda tarif jazoni ham "kuchaytirar" edi.
        • Balans hech qachon manfiy bo'lmaydi: 0 da turgan o'quvchidan
          yechib olinmaydi.
        """
        if miqdor > 0 and self.chaqmoq_bonus_foiz:
            miqdor = (miqdor * (100 + self.chaqmoq_bonus_foiz) / 100).quantize(
                Decimal("0.1")
            )

        joriy = self.chaqmoq or Decimal("0.0")
        yangi = joriy + miqdor
        if yangi < 0:
            yangi = Decimal("0.0")

        haqiqiy = yangi - joriy
        self.chaqmoq = yangi
        return haqiqiy

    def jon_qoshi(self, soni: int = 1) -> None:
        self.jon = min(self.max_jon, self.joriy_jon + soni)
        self.save(update_fields=["jon", "jon_yangilangan", "jon_kuni"])

    # ─── Streak / liga ──────────────────────────────────────────

    def streak_yangila(self) -> None:
        bugun = timezone.localdate()
        if self.oxirgi_oyin_kuni == bugun:
            return
        kecha = bugun - timezone.timedelta(days=1)
        self.streak_kun = self.streak_kun + 1 if self.oxirgi_oyin_kuni == kecha else 1
        self.oxirgi_oyin_kuni = bugun

    def liga_yangila(self) -> None:
        if self.hafta_xp >= 1500:
            self.liga = "olmos"
        elif self.hafta_xp >= 800:
            self.liga = "oltin"
        elif self.hafta_xp >= 300:
            self.liga = "kumush"
        else:
            self.liga = "bronza"


# ═══════════════════════════════════════════════════════════════
# DUEL
# ═══════════════════════════════════════════════════════════════

class Duel(models.Model):
    """Bitta duel. Raqib — robot yoki (chaqiriq orqali) boshqa o'quvchi."""

    HOLAT_DAVOM = "davom"
    HOLAT_TUGAGAN = "tugagan"

    NATIJA_GALABA = "galaba"
    NATIJA_MAGLUBIYAT = "maglubiyat"
    NATIJA_DURRANG = "durrang"

    oyinchi = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duels",
        verbose_name="O'yinchi",
    )
    center = models.ForeignKey(
        "accounts.Center", on_delete=models.CASCADE, null=True, blank=True
    )
    # Katalogdagi qaysi duel o'yini o'ynalgani (savol manbai, mukofot koeffitsiyenti).
    # Eski duellarda bo'sh — ular katalog paydo bo'lishidan oldin o'ynalgan.
    mode = models.ForeignKey(
        "GameMode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duellar",
        verbose_name="O'yin (katalog)",
    )

    raqib = models.ForeignKey(
        GameProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raqib_duellari",
        verbose_name="Raqib",
    )
    raqib_nomi = models.CharField("Raqib nomi", max_length=120)

    # ─── Real duel (odam bilan) ─────────────────────────────────
    #
    # Har o'yinchi uchun alohida Duel yozuvi yaratiladi va ular `juft` orqali
    # bog'lanadi. Ikkalasida savollar bir xil — shuning uchun taqqoslash halol.
    # Raqibning hisobi shu yerdan **jonli** o'qiladi (robotdagi kabi oldindan
    # hisoblab qo'yilmaydi).
    pvp = models.BooleanField("Odam bilan duel", default=False)
    juft = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="juft_teskari",
        verbose_name="Juft duel",
    )

    ball = models.PositiveIntegerField("O'yinchi bali", default=0)
    raqib_ball = models.PositiveIntegerField("Raqib bali", default=0)
    togri_javoblar = models.PositiveSmallIntegerField("To'g'ri javoblar", default=0)

    holat = models.CharField(
        max_length=10,
        choices=[(HOLAT_DAVOM, "Davom etmoqda"), (HOLAT_TUGAGAN, "Tugagan")],
        default=HOLAT_DAVOM,
    )
    natija = models.CharField(
        max_length=12,
        choices=[
            (NATIJA_GALABA, "G'alaba"),
            (NATIJA_MAGLUBIYAT, "Mag'lubiyat"),
            (NATIJA_DURRANG, "Durrang"),
        ],
        blank=True,
        default="",
    )

    olingan_xp = models.PositiveIntegerField("Olingan XP", default=0)
    olingan_chaqmoq = models.DecimalField(
        "Olingan chaqmoq", max_digits=5, decimal_places=1, default=Decimal("0.0")
    )

    boshlangan = models.DateTimeField(auto_now_add=True)
    tugagan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Duel"
        verbose_name_plural = "Duellar"
        ordering = ["-boshlangan"]

    def __str__(self):
        return f"{self.oyinchi} vs {self.raqib_nomi} — {self.ball}:{self.raqib_ball}"


class DuelQuestion(models.Model):
    """Dueldagi bitta savol: o'yinchi javobi va raqibning javobi."""

    duel = models.ForeignKey(Duel, on_delete=models.CASCADE, related_name="savollar")
    savol = models.ForeignKey(Question, on_delete=models.CASCADE)
    tartib = models.PositiveSmallIntegerField()

    # Variantlar duel boshlanganda aralashtirilib, shu yerda muzlatiladi —
    # aks holda har so'rovda tartib o'zgarib ketardi.
    variantlar = models.JSONField(default=list)

    tanlangan = models.CharField(max_length=120, blank=True, default="")
    togri = models.BooleanField(null=True, blank=True)
    sarflangan_ms = models.PositiveIntegerField(default=0)
    olingan_ball = models.PositiveIntegerField(default=0)

    raqib_togri = models.BooleanField(default=False)
    raqib_ms = models.PositiveIntegerField(default=0)
    raqib_ball = models.PositiveIntegerField(default=0)

    javob_berilgan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Duel savoli"
        verbose_name_plural = "Duel savollari"
        ordering = ["tartib"]
        unique_together = [("duel", "tartib")]

    def __str__(self):
        return f"#{self.tartib} — {self.savol.savol}"


# ═══════════════════════════════════════════════════════════════
# DO'KON
# ═══════════════════════════════════════════════════════════════

class ShopItem(SoftDeleteMixin, models.Model):
    """Do'kon mahsuloti. Narxi — chaqmoqda. Admin paneldan qo'shiladi."""

    TUR_AVATAR = "avatar"
    TUR_RAMKA = "ramka"
    TUR_ASSESUAR = "assesuar"
    TUR_JON = "jon"

    TUR_CHOICES = [
        (TUR_AVATAR, "Avatar"),
        (TUR_RAMKA, "Ramka"),
        (TUR_ASSESUAR, "Aksessuar"),
        (TUR_JON, "Jon to'plami"),
    ]

    nom = models.CharField("Nomi", max_length=120)
    izoh = models.CharField("Izoh", max_length=200, blank=True)
    tur = models.CharField("Turi", max_length=16, choices=TUR_CHOICES, default=TUR_ASSESUAR)
    rasm = models.ImageField("Rasm", upload_to="game/dokon/", blank=True, null=True)

    narx_chaqmoq = models.DecimalField("Narxi (chaqmoq)", max_digits=7, decimal_places=1)

    # Jon to'plami uchun — sotib olinganda nechta jon beriladi.
    beradigan_jon = models.PositiveSmallIntegerField("Beradigan jon", default=0)

    zaxira = models.IntegerField(
        "Zaxira",
        default=-1,
        help_text="-1 = cheksiz",
    )
    faol = models.BooleanField("Faol", default=True)
    tartib = models.PositiveSmallIntegerField("Tartib", default=0)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz (bo'sh = umumiy)",
    )

    class Meta:
        verbose_name = "Do'kon mahsuloti"
        verbose_name_plural = "Do'kon mahsulotlari"
        ordering = ["tartib", "narx_chaqmoq"]

    def __str__(self):
        return f"{self.nom} — {self.narx_chaqmoq} ⚡"

    @property
    def mavjud(self) -> bool:
        return self.faol and (self.zaxira == -1 or self.zaxira > 0)


class Purchase(models.Model):
    """Do'kondan sotib olish — chaqmoq yechiladi."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_xaridlar",
    )
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT, related_name="xaridlar")
    narx_chaqmoq = models.DecimalField("To'langan chaqmoq", max_digits=7, decimal_places=1)
    sana = models.DateTimeField(auto_now_add=True)

    # Jismoniy aksessuar bo'lsa — markaz topshirishi kerak.
    topshirildi = models.BooleanField("Topshirildi", default=False)

    class Meta:
        verbose_name = "Xarid"
        verbose_name_plural = "Xaridlar"
        ordering = ["-sana"]

    def __str__(self):
        return f"{self.user} → {self.item.nom}"


# ═══════════════════════════════════════════════════════════════
# DO'STLAR VA CHAQIRIQLAR
# ═══════════════════════════════════════════════════════════════

class Friendship(models.Model):
    """Do'stlik so'rovi / do'stlik."""

    KUTILMOQDA = "kutilmoqda"
    QABUL = "qabul"
    RAD = "rad"

    kimdan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="yuborilgan_dostliklar",
    )
    kimga = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kelgan_dostliklar",
    )
    holat = models.CharField(
        max_length=12,
        choices=[(KUTILMOQDA, "Kutilmoqda"), (QABUL, "Qabul qilindi"), (RAD, "Rad etildi")],
        default=KUTILMOQDA,
    )
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Do'stlik"
        verbose_name_plural = "Do'stliklar"
        unique_together = [("kimdan", "kimga")]
        ordering = ["-yaratilgan"]

    def __str__(self):
        return f"{self.kimdan} → {self.kimga} ({self.holat})"


class GameMode(SoftDeleteMixin, models.Model):
    """Katalogdagi bitta **o'yin** — admin panelidan qo'shiladi.

    Ilova o'yinlar ro'yxatini `/api/mobile/game/catalog/` dan oladi, ya'ni bu
    yerga yangi qator qo'shilishi bilanoq o'yin telefonda paydo bo'ladi.
    Mexanika (`motor`) esa ilovada kod bilan yozilgan — qarang: `game/engines.py`.
    """

    nom = models.CharField("O'yin nomi", max_length=80)
    slug = models.SlugField(
        "Kod nomi",
        max_length=90,
        unique=True,
        blank=True,
        help_text="Bo'sh qoldirsangiz nomdan avtomatik yasaladi.",
    )
    motor = models.CharField(
        "Mexanika (motor)",
        max_length=32,
        choices=MOTOR_CHOICES,
        help_text="O'yin qanday o'ynalishi. Ilovada shu mexanika ekrani ochiladi.",
    )

    izoh = models.CharField("Qisqa izoh", max_length=160, blank=True)
    yoriqnoma = models.CharField(
        "Qoida",
        max_length=255,
        blank=True,
        help_text="Bo'sh qoldirsangiz motorning standart qoidasi ishlatiladi.",
    )

    ikonka = models.CharField(
        "Ikonka (emoji)",
        max_length=8,
        blank=True,
        help_text="Masalan: 🧠 ⚡ 🃏. Bo'sh bo'lsa motor ikonkasi olinadi.",
    )
    rang = models.CharField(
        "Rang (HEX)",
        max_length=7,
        blank=True,
        help_text="Masalan: #0EA5E9. Bo'sh bo'lsa motor rangi olinadi.",
    )
    rasm = models.ImageField("Muqova rasmi", upload_to="game/oyinlar/", blank=True, null=True)

    # ─── Savol manbai ───────────────────────────────────────────
    kategoriyalar = models.ManyToManyField(
        QuestionCategory,
        blank=True,
        related_name="oyinlar",
        verbose_name="Savollar to'plamlari",
        help_text="Bo'sh = barcha to'plamlardan savol olinadi.",
    )
    daraja = models.CharField(
        "Daraja filtri",
        max_length=2,
        choices=DARAJA_CHOICES,
        blank=True,
        help_text="Bo'sh = daraja bo'yicha cheklanmaydi.",
    )

    # ─── O'yin qoidalari ────────────────────────────────────────
    savollar_soni = models.PositiveSmallIntegerField("Savollar soni", default=10)
    savol_soniya = models.PositiveSmallIntegerField(
        "Bitta savolga soniya",
        default=10,
        help_text="0 = savolga alohida taymer yo'q (Sprint/Xotira kabi o'yinlarda).",
    )
    jon_narxi = models.PositiveSmallIntegerField(
        "Necha jon sarflaydi",
        default=1,
        help_text="0 = bepul, jon talab qilinmaydi.",
    )
    xp_mukofot = models.PositiveSmallIntegerField(
        "To'liq bajarilganda XP",
        default=40,
        help_text="Aniqlikka mutanosib beriladi: 8/10 to'g'ri → 80%.",
    )
    chaqmoq_koef = models.DecimalField(
        "Chaqmoq koeffitsiyenti",
        max_digits=4,
        decimal_places=1,
        default=Decimal("1.0"),
        help_text="Standart mukofot shunga ko'paytiriladi (1.0 = duel bilan bir xil).",
    )

    sozlamalar = models.JSONField(
        "Qo'shimcha sozlamalar",
        default=dict,
        blank=True,
        help_text="Motorga xos sozlamalar, masalan Sprint uchun "
        '{"davomiylik_soniya": 60}. Bo\'sh qoldirsangiz standart qiymat ishlatiladi.',
    )

    faqat_pro = models.BooleanField(
        "Faqat Pro (tarifli) o'quvchilarga",
        default=False,
    )
    faol = models.BooleanField("Faol", default=True)
    tartib = models.PositiveSmallIntegerField("Tartib", default=0)

    center = models.ForeignKey(
        "accounts.Center",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Markaz (bo'sh = barcha markazlarga)",
    )

    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O'yin"
        verbose_name_plural = "O'yinlar (katalog)"
        ordering = ["tartib", "nom"]
        indexes = [models.Index(fields=["faol", "center"])]

    def __str__(self):
        return f"{self.belgi} {self.nom}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_yasa()
        super().save(*args, **kwargs)

    def _slug_yasa(self) -> str:
        asos = slugify(self.nom) or self.motor or "oyin"
        slug = asos[:90]
        raqam = 2
        while GameMode.all_objects.filter(slug=slug).exclude(pk=self.pk).exists():
            qoshimcha = f"-{raqam}"
            slug = f"{asos[:90 - len(qoshimcha)]}{qoshimcha}"
            raqam += 1
        return slug

    # ─── Motor bilan birlashtirilgan qiymatlar ──────────────────

    @property
    def motor_obyekt(self) -> Motor | None:
        return motor_ol(self.motor)

    @property
    def belgi(self) -> str:
        m = self.motor_obyekt
        return self.ikonka or (m.ikonka if m else "🎮")

    @property
    def tus(self) -> str:
        m = self.motor_obyekt
        return self.rang or (m.rang if m else "#0EA5E9")

    @property
    def qoida(self) -> str:
        m = self.motor_obyekt
        return self.yoriqnoma or (m.yoriqnoma if m else "")

    @property
    def toliq_sozlamalar(self) -> dict:
        m = self.motor_obyekt
        return m.sozlama(self.sozlamalar) if m else dict(self.sozlamalar or {})

    @property
    def duel_oqimi(self) -> bool:
        m = self.motor_obyekt
        return bool(m and m.duel_oqimi)

    def savollar_qs(self):
        """Shu o'yin uchun mos savollar to'plami."""
        qs = Question.objects.filter(faol=True, kategoriya__faol=True).filter(
            models.Q(center__isnull=True) | models.Q(center=self.center)
        )
        kategoriyalar = list(self.kategoriyalar.filter(faol=True).values_list("id", flat=True))
        if kategoriyalar:
            qs = qs.filter(kategoriya_id__in=kategoriyalar)
        if self.daraja:
            qs = qs.filter(kategoriya__daraja=self.daraja)
        return qs


class GameCooldown(models.Model):
    """O'ynalgan o'yin qulfi — bitta o'yinni takrorlab chaqmoq yig'ishning oldini oladi.

    Qoida: o'yin o'ynalgach `oyin_qulf_soat` soatga yopiladi (bepulda 24 soat).
    Shu sababli o'quvchi 3 ta jonini **turli** o'yinlarga sarflaydi.
    """

    profile = models.ForeignKey(
        GameProfile, on_delete=models.CASCADE, related_name="qulflar"
    )
    mode = models.ForeignKey(
        "GameMode", on_delete=models.CASCADE, related_name="qulflar"
    )
    oxirgi_oynalgan = models.DateTimeField("Oxirgi o'ynalgan", default=timezone.now)

    class Meta:
        verbose_name = "O'yin qulfi"
        verbose_name_plural = "O'yin qulflari"
        unique_together = [("profile", "mode")]
        indexes = [models.Index(fields=["profile", "oxirgi_oynalgan"])]

    def __str__(self):
        return f"{self.profile} — {self.mode}"

    def ochiladi(self, qulf_soat: int) -> timezone.datetime:
        return self.oxirgi_oynalgan + timezone.timedelta(hours=qulf_soat)

    def qolgan_soniya(self, qulf_soat: int) -> int:
        if qulf_soat <= 0:
            return 0
        farq = self.ochiladi(qulf_soat) - timezone.now()
        return max(0, int(farq.total_seconds()))


class GameSession(models.Model):
    """Yakka o'yin sessiyasi (duel'dan tashqari barcha motorlar).

    Ballni **server** hisoblaydi: ilova faqat tanlangan variantni yuboradi,
    to'g'riligini shu yerda tekshiramiz. Shunda mukofotni ilova tomondan
    o'zgartirib bo'lmaydi.
    """

    HOLAT_DAVOM = "davom"
    HOLAT_TUGAGAN = "tugagan"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_sessiyalar",
        verbose_name="O'yinchi",
    )
    center = models.ForeignKey(
        "accounts.Center", on_delete=models.CASCADE, null=True, blank=True
    )
    mode = models.ForeignKey(
        GameMode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessiyalar",
        verbose_name="O'yin",
    )
    # O'yin katalogdan o'chirilsa ham tarix o'qilishi uchun nusxa.
    oyin_nomi = models.CharField("O'yin nomi", max_length=80, blank=True)
    motor = models.CharField("Motor", max_length=32, blank=True)

    jami_savol = models.PositiveSmallIntegerField("Berilgan savollar", default=0)
    togri_javoblar = models.PositiveSmallIntegerField("To'g'ri javoblar", default=0)
    xato_javoblar = models.PositiveSmallIntegerField("Xato javoblar", default=0)
    ball = models.PositiveIntegerField("Ball", default=0)

    olingan_xp = models.PositiveIntegerField("Olingan XP", default=0)
    olingan_chaqmoq = models.DecimalField(
        "Olingan chaqmoq", max_digits=6, decimal_places=1, default=Decimal("0.0")
    )

    holat = models.CharField(
        max_length=10,
        choices=[(HOLAT_DAVOM, "Davom etmoqda"), (HOLAT_TUGAGAN, "Tugagan")],
        default=HOLAT_DAVOM,
    )
    boshlangan = models.DateTimeField(auto_now_add=True)
    tugagan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "O'yin sessiyasi"
        verbose_name_plural = "O'yin sessiyalari"
        ordering = ["-boshlangan"]
        indexes = [models.Index(fields=["user", "holat"])]

    def __str__(self):
        return f"{self.user} — {self.oyin_nomi} ({self.ball})"

    @property
    def aniqlik(self) -> float:
        javob_berilgan = self.togri_javoblar + self.xato_javoblar
        if javob_berilgan <= 0:
            return 0.0
        return self.togri_javoblar / javob_berilgan


class GameSessionQuestion(models.Model):
    """Sessiyadagi bitta savol — variantlari boshida muzlatiladi."""

    sessiya = models.ForeignKey(
        GameSession, on_delete=models.CASCADE, related_name="savollar"
    )
    savol = models.ForeignKey(Question, on_delete=models.CASCADE)
    tartib = models.PositiveSmallIntegerField()
    variantlar = models.JSONField(default=list)

    tanlangan = models.CharField(max_length=120, blank=True, default="")
    togri = models.BooleanField(null=True, blank=True)
    sarflangan_ms = models.PositiveIntegerField(default=0)
    olingan_ball = models.PositiveIntegerField(default=0)
    javob_berilgan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Sessiya savoli"
        verbose_name_plural = "Sessiya savollari"
        ordering = ["tartib"]
        unique_together = [("sessiya", "tartib")]

    def __str__(self):
        return f"#{self.tartib} — {self.savol.savol}"


class DuelQueue(models.Model):
    """Real duel uchun navbat.

    O'quvchi duel boshlaganda navbatga tushadi. Boshqa o'quvchi ham shu o'yinga
    kelsa — ikkalasi juftlanadi va bir xil savollar bilan o'ynaydi. Belgilangan
    vaqt ichida hech kim kelmasa, robot raqib qo'yiladi.

    WebSocket kerak emas: ilova qisqa vaqt so'rov yuborib turadi (polling).
    Render'dagi bitta worker uchun ataylab shunday tanlangan.
    """

    KUTMOQDA = "kutmoqda"
    TOPILDI = "topildi"
    BEKOR = "bekor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duel_navbatlari",
    )
    center = models.ForeignKey(
        "accounts.Center", on_delete=models.CASCADE, null=True, blank=True
    )
    mode = models.ForeignKey(
        GameMode, on_delete=models.CASCADE, related_name="navbatlar"
    )

    holat = models.CharField(
        max_length=10,
        choices=[
            (KUTMOQDA, "Raqib kutilmoqda"),
            (TOPILDI, "Raqib topildi"),
            (BEKOR, "Bekor qilindi"),
        ],
        default=KUTMOQDA,
    )
    duel = models.ForeignKey(
        Duel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="navbat_yozuvlari",
    )
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Duel navbati"
        verbose_name_plural = "Duel navbati"
        ordering = ["yaratilgan"]
        indexes = [models.Index(fields=["holat", "mode", "yaratilgan"])]

    def __str__(self):
        return f"{self.user} — {self.mode} ({self.holat})"


class Feedback(models.Model):
    """O'quvchidan kelgan shikoyat, taklif yoki xato haqidagi xabar."""

    TUR_SHIKOYAT = "shikoyat"
    TUR_TAKLIF = "taklif"
    TUR_XATO = "xato"

    TUR_CHOICES = [
        (TUR_SHIKOYAT, "Shikoyat"),
        (TUR_TAKLIF, "Taklif"),
        (TUR_XATO, "Xatolik haqida xabar"),
    ]

    HOLAT_YANGI = "yangi"
    HOLAT_KORILDI = "korildi"
    HOLAT_HAL = "hal"

    HOLAT_CHOICES = [
        (HOLAT_YANGI, "Yangi"),
        (HOLAT_KORILDI, "Ko'rib chiqilmoqda"),
        (HOLAT_HAL, "Hal qilindi"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_murojaatlar",
        verbose_name="Kimdan",
    )
    center = models.ForeignKey(
        "accounts.Center", on_delete=models.SET_NULL, null=True, blank=True
    )
    mode = models.ForeignKey(
        GameMode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="murojaatlar",
        verbose_name="Qaysi o'yin haqida",
    )

    tur = models.CharField("Turi", max_length=12, choices=TUR_CHOICES, default=TUR_TAKLIF)
    matn = models.TextField("Xabar matni")
    aloqa = models.CharField(
        "Aloqa uchun", max_length=120, blank=True, help_text="Telefon yoki Telegram"
    )

    holat = models.CharField("Holat", max_length=10, choices=HOLAT_CHOICES, default=HOLAT_YANGI)
    javob = models.TextField("Javob", blank=True)

    yaratilgan = models.DateTimeField(auto_now_add=True)
    javob_berilgan = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Murojaat (shikoyat/taklif)"
        verbose_name_plural = "Murojaatlar (shikoyat/taklif)"
        ordering = ["-yaratilgan"]
        indexes = [models.Index(fields=["holat", "-yaratilgan"])]

    def __str__(self):
        return f"{self.get_tur_display()} — {self.user}"


class DuelInvite(models.Model):
    """Do'stni duelga chaqirish."""

    KUTILMOQDA = "kutilmoqda"
    QABUL = "qabul"
    RAD = "rad"

    kimdan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="yuborilgan_chaqiriqlar",
    )
    kimga = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kelgan_chaqiriqlar",
    )
    holat = models.CharField(
        max_length=12,
        choices=[(KUTILMOQDA, "Kutilmoqda"), (QABUL, "Qabul qilindi"), (RAD, "Rad etildi")],
        default=KUTILMOQDA,
    )
    yaratilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Duel chaqirig'i"
        verbose_name_plural = "Duel chaqiriqlari"
        ordering = ["-yaratilgan"]

    def __str__(self):
        return f"{self.kimdan} ⚔ {self.kimga}"
