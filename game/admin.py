"""Chaqmoq Game admin — savol, yangilik, do'kon, tarif va robot boshqaruvi.

Savollarni bittalab qo'shish ham, CSV faylidan ommaviy yuklash ham mumkin
("Savollar" ro'yxatidagi «CSV'dan yuklash» tugmasi).
"""

from __future__ import annotations

import csv
import io

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from .models import (
    Duel,
    DuelInvite,
    DuelQuestion,
    Friendship,
    GameProfile,
    NewsPost,
    Obuna,
    Purchase,
    Question,
    QuestionCategory,
    ShopItem,
    Tarif,
)


CSV_USTUNLAR = [
    "kategoriya", "tur", "savol", "togri_javob",
    "notogri_1", "notogri_2", "notogri_3", "izoh",
]


# ═══════════════════════════════════════════════════════════════
# KONTENT
# ═══════════════════════════════════════════════════════════════

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ("nom", "daraja", "savollar_soni", "faol", "center")
    list_filter = ("daraja", "faol", "center")
    search_fields = ("nom",)
    list_editable = ("faol",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("savol", "togri_javob", "kategoriya", "tur", "faol", "center")
    list_filter = ("tur", "faol", "kategoriya__daraja", "kategoriya", "center")
    search_fields = ("savol", "togri_javob")
    list_editable = ("faol",)
    autocomplete_fields = ("kategoriya",)
    change_list_template = "admin/game/question_changelist.html"

    fieldsets = (
        ("Savol", {"fields": ("kategoriya", "tur", "savol", "izoh")}),
        ("Javoblar", {"fields": ("togri_javob", "notogri_1", "notogri_2", "notogri_3")}),
        ("Media (ixtiyoriy)", {"fields": ("audio", "rasm")}),
        ("Sozlamalar", {"fields": ("faol", "center")}),
    )

    def get_urls(self):
        return [
            path(
                "csv-yuklash/",
                self.admin_site.admin_view(self.csv_yuklash_view),
                name="game_question_csv_yuklash",
            ),
            *super().get_urls(),
        ]

    def csv_yuklash_view(self, request):
        if request.method == "POST":
            fayl = request.FILES.get("csv_fayl")
            if not fayl:
                messages.error(request, "Fayl tanlanmadi.")
                return redirect("..")

            try:
                matn = fayl.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                messages.error(request, "Fayl UTF-8 kodlashda bo'lishi kerak.")
                return redirect("..")

            reader = csv.DictReader(io.StringIO(matn))
            yetishmayotgan = set(CSV_USTUNLAR[:7]) - set(reader.fieldnames or [])
            if yetishmayotgan:
                messages.error(
                    request,
                    f"CSV'da ustunlar yetishmayapti: {', '.join(sorted(yetishmayotgan))}",
                )
                return redirect("..")

            qoshildi = 0
            xatolar: list[str] = []

            for qator, row in enumerate(reader, start=2):
                kategoriya_nomi = (row.get("kategoriya") or "").strip()
                kategoriya = QuestionCategory.objects.filter(
                    nom__iexact=kategoriya_nomi
                ).first()
                if kategoriya is None:
                    xatolar.append(f"{qator}-qator: «{kategoriya_nomi}» to'plami topilmadi")
                    continue

                savol = (row.get("savol") or "").strip()
                togri = (row.get("togri_javob") or "").strip()
                if not savol or not togri:
                    xatolar.append(f"{qator}-qator: savol yoki to'g'ri javob bo'sh")
                    continue

                Question.objects.create(
                    kategoriya=kategoriya,
                    tur=(row.get("tur") or Question.TUR_TARJIMA).strip(),
                    savol=savol,
                    togri_javob=togri,
                    notogri_1=(row.get("notogri_1") or "").strip(),
                    notogri_2=(row.get("notogri_2") or "").strip(),
                    notogri_3=(row.get("notogri_3") or "").strip(),
                    izoh=(row.get("izoh") or "").strip(),
                    center=kategoriya.center,
                )
                qoshildi += 1

            if qoshildi:
                messages.success(request, f"✅ {qoshildi} ta savol yuklandi.")
            for xato in xatolar[:10]:
                messages.warning(request, xato)
            if len(xatolar) > 10:
                messages.warning(request, f"... va yana {len(xatolar) - 10} ta xato.")

            return redirect("admin:game_question_changelist")

        return render(
            request,
            "admin/game/csv_yuklash.html",
            {
                "title": "Savollarni CSV'dan yuklash",
                "ustunlar": CSV_USTUNLAR,
                "namuna": "kategoriya,tur,savol,togri_javob,notogri_1,notogri_2,notogri_3,izoh\n"
                          "Mevalar (A1),tarjima,apple,olma,nok,uzum,shaftoli,Meva nomlari\n",
                "opts": self.model._meta,
            },
        )


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("sarlavha", "tur", "muhim", "faol", "chop_etilgan", "center")
    list_filter = ("tur", "muhim", "faol", "center")
    search_fields = ("sarlavha", "matn")
    list_editable = ("muhim", "faol")


# ═══════════════════════════════════════════════════════════════
# DO'KON
# ═══════════════════════════════════════════════════════════════

@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("rasm_ustun", "nom", "tur", "narx_ustun", "zaxira", "faol", "center")
    list_filter = ("tur", "faol", "center")
    search_fields = ("nom",)
    list_editable = ("faol",)

    fieldsets = (
        ("Mahsulot", {"fields": ("nom", "izoh", "tur", "rasm")}),
        ("Narx", {
            "fields": ("narx_chaqmoq", "beradigan_jon"),
            "description": "Narx <b>chaqmoqda</b>. «Beradigan jon» faqat jon to'plami uchun.",
        }),
        ("Sozlamalar", {"fields": ("zaxira", "faol", "tartib", "center")}),
    )

    @admin.display(description="Rasm")
    def rasm_ustun(self, obj):
        if obj.rasm:
            return format_html(
                '<img src="{}" style="height:40px;border-radius:6px;">', obj.rasm.url
            )
        return "—"

    @admin.display(description="Narxi", ordering="narx_chaqmoq")
    def narx_ustun(self, obj):
        return format_html("<b>{} ⚡</b>", obj.narx_chaqmoq)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "narx_chaqmoq", "topshirildi", "sana")
    list_filter = ("topshirildi", "item__tur")
    search_fields = ("user__ism", "user__email", "item__nom")
    list_editable = ("topshirildi",)
    readonly_fields = ("user", "item", "narx_chaqmoq", "sana")

    def has_add_permission(self, request):
        return False


