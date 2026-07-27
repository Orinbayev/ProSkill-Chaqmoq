"""Chaqmoq Game admin — savol, yangilik, do'kon, tarif va robot boshqaruvi.

Savollarni bittalab qo'shish ham, CSV faylidan ommaviy yuklash ham mumkin
("Savollar" ro'yxatidagi «CSV'dan yuklash» tugmasi).
"""

from __future__ import annotations

import csv
import io

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .engines import motor_ol
from .payments import obunani_yoq
from .models import (
    Duel,
    DuelInvite,
    DuelQuestion,
    Feedback,
    Friendship,
    GameCooldown,
    GameMode,
    GameProfile,
    GameSession,
    GameSessionQuestion,
    NewsPost,
    Obuna,
    Purchase,
    Question,
    QuestionCategory,
    ShopItem,
    Tarif,
    TarifSorovi,
)


CSV_USTUNLAR = [
    "kategoriya", "tur", "savol", "togri_javob",
    "notogri_1", "notogri_2", "notogri_3", "izoh",
]


# ═══════════════════════════════════════════════════════════════
# O'YINLAR KATALOGI
#
# Bu yerga qo'shilgan har bir qator — ilovadagi bitta o'yin kartasi.
# Saqlash bilanoq o'quvchining telefonida paydo bo'ladi.
# ═══════════════════════════════════════════════════════════════

class GameModeForm(forms.ModelForm):
    class Meta:
        model = GameMode
        fields = "__all__"

    def clean(self):
        tozalangan = super().clean()
        motor = motor_ol(tozalangan.get("motor") or "")
        soni = tozalangan.get("savollar_soni") or 0

        if motor and soni < motor.min_savol:
            self.add_error(
                "savollar_soni",
                f"«{motor.nom}» uchun kamida {motor.min_savol} ta savol kerak.",
            )

        sozlamalar = tozalangan.get("sozlamalar")
        if sozlamalar in (None, ""):
            tozalangan["sozlamalar"] = {}
        elif not isinstance(sozlamalar, dict):
            self.add_error("sozlamalar", "Sozlamalar JSON obyekt bo'lishi kerak, masalan {}.")

        return tozalangan


