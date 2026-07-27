"""Chaqmoq Game — o'yin **motorlari** registri.

Motor — bu o'yin mexanikasi (duel, viktorina, xotira...). Motor ilovada kod
bilan yozilgan. Admin esa panelda motor ustiga *o'yin* qo'yadi: nomi, savollar
to'plami, nechta savol, necha soniya, mukofot. Shu sababli:

  • Admin yangi **o'yin** qo'shsa — ilova uni avtomatik ko'radi (katalog API).
  • Yangi **motor** esa ilovaning yangi versiyasini talab qiladi — chunki
    mexanikaning o'zi Flutter kodida.

Ilova tanimaydigan motor kelib qolsa (eski versiya), katalogda "ilovani
yangilang" holatida ko'rsatiladi — o'yin ro'yxati buzilmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Motor:
    """Bitta o'yin mexanikasi."""

    kalit: str
    nom: str
    izoh: str

    # O'quvchiga o'yin boshlanishidan oldin ko'rsatiladigan qoida.
    yoriqnoma: str

    # Admin yangi o'yin yaratganda tavsiya etiladigan boshlang'ich qiymatlar.
    ikonka: str = "🎮"
    rang: str = "#0EA5E9"
    savollar_soni: int = 10
    savol_soniya: int = 10

    # Sessiya ochilishi uchun kerak bo'lgan eng kam savol.
    min_savol: int = 4

    # Savol bilan birga to'g'ri javobni ham ilovaga yuboramizmi?
    # Xotira/juftlash kabi o'yinlarda kartaning ikkala tomoni ekranda turadi —
    # javobni yashirishning ma'nosi yo'q. Viktorinada esa yashiriladi.
    javob_ochiq: bool = False

    # Duel oqimi alohida endpointlarda yuritiladi (robot raqib, revansh, ...).
    duel_oqimi: bool = False

    # Motorga xos qo'shimcha sozlamalar (GameMode.sozlamalar ustiga qo'yiladi).
    sozlamalar: dict = field(default_factory=dict)

    def sozlama(self, mode_sozlamalari: dict | None) -> dict:
        """Motor standartlari + admin kiritgan sozlamalar."""
        birlashgan = dict(self.sozlamalar)
        if isinstance(mode_sozlamalari, dict):
            birlashgan.update(mode_sozlamalari)
        return birlashgan

    def dict(self) -> dict:
        return {
            "kalit": self.kalit,
            "nom": self.nom,
            "izoh": self.izoh,
            "yoriqnoma": self.yoriqnoma,
            "javob_ochiq": self.javob_ochiq,
            "duel_oqimi": self.duel_oqimi,
        }


MOTORLAR: dict[str, Motor] = {
    m.kalit: m
    for m in [
        Motor(
            kalit="duel",
            nom="Duel",
            izoh="Raqib bilan yonma-yon poyga — kim ko'proq to'g'ri javob beradi.",
            yoriqnoma="Har savolga 10 soniya. Raqibingiz ham shu savollarga javob beradi.",
            ikonka="⚔️",
            rang="#6366F1",
            savollar_soni=10,
            savol_soniya=10,
            min_savol=10,
            duel_oqimi=True,
        ),
        Motor(
            kalit="viktorina",
            nom="Viktorina",
            izoh="Yakka o'yin: savollarga vaqt ichida javob bering.",
            yoriqnoma="Har savolga vaqt beriladi. Qancha ko'p to'g'ri javob — shuncha ko'p chaqmoq.",
            ikonka="🧠",
            rang="#0EA5E9",
            savollar_soni=10,
            savol_soniya=12,
            min_savol=1,
        ),
        Motor(
            kalit="omon_qol",
            nom="Omon qol",
            izoh="Xato qilsangiz jon ketadi. Jonlar tugaguncha davom etadi.",
            yoriqnoma="3 marta xato qilsangiz o'yin tugaydi. Qanchaga chidaysiz?",
            ikonka="🛡️",
            rang="#F43F5E",
            savollar_soni=30,
            savol_soniya=10,
            min_savol=5,
            sozlamalar={"ruxsat_xato": 3},
        ),
        Motor(
            kalit="sprint",
            nom="Sprint",
            izoh="Belgilangan vaqt ichida imkon qadar ko'p to'g'ri javob.",
            yoriqnoma="Vaqt umumiy — savolma-savol emas. Tez javob bering!",
            ikonka="⚡",
            rang="#F59E0B",
            savollar_soni=40,
            savol_soniya=0,  # Umumiy taymer ishlaydi, savolga alohida vaqt yo'q.
            min_savol=5,
            sozlamalar={"davomiylik_soniya": 60},
        ),
        Motor(
            kalit="xotira",
            nom="Xotira",
            izoh="So'z va tarjimasini yopiq kartalar orasidan toping.",
            yoriqnoma="Kartalarni ochib, so'zni tarjimasi bilan juftlang.",
            ikonka="🃏",
            rang="#10B981",
            savollar_soni=6,
            savol_soniya=0,
            min_savol=4,
            javob_ochiq=True,
            sozlamalar={"ochiq_qolish_ms": 900},
        ),
        Motor(
            kalit="juftlash",
            nom="Juftlash",
            izoh="Chap ustundagi so'zni o'ng ustundagi tarjimasiga ulang.",
            yoriqnoma="So'zni bosing, so'ng uning tarjimasini bosing.",
            ikonka="🔗",
            rang="#A855F7",
            savollar_soni=6,
            savol_soniya=0,
            min_savol=3,
            javob_ochiq=True,
        ),
    ]
}


MOTOR_CHOICES = [(m.kalit, f"{m.ikonka} {m.nom} — {m.izoh}") for m in MOTORLAR.values()]


def motor_ol(kalit: str) -> Motor | None:
    return MOTORLAR.get(kalit)
