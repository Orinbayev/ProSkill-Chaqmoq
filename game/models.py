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

from core.soft_delete import SoftDeleteMixin


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

# Bepul reja: 3 jon, har kuni yarim tunda tiklanadi → kuniga 3 duel.
BEPUL_JON = 3

# Chaqmoq mukofoti — to'g'ri javoblar soniga qarab (10 tadan).
#   10/10  → 3.0
#   8–9/10 → 2.0
#   5–7/10 → 1.0
#   <5     → 0.5
def chaqmoq_mukofoti(togri_javoblar: int) -> Decimal:
    """To'g'ri javoblar soniga qarab chaqmoq beradi."""
    if togri_javoblar >= SAVOLLAR_SONI:
        return Decimal("3.0")
    if togri_javoblar >= 8:
        return Decimal("2.0")
    if togri_javoblar >= 5:
        return Decimal("1.0")
    return Decimal("0.5")


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
    """Pullik reja. Jonlar `soat` soatda bir marta `jon_soni` taga tiklanadi.

    Bepul rejada jonlar har kuni 3 taga tiklanadi (soatlik tiklanish yo'q).
    """

    nom = models.CharField("Nomi", max_length=80)
    narx_som = models.PositiveIntegerField("Narxi (so'm)")
    kun = models.PositiveSmallIntegerField("Muddati (kun)")
    jon_soni = models.PositiveSmallIntegerField("Bir tiklanishda nechta jon", default=3)
    soat = models.PositiveSmallIntegerField("Necha soatda bir tiklanadi")

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
        return f"Har {self.soat} soatda {self.jon_soni} ta jon"


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
        """Faol obuna, bo'lmasa None."""
        if self.user is None:
            return None
        return (
            Obuna.objects
            .filter(user=self.user, tolangan=True, tugaydi__gt=timezone.now())
            .select_related("tarif")
            .order_by("-tugaydi")
            .first()
        )

    @property
    def pro(self) -> bool:
        return self.obuna is not None

    @property
    def max_jon(self) -> int:
        obuna = self.obuna
        return obuna.tarif.jon_soni if obuna else BEPUL_JON

    # ─── Jonlar ─────────────────────────────────────────────────
    #
    # Jonlar "yotgan" holatda saqlanadi va faqat o'qilganda tiklanadi
    # (lazy regeneration) — cron yoki fon vazifasi kerak emas.
    #
    # Bepul reja: har kuni yarim tunda 3 taga tiklanadi → kuniga 3 duel.
    # Pullik reja: har `soat` soatda `jon_soni` taga tiklanadi.

    def _tikla(self) -> None:
        obuna = self.obuna

        if obuna is None:
            # Bepul: kunlik tiklanish.
            bugun = timezone.localdate()
            if self.jon_kuni != bugun:
                self.jon = BEPUL_JON
                self.jon_kuni = bugun
                self.jon_yangilangan = timezone.now()
            return

        # Pullik: soatlik tiklanish.
        maks = obuna.tarif.jon_soni
        if self.jon >= maks:
            self.jon_yangilangan = timezone.now()
            return

        oraliq = timezone.timedelta(hours=obuna.tarif.soat)
        o_tgan = timezone.now() - self.jon_yangilangan
        marta = int(o_tgan / oraliq)
        if marta <= 0:
            return

        self.jon = min(maks, self.jon + marta * obuna.tarif.jon_soni)
        if self.jon >= maks:
            self.jon_yangilangan = timezone.now()
        else:
            self.jon_yangilangan += oraliq * marta

    @property
    def joriy_jon(self) -> int:
        self._tikla()
        return self.jon

    def keyingi_jon_soniya(self) -> int:
        """Keyingi tiklanishgacha necha soniya. 0 = kutish shart emas."""
        if self.joriy_jon >= self.max_jon:
            return 0

        obuna = self.obuna
        if obuna is None:
            # Bepul: ertaga yarim tunda.
            ertaga = timezone.localdate() + timezone.timedelta(days=1)
            yarim_tun = timezone.make_aware(
                timezone.datetime.combine(ertaga, timezone.datetime.min.time())
            )
            return max(0, int((yarim_tun - timezone.now()).total_seconds()))

        keyingi = self.jon_yangilangan + timezone.timedelta(hours=obuna.tarif.soat)
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

    raqib = models.ForeignKey(
        GameProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raqib_duellari",
        verbose_name="Raqib",
    )
    raqib_nomi = models.CharField("Raqib nomi", max_length=120)

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