@admin.register(GameMode)
class GameModeAdmin(admin.ModelAdmin):
    """O'yin qo'shish — ilovaga yangi o'yin shu yerdan chiqadi."""

    form = GameModeForm

    list_display = (
        "nom_ustun",
        "motor_ustun",
        "manba_ustun",
        "mavjud_ustun",
        "qoida_ustun",
        "faqat_pro",
        "faol",
        "tartib",
        "center",
    )
    list_display_links = ("nom_ustun",)
    list_editable = ("faol", "tartib")
    list_filter = ("motor", "faol", "faqat_pro", "daraja", "center")
    search_fields = ("nom", "slug", "izoh")
    filter_horizontal = ("kategoriyalar",)
    ordering = ("tartib", "nom")

    fieldsets = (
        (
            "O'yin",
            {
                "fields": ("nom", "motor", "izoh", "yoriqnoma"),
                "description": (
                    "<b>Motor</b> — o'yin qanday o'ynalishi. Ilovada shu mexanika "
                    "ekrani ochiladi. Yangi motor ilovaning yangi versiyasi bilan "
                    "keladi, lekin bitta motor ustiga <b>xohlagancha o'yin</b> "
                    "qo'shish mumkin (turli to'plam, uzunlik va mukofot bilan)."
                ),
            },
        ),
        (
            "Ko'rinish",
            {
                "fields": ("ikonka", "rang", "rasm", "tartib"),
                "description": "Bo'sh qoldirilsa motorning standart ikonkasi va rangi olinadi.",
            },
        ),
        (
            "Savollar manbai",
            {
                "fields": ("kategoriyalar", "daraja"),
                "description": "Ikkalasi ham bo'sh bo'lsa — barcha faol savollardan olinadi.",
            },
        ),
        (
            "Qoidalar va mukofot",
            {
                "fields": (
                    "savollar_soni",
                    "savol_soniya",
                    "jon_narxi",
                    "xp_mukofot",
                    "chaqmoq_koef",
                ),
            },
        ),
        (
            "Qo'shimcha",
            {
                "fields": ("sozlamalar", "faqat_pro", "faol", "center", "slug"),
                "classes": ("collapse",),
                "description": (
                    "«Sozlamalar» — motorga xos qiymatlar. Masalan Sprint uchun "
                    '<code>{"davomiylik_soniya": 60}</code>, Omon qol uchun '
                    '<code>{"ruxsat_xato": 3}</code>. Kod nomi (slug) bo\'sh '
                    "qoldirilsa nomdan avtomatik yasaladi."
                ),
            },
        ),
    )

    @admin.display(description="O'yin", ordering="nom")
    def nom_ustun(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:8px;">'
            '<span style="width:10px;height:10px;border-radius:50%;background:{};'
            'display:inline-block;"></span>{} <b>{}</b></span>',
            obj.tus,
            obj.belgi,
            obj.nom,
        )

    @admin.display(description="Mexanika", ordering="motor")
    def motor_ustun(self, obj):
        motor = obj.motor_obyekt
        if motor is None:
            return format_html('<span style="color:#b91c1c;">? {}</span>', obj.motor)
        return motor.nom

    @admin.display(description="Savol manbai")
    def manba_ustun(self, obj):
        nomlar = [k.nom for k in obj.kategoriyalar.all()[:3]]
        qism = ", ".join(nomlar) if nomlar else "Barcha to'plamlar"
        if obj.daraja:
            qism = f"{qism} · {obj.daraja}"
        return qism

    @admin.display(description="Savollar")
    def mavjud_ustun(self, obj):
        """Shu o'yin uchun nechta savol bor — yetmasa admin darrov ko'radi."""
        mavjud = obj.savollar_qs().count()
        motor = obj.motor_obyekt
        kerak = motor.min_savol if motor else obj.savollar_soni
        if mavjud < kerak:
            return format_html(
                '<span style="color:#b91c1c;font-weight:600;">{} ta — '
                "kamida {} kerak</span>",
                mavjud,
                kerak,
            )
        return format_html("{} ta", mavjud)

    @admin.display(description="Qoida")
    def qoida_ustun(self, obj):
        vaqt = f"{obj.savol_soniya}s/savol" if obj.savol_soniya else "taymersiz"
        return f"{obj.savollar_soni} savol · {vaqt} · {obj.jon_narxi} jon"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("kategoriyalar")


class GameSessionQuestionInline(admin.TabularInline):
    model = GameSessionQuestion
    extra = 0
    can_delete = False
    readonly_fields = ("tartib", "savol", "tanlangan", "togri", "sarflangan_ms", "olingan_ball")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "oyin_nomi",
        "motor",
        "ball",
        "aniqlik_ustun",
        "olingan_xp",
        "olingan_chaqmoq",
        "holat",
        "boshlangan",
    )
    list_filter = ("motor", "holat", "mode", "center")
    search_fields = ("user__ism", "user__email", "oyin_nomi")
    readonly_fields = tuple(
        f.name for f in GameSession._meta.fields if f.name != "id"
    )
    inlines = [GameSessionQuestionInline]

    @admin.display(description="Aniqlik")
    def aniqlik_ustun(self, obj):
        return f"{round(obj.aniqlik * 100)}%"

    def has_add_permission(self, request):
        return False


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
    list_display = ("nom", "narx_ustun", "haftalik_ustun", "kun", "tavsif", "faol")
    list_editable = ("faol",)
    ordering = ("tartib", "narx_som")

    fieldsets = (
        ("Tarif", {"fields": ("nom", "narx_som", "kun", "izoh", "tartib", "faol")}),
        (
            "Nimani tezlashtiradi",
            {
                "fields": ("jon_soni", "soat", "oyin_qulf_soat", "chaqmoq_bonus_foiz"),
                "description": (
                    "Bepul reja: <b>3 jon / 8 soat</b>, o'ynalgan o'yin "
                    "<b>24 soatdan</b> keyin ochiladi.<br>"
                    "Diqqat: o'yinlar soni cheklangani uchun <b>o'yin qulfi</b> "
                    "asosiy to'siq. Faqat jonni tezlashtirish o'quvchiga deyarli "
                    "hech narsa bermaydi — ikkalasini birga qisqartiring."
                ),
            },
        ),
    )

    @admin.display(description="Narxi", ordering="narx_som")
    def narx_ustun(self, obj):
        return f"{obj.narx_som:,} so'm".replace(",", " ")

    @admin.display(description="Haftasiga")
    def haftalik_ustun(self, obj):
        return f"{obj.haftalik_narx:,} so'm".replace(",", " ")


