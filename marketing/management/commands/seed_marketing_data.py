from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand

from marketing.models import (
    FAQ,
    FeatureBlock,
    PartnerLogo,
    PricingFeature,
    PricingPlan,
    SiteSetting,
    StaticPage,
    SupportCard,
    Testimonial,
    Vacancy,
)


class Command(BaseCommand):
    help = "Marketing app uchun boshlang'ich demo ma'lumotlarni yaratadi"

    def handle(self, *args, **options):
        seed_image = self._ensure_seed_image()

        self._seed_site_setting(seed_image)
        self._seed_feature_blocks()
        self._seed_pricing()
        self._seed_faq()
        self._seed_testimonials()
        self._seed_support_cards()
        self._seed_vacancies()
        self._seed_static_pages()
        self._seed_partner_logos(seed_image)

        self.stdout.write(self.style.SUCCESS("Marketing demo ma'lumotlar tayyor."))

    def _ensure_seed_image(self):
        media_root = Path(settings.MEDIA_ROOT)
        target_dir = media_root / "marketing" / "seed"
        target_dir.mkdir(parents=True, exist_ok=True)

        source_candidates = [
            Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_blue_logo.png",
            Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_blue_logo_v2.png",
            Path(settings.BASE_DIR) / "static" / "img" / "chaqmoq_logo_transparent.png",
        ]

        source = None
        for candidate in source_candidates:
            if candidate.exists():
                source = candidate
                break

        if not source:
            return ""

        target_file = target_dir / "seed-logo.png"
        if not target_file.exists():
            shutil.copy(source, target_file)

        return str(target_file.relative_to(media_root))

    def _seed_site_setting(self, seed_image):
        defaults = {
            "site_name": "ChaqmoqApp",
            "phone": "+998 90 123 45 67",
            "telegram": "https://t.me/chaqmoqapp",
            "instagram": "https://instagram.com/chaqmoqapp",
            "youtube": "https://youtube.com/@chaqmoqapp",
            "address": "Toshkent shahri, Yunusobod tumani",
            "meta_title": "ChaqmoqApp | O'quv markazlar uchun zamonaviy boshqaruv tizimi",
            "meta_description": "ChaqmoqApp o'quv markazlar uchun o'quvchi nazorati, guruh va davomat, to'lovlar, qarzdorlik, filiallar va Telegram integratsiyasini bitta tizimda birlashtiradi.",
            "hero_title": "O'quv markazingiz boshqaruvini tez, aniq va zamonaviy qiling",
            "hero_subtitle": "Sotuvdan tortib to'lovgacha bo'lgan barcha jarayonni ChaqmoqApp'da avtomatlashtiring.",
            "primary_cta_text": "Demo olish",
            "primary_cta_url": "/demo/",
            "secondary_cta_text": "Narxlarni ko'rish",
            "secondary_cta_url": "/pricing/",
            "is_active": True,
        }

        site_setting = SiteSetting.objects.filter(is_active=True).first()
        if not site_setting:
            site_setting = SiteSetting.objects.create(**defaults)
            self.stdout.write(self.style.SUCCESS("SiteSetting yaratildi."))
        else:
            for key, value in defaults.items():
                if not getattr(site_setting, key):
                    setattr(site_setting, key, value)
            site_setting.save()
            self.stdout.write(self.style.WARNING("SiteSetting mavjud, bo'sh joylari to'ldirildi."))

        if seed_image and not site_setting.hero_image:
            site_setting.hero_image = seed_image
            site_setting.save(update_fields=["hero_image", "updated_at"])

    def _seed_feature_blocks(self):
        feature_rows = [
            (FeatureBlock.Section.FEATURE, "O'quvchilar boshqaruvi", "Bitta bazada to'liq karta va tarix."),
            (FeatureBlock.Section.FEATURE, "Guruh va davomat nazorati", "Har dars bo'yicha qatnashuvni real vaqt kuzatish."),
            (FeatureBlock.Section.FEATURE, "To'lovlar va qarzdorlik", "Qaysi o'quvchi kechikkanini bir zumda ko'rish."),
            (FeatureBlock.Section.FEATURE, "O'qituvchi nazorati", "Ustozlar jadvali va samaradorlik analitikasi."),
            (FeatureBlock.Section.FEATURE, "Filial boshqaruvi", "Bir nechta markazni yagona dashboarddan boshqarish."),
            (FeatureBlock.Section.FEATURE, "Statistika va admin panel", "Rahbar uchun qaror qabul qilishga tayyor ma'lumotlar."),
            (FeatureBlock.Section.INTEGRATION, "Telegram bot", "Eslatmalar va xabarnomalarni avtomatlashtirish."),
            (FeatureBlock.Section.INTEGRATION, "Click / Payme to'lov", "Onlayn to'lovlarni qabul qilish uchun tayyor modul."),
            (FeatureBlock.Section.INTEGRATION, "SMS va qo'ng'iroq", "Mijozlar bilan aloqa jarayonlarini kuchaytirish."),
            (FeatureBlock.Section.INTEGRATION, "CRM ulanish", "Leaddan sotuvgacha bo'lgan yo'lni monitoring qilish."),
            (FeatureBlock.Section.SOLUTION, "Nazoratning yo'qolishi", "Har bo'lim bo'yicha aniq KPI va hisobotlar bilan tartibni tiklang."),
            (FeatureBlock.Section.SOLUTION, "Qo'lda ishlash ko'pligi", "Takroriy ishlarni avtomatlashtirib jamoa vaqtini tejang."),
            (FeatureBlock.Section.SOLUTION, "Qarzdorlik ko'payishi", "To'lov intizomini monitoring qilib tushumni barqarorlashtiring."),
        ]

        for index, (section, title, description) in enumerate(feature_rows, start=1):
            FeatureBlock.objects.get_or_create(
                section=section,
                title=title,
                defaults={
                    "description": description,
                    "subtitle": "",
                    "icon": "bi bi-stars",
                    "order": index,
                    "is_active": True,
                },
            )

    def _seed_pricing(self):
        plan_defs = [
            {
                "name": "Start",
                "student_range": "0-200",
                "base_price": 990000,
                "features": [
                    "O'quvchi va guruhlar boshqaruvi",
                    "Davomat jurnali",
                    "To'lov va qarzdorlik nazorati",
                    "Admin panel statistikasi",
                ],
            },
            {
                "name": "Growth",
                "student_range": "200-500",
                "base_price": 1490000,
                "features": [
                    "Barcha Start funksiyalari",
                    "Ko'p filialli boshqaruv",
                    "Telegram avtomatik xabarnomalar",
                    "Ustozlar samaradorlik hisobotlari",
                ],
            },
            {
                "name": "Pro",
                "student_range": "500+",
                "base_price": 2290000,
                "features": [
                    "Barcha Growth funksiyalari",
                    "Integratsiya uchun kengaytirilgan imkoniyatlar",
                    "Prioritet texnik yordam",
                    "Maxsus onboarding sessiya",
                ],
            },
        ]

        duration_discounts = {
            3: (0, ""),
            6: (8, "8% chegirma"),
            9: (12, "12% chegirma"),
            12: (18, "18% chegirma"),
        }

        for order, plan_def in enumerate(plan_defs, start=1):
            for duration, (discount_percent, discount_label) in duration_discounts.items():
                old_price = plan_def["base_price"] * duration
                discounted = int(old_price * (100 - discount_percent) / 100)
                plan, _ = PricingPlan.objects.get_or_create(
                    name=plan_def["name"],
                    student_range=plan_def["student_range"],
                    duration_months=duration,
                    defaults={
                        "old_price": old_price,
                        "current_price": discounted,
                        "discount_label": discount_label,
                        "badge_text": "Tavsiya etiladi" if (plan_def["name"] == "Growth" and duration == 12) else "",
                        "is_recommended": plan_def["name"] == "Growth" and duration in (9, 12),
                        "is_active": True,
                        "order": order,
                    },
                )

                if not plan.features.exists():
                    for feature_order, feature_text in enumerate(plan_def["features"], start=1):
                        PricingFeature.objects.create(
                            pricing_plan=plan,
                            text=feature_text,
                            order=feature_order,
                        )

    def _seed_faq(self):
        rows = [
            (
                "Joriy qilish qancha vaqt oladi?",
                "Odatda 1-2 ish kuni ichida markazingizni to'liq ishga tushiramiz.",
            ),
            (
                "Ma'lumotlar xavfsizmi?",
                "Ha, platforma bulutda himoyalangan holda ishlaydi va doimiy backup qilinadi.",
            ),
            (
                "Telegram integratsiyasi bormi?",
                "Ha, to'lov eslatmalari, xabarlar va boshqa avtomatlashtirilgan oqimlar mavjud.",
            ),
            (
                "Tarifni keyin o'zgartirish mumkinmi?",
                "Albatta, markazingiz o'sishiga qarab tarifni istalgan payt yangilashingiz mumkin.",
            ),
        ]

        for index, (question, answer) in enumerate(rows, start=1):
            FAQ.objects.get_or_create(
                question=question,
                defaults={
                    "answer": answer,
                    "order": index,
                    "is_active": True,
                },
            )

    def _seed_testimonials(self):
        rows = [
            (
                "Azizbek Yo'ldoshev",
                "Nova Education",
                "Direktor",
                "ChaqmoqApp orqali qarzdorlik va davomat nazoratimiz ancha kuchaydi. Jamoa uchun juda qulay.",
            ),
            (
                "Nigora Xasanova",
                "Result Academy",
                "Bosh administrator",
                "Oldin qo'lda yuritilgan jarayonlar endi avtomatlashtirildi. Hisobotlar bir necha daqiqada tayyor bo'ladi.",
            ),
            (
                "Bekzod Nematov",
                "Prime Kids",
                "Markaz egasi",
                "Filiallar kesimida ko'rinish va Telegram xabarlari juda foydali bo'ldi. Sotuv tizimli boshqarilmoqda.",
            ),
        ]

        for index, (full_name, center_name, role, text) in enumerate(rows, start=1):
            Testimonial.objects.get_or_create(
                full_name=full_name,
                center_name=center_name,
                defaults={
                    "role": role,
                    "text": text,
                    "rating": 5,
                    "is_active": True,
                    "order": index,
                },
            )

    def _seed_support_cards(self):
        rows = [
            (
                "Video darslar",
                "Platformani 0 dan tez o'rganish uchun bosqichma-bosqich video qo'llanmalar.",
                "Videolarni ko'rish",
                "https://youtube.com/@chaqmoqapp",
                "bi bi-play-circle",
            ),
            (
                "Dokumentatsiya",
                "Har bir modul bo'yicha to'liq yo'riqnoma va tez-tez so'raladigan savollar.",
                "Dokumentatsiyani ochish",
                "https://chaqmoqapp.uz/support/",
                "bi bi-journal-code",
            ),
            (
                "Support aloqasi",
                "Texnik yoki biznes savollar bo'yicha mutaxassis bilan bevosita bog'laning.",
                "Supportga yozish",
                "https://t.me/chaqmoqapp",
                "bi bi-chat-dots",
            ),
        ]

        for index, (title, description, button_text, button_url, icon) in enumerate(rows, start=1):
            SupportCard.objects.get_or_create(
                title=title,
                defaults={
                    "description": description,
                    "button_text": button_text,
                    "button_url": button_url,
                    "icon": icon,
                    "order": index,
                    "is_active": True,
                },
            )

    def _seed_vacancies(self):
        rows = [
            {
                "title": "Middle Django Developer",
                "city": "Toshkent",
                "employment_type": Vacancy.EmploymentType.HYBRID,
                "department": "Engineering",
                "description": "Ta'lim texnologiyalari uchun Django asosidagi modullarni ishlab chiqish.",
                "requirements": "Django va DRF tajribasi\nPostgreSQL bilan ishlash\nAPI integratsiyalari",
                "responsibilities": "Yangi funksiyalarni ishlab chiqish\nKod review\nPerformance optimizatsiya",
                "apply_url": "https://t.me/chaqmoqapp",
                "order": 1,
            },
            {
                "title": "Sales Manager",
                "city": "Toshkent",
                "employment_type": Vacancy.EmploymentType.OFFLINE,
                "department": "Sales",
                "description": "O'quv markazlar bilan uchrashuvlar o'tkazish va demo jarayonlarini boshqarish.",
                "requirements": "B2B sotuv tajribasi\nCRM bilan ishlash\nO'zbek va rus tillarida muloqot",
                "responsibilities": "Leadlarni qayta ishlash\nDemo taqdimotlar\nShartnoma yopish",
                "apply_url": "https://t.me/chaqmoqapp",
                "order": 2,
            },
        ]

        for row in rows:
            Vacancy.objects.get_or_create(
                title=row["title"],
                defaults={
                    "city": row["city"],
                    "employment_type": row["employment_type"],
                    "department": row["department"],
                    "description": row["description"],
                    "requirements": row["requirements"],
                    "responsibilities": row["responsibilities"],
                    "apply_url": row["apply_url"],
                    "apply_button_text": "Ariza topshirish",
                    "is_active": True,
                    "order": row["order"],
                },
            )

    def _seed_static_pages(self):
        privacy_content = (
            "ChaqmoqApp foydalanuvchi ma'lumotlarini maxfiy saqlaydi.\n\n"
            "1. Yig'iladigan ma'lumotlar: ism, telefon, markaz nomi va tizimdan foydalanish statistikasi.\n"
            "2. Maqsad: platforma xizmatini yaxshilash, support va billing jarayonlarini boshqarish.\n"
            "3. Ma'lumotlar uchinchi tomonga foydalanuvchi roziligisiz berilmaydi, qonunda ko'rsatilgan holatlar bundan mustasno.\n"
            "4. So'rov bo'yicha ma'lumotlarni yangilash yoki o'chirish yuzasidan supportga murojaat qilishingiz mumkin."
        )

        terms_content = (
            "ChaqmoqApp platformasidan foydalanishda quyidagi shartlar amal qiladi.\n\n"
            "1. Foydalanuvchi tizimdan faqat qonuniy faoliyat doirasida foydalanishi kerak.\n"
            "2. Hisobga kirish ma'lumotlarini xavfsiz saqlash foydalanuvchi zimmasida.\n"
            "3. Tarif va to'lov shartlari pricing sahifasida ko'rsatiladi va admin tomonidan yangilanadi.\n"
            "4. Platforma funksiyalarini noqonuniy buzishga urinish xizmatdan cheklanishga olib keladi."
        )

        StaticPage.objects.get_or_create(
            key=StaticPage.PageKey.PRIVACY,
            defaults={
                "title": "Maxfiylik siyosati",
                "content": privacy_content,
                "is_active": True,
            },
        )
        StaticPage.objects.get_or_create(
            key=StaticPage.PageKey.TERMS,
            defaults={
                "title": "Foydalanish shartlari",
                "content": terms_content,
                "is_active": True,
            },
        )

    def _seed_partner_logos(self, seed_image):
        if not seed_image:
            self.stdout.write(self.style.WARNING("Seed image topilmadi, PartnerLogo yaratilmaydi."))
            return

        rows = [
            ("Alpha Learning", "https://example.com"),
            ("Progress Academy", "https://example.com"),
            ("Smart Edu", "https://example.com"),
            ("Prime School", "https://example.com"),
            ("Nova Study", "https://example.com"),
            ("Target Center", "https://example.com"),
        ]

        for index, (name, url) in enumerate(rows, start=1):
            PartnerLogo.objects.get_or_create(
                name=name,
                defaults={
                    "image": seed_image,
                    "url": url,
                    "order": index,
                    "is_active": True,
                },
            )