# ═══════════════════════════════════════════════════════════════
# TARIFLAR
# ═══════════════════════════════════════════════════════════════

@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = ("nom", "narx_ustun", "kun", "tavsif", "faol")
    list_editable = ("faol",)
    ordering = ("tartib", "narx_som")

    @admin.display(description="Narxi", ordering="narx_som")
    def narx_ustun(self, obj):
        return f"{obj.narx_som:,} so'm".replace(",", " ")


@admin.register(Obuna)
class ObunaAdmin(admin.ModelAdmin):
    list_display = ("user", "tarif", "boshlangan", "tugaydi", "tolangan", "faol_ustun")
    list_filter = ("tolangan", "tarif")
    search_fields = ("user__ism", "user__email")
    list_editable = ("tolangan",)
    autocomplete_fields = ("user",)

    @admin.display(description="Faol", boolean=True)
    def faol_ustun(self, obj):
        return obj.faol


# ═══════════════════════════════════════════════════════════════
# O'YINCHILAR VA ROBOTLAR
# ═══════════════════════════════════════════════════════════════

class RobotFilter(admin.SimpleListFilter):
    title = "Turi"
    parameter_name = "kim"

    def lookups(self, request, model_admin):
        return [("odam", "O'quvchilar"), ("robot", "Robotlar")]

    def queryset(self, request, queryset):
        if self.value() == "robot":
            return queryset.filter(robot=True)
        if self.value() == "odam":
            return queryset.filter(robot=False)
        return queryset


@admin.register(GameProfile)
class GameProfileAdmin(admin.ModelAdmin):
    list_display = (
        "nomi", "kim_ustun", "xp", "hafta_xp", "chaqmoq_ustun",
        "jon_ustun", "streak_kun", "liga", "center",
    )
    list_filter = (RobotFilter, "liga", "center")
    search_fields = ("robot_ism", "user__ism", "user__email")
    readonly_fields = ("xp", "hafta_xp", "streak_kun", "oxirgi_oyin_kuni", "yaratilgan")

    fieldsets = (
        ("Kim", {"fields": ("user", "robot", "robot_ism", "maxorat", "avatar", "center")}),
        ("Holat", {"fields": ("chaqmoq", "jon", "liga")}),
        ("Statistika", {"fields": ("xp", "hafta_xp", "streak_kun", "oxirgi_oyin_kuni")}),
    )

    @admin.display(description="Kim")
    def kim_ustun(self, obj):
        return "🤖 Robot" if obj.robot else "👤 O'quvchi"

    @admin.display(description="Chaqmoq", ordering="chaqmoq")
    def chaqmoq_ustun(self, obj):
        return format_html("<b>{} ⚡</b>", obj.chaqmoq)

    @admin.display(description="Jon")
    def jon_ustun(self, obj):
        if obj.robot:
            return "—"
        return f"{obj.joriy_jon} / {obj.max_jon}"


class DuelQuestionInline(admin.TabularInline):
    model = DuelQuestion
    extra = 0
    can_delete = False
    readonly_fields = (
        "tartib", "savol", "tanlangan", "togri", "sarflangan_ms",
        "olingan_ball", "raqib_togri", "raqib_ball",
    )
    fields = readonly_fields


@admin.register(Duel)
class DuelAdmin(admin.ModelAdmin):
    list_display = (
        "oyinchi", "raqib_nomi", "ball", "raqib_ball",
        "togri_javoblar", "natija", "olingan_chaqmoq", "boshlangan",
    )
    list_filter = ("natija", "holat", "center")
    search_fields = ("oyinchi__ism", "oyinchi__email", "raqib_nomi")
    inlines = [DuelQuestionInline]

    def has_add_permission(self, request):
        return False


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("kimdan", "kimga", "holat", "yaratilgan")
    list_filter = ("holat",)


@admin.register(DuelInvite)
class DuelInviteAdmin(admin.ModelAdmin):
    list_display = ("kimdan", "kimga", "holat", "yaratilgan")
    list_filter = ("holat",)