@admin.register(TarifSorovi)
class TarifSoroviAdmin(admin.ModelAdmin):
    """Naqd to'lovlar shu yerdan tasdiqlanadi."""

    list_display = (
        "user", "tarif", "narx_ustun", "usul", "holat_ustun", "yaratilgan", "tasdiqlangan",
    )
    list_filter = ("holat", "usul", "tarif", "center")
    search_fields = ("user__ism", "user__email", "transaction_id")
    readonly_fields = ("transaction_id", "obuna", "tasdiqlangan", "yaratilgan")
    autocomplete_fields = ("user",)
    actions = ("tasdiqlash", "bekor_qilish")

    @admin.display(description="Summa", ordering="narx_som")
    def narx_ustun(self, obj):
        return f"{obj.narx_som:,} so'm".replace(",", " ")

    @admin.display(description="Holat", ordering="holat")
    def holat_ustun(self, obj):
        ranglar = {
            TarifSorovi.HOLAT_TOLANGAN: "#15803d",
            TarifSorovi.HOLAT_KUTILMOQDA: "#b45309",
            TarifSorovi.HOLAT_BEKOR: "#b91c1c",
        }
        return format_html(
            '<b style="color:{};">{}</b>',
            ranglar.get(obj.holat, "#334155"),
            obj.get_holat_display(),
        )

    @admin.action(description="To'landi deb belgilash va tarifni yoqish")
    def tasdiqlash(self, request, queryset):
        yoqildi = 0
        for sorov in queryset.filter(holat=TarifSorovi.HOLAT_KUTILMOQDA):
            obunani_yoq(sorov, izoh=f"Admin tasdiqladi: {request.user}")
            yoqildi += 1
        self.message_user(
            request, f"{yoqildi} ta tarif yoqildi.", messages.SUCCESS
        )

    @admin.action(description="Bekor qilish")
    def bekor_qilish(self, request, queryset):
        soni = queryset.filter(holat=TarifSorovi.HOLAT_KUTILMOQDA).update(
            holat=TarifSorovi.HOLAT_BEKOR
        )
        self.message_user(request, f"{soni} ta so'rov bekor qilindi.", messages.WARNING)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """O'quvchilardan kelgan shikoyat va takliflar."""

    list_display = ("tur", "user", "qisqa_matn", "mode", "holat", "yaratilgan")
    list_filter = ("tur", "holat", "center", "mode")
    search_fields = ("matn", "user__ism", "user__email", "aloqa")
    readonly_fields = ("user", "center", "mode", "tur", "matn", "aloqa", "yaratilgan")

    fieldsets = (
        ("Murojaat", {"fields": ("tur", "user", "center", "mode", "matn", "aloqa", "yaratilgan")}),
        ("Javob", {"fields": ("holat", "javob", "javob_berilgan")}),
    )

    @admin.display(description="Xabar")
    def qisqa_matn(self, obj):
        return obj.matn[:70] + ("…" if len(obj.matn) > 70 else "")

    def save_model(self, request, obj, form, change):
        if obj.javob and not obj.javob_berilgan:
            obj.javob_berilgan = timezone.now()
            if obj.holat == Feedback.HOLAT_YANGI:
                obj.holat = Feedback.HOLAT_KORILDI
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return False


@admin.register(GameCooldown)
class GameCooldownAdmin(admin.ModelAdmin):
    """O'yin qulflari — kerak bo'lsa qo'lda ochish uchun."""

    list_display = ("profile", "mode", "oxirgi_oynalgan")
    list_filter = ("mode",)
    search_fields = ("profile__user__ism", "profile__user__email")
    actions = ("qulfni_ochish",)

    @admin.action(description="Qulfni ochish (darhol o'ynasa bo'ladi)")
    def qulfni_ochish(self, request, queryset):
        soni = queryset.count()
        queryset.delete()
        self.message_user(request, f"{soni} ta qulf ochildi.", messages.SUCCESS)

    def has_add_permission(self, request):
        return False


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
