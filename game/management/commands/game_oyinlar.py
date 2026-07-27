"""O'yinlar katalogini boshlang'ich qiymatlar bilan to'ldiradi.

Ishlatish:
    python manage.py game_oyinlar

Har motor uchun bittadan tayyor o'yin yaratadi. Mavjudini o'zgartirmaydi —
admin panelda qilingan tahrirlar saqlanib qoladi. Yangi o'yinlar keyin admin
panelidan ("O'yinlar (katalog)") qo'shiladi va ilovada avtomatik ko'rinadi.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from game.models import GameMode


# (slug, nom, motor, izoh, savollar_soni, savol_soniya, jon, xp, koef, sozlamalar)
OYINLAR = [
    (
        "duel",
        "Duel",
        "duel",
        "Raqib bilan yonma-yon poyga — kim ko'proq to'g'ri javob beradi.",
        10, 10, 1, 45, "1.0", {},
    ),
    (
        "viktorina",
        "Viktorina",
        "viktorina",
        "Yakka o'yin: 10 savol, har biriga 12 soniya.",
        10, 12, 1, 35, "0.8", {},
    ),
    (
        "sprint",
        "Sprint",
        "sprint",
        "60 soniya ichida imkon qadar ko'p to'g'ri javob bering.",
        40, 0, 1, 40, "1.0", {"davomiylik_soniya": 60},
    ),
    (
        "omon-qol",
        "Omon qol",
        "omon_qol",
        "3 marta xato qilsangiz o'yin tugaydi. Qanchaga chidaysiz?",
        30, 10, 1, 50, "1.2", {"ruxsat_xato": 3},
    ),
    (
        "xotira",
        "Xotira",
        "xotira",
        "So'z va tarjimasini yopiq kartalar orasidan toping.",
        6, 0, 1, 30, "0.8", {"ochiq_qolish_ms": 900},
    ),
    (
        "juftlash",
        "Juftlash",
        "juftlash",
        "So'zlarni tarjimalari bilan ulang — vaqt cheklovisiz.",
        6, 0, 1, 25, "0.6", {},
    ),
]


class Command(BaseCommand):
    help = "O'yinlar katalogini standart o'yinlar bilan to'ldiradi."

    def handle(self, *args, **options):
        yangi = 0
        for tartib, (
            slug, nom, motor, izoh, soni, soniya, jon, xp, koef, sozlamalar
        ) in enumerate(OYINLAR):
            mode, created = GameMode.all_objects.get_or_create(
                slug=slug,
                defaults={
                    "nom": nom,
                    "motor": motor,
                    "izoh": izoh,
                    "savollar_soni": soni,
                    "savol_soniya": soniya,
                    "jon_narxi": jon,
                    "xp_mukofot": xp,
                    "chaqmoq_koef": Decimal(koef),
                    "sozlamalar": sozlamalar,
                    "tartib": tartib,
                    "faol": True,
                },
            )
            if created:
                yangi += 1
                self.stdout.write(self.style.SUCCESS(f"  + {mode.belgi} {mode.nom}"))

        jami = GameMode.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"O'yinlar katalogi: {jami} ta ({yangi} ta yangi qo'shildi)")
        )
        self.stdout.write(
            "Yangi o'yin qo'shish: admin panel → Game → «O'yinlar (katalog)» → Qo'shish."
        )
