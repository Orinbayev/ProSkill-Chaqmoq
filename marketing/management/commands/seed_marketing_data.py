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
            "hero_title": "O'quv markazingizni ChaqmoqApp bilan avtomatlashtiring",
            "hero_subtitle": "Bitta tizim — daromadni oshiradi, vaqtni tejaydi, xatolarni yo'qotadi.",
            "primary_cta_text": "Demo so'rash",
            "primary_cta_url": "/demo/",
            "secondary_cta_text": "Imkoniyatlarni ko'rish",
            "secondary_cta_url": "#imkoniyatlar",
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
            (
                FeatureBlock.Section.FEATURE, "bi bi-mortarboard-fill",
                "O'quvchilar",
                "Har bir o'quvchining to'liq kartasi va tarixi.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-clipboard2-check-fill",
                "Davomat",
                "Bir bosishda davomat va Telegram xabar.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-credit-card-2-front-fill",
                "To'lov va qarzdorlik",
                "Qarzdorlar avtomatik ro'yxat va eslatmalar.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-calendar2-week-fill",
                "Guruh va jadval",
                "Guruh, o'qituvchi va jadval bitta tizimda.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-phone-fill",
                "Ota-ona paneli",
                "Ota-ona telefondan farzand ma'lumotini ko'radi.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-graph-up-arrow",
                "Analitika",
                "Tushum, davomat va qarzdorlik bo'yicha hisobot.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-cash-coin",
                "O'qituvchi maoshi",
                "Har dars uchun maosh avtomatik hisoblanadi.",
            ),
            (
                FeatureBlock.Section.FEATURE, "bi bi-buildings-fill",
                "Ko'p filial",
                "Barcha filiallar bitta dashboardda.",
            ),
            (
                FeatureBlock.Section.INTEGRATION, "bi bi-telegram",
                "Telegram bot integratsiyasi",
                "To'lov eslatmalari, davomat xabarlari va qarzdorlik bildirishnomalarini avtomatik yuboring.",
            ),
            (
                FeatureBlock.Section.INTEGRATION, "bi bi-credit-card-fill",
                "Click to'lov tizimi",
                "O'quvchilar Click orqali onlayn to'lov qilishi va chek olishi mumkin. Ma'lumot avtomatik yangilanadi.",
            ),
        ]

        # Avval barcha FEATURE bloklarini deactivate qilamiz (eski uzun matnlar yoki ortiqcha kartalar tozalansin)
        FeatureBlock.objects.filter(section=FeatureBlock.Section.FEATURE).update(is_active=False)

        for index, (section, icon, title, description) in enumerate(feature_rows, start=1):
            FeatureBlock.objects.update_or_create(
                section=section,
                title=title,
                defaults={
                    "description": description,
                    "subtitle": "",
                    "icon": icon,
                    "order": index,
                    "is_active": True,
                    # Lokalizatsiya fieldlarini tozalash — tarjima override bo'lib qolmasin
                    "title_uz": "",
                    "description_uz": "",
                },
            )

    def _seed_pricing(self):
        # Yangi narx tizimi: oylik abonement, 1 filial uchun
        # Standart=400k, Premium=600k (tavsiya), Pro=900k so'm/oy
        plan_defs = [
            {
                "name": "Standart",
                "student_range": "0–200 ta o'quvchi",
                "base_price": 400000,
                "is_recommended": False,
                "badge_text": "",
                "features": [
                    "O'quvchilar va guruhlar boshqaruvi",
                    "Davomat jurnali (kunlik)",
                    "To'lovlar nazorati",
                    "Director dashboard (asosiy statistika)",
                    "1 ta filial",
                ],
                "order": 1,
            },
            {
                "name": "Premium",
                "student_range": "200–500 ta o'quvchi",
                "base_price": 600000,
                "is_recommended": True,
                "badge_text": "Top tavsiya",
                "features": [
                    "Standart dagi hamma imkoniyatlar",
                    "Avtomatik qarzdorlik nazorati",
                    "Ota-ona / o'quvchi shaxsiy panel",
                    "Telegram bot integratsiyasi",
                    "Kengaytirilgan analytics",
                    "Prioritet support",
                ],
                "order": 2,
            },
            {
                "name": "Pro",
                "student_range": "500+ ta o'quvchi",
                "base_price": 900000,
                "is_recommended": False,
                "badge_text": "Ko'p filial",
                "features": [
                    "Premium dagi hamma imkoniyatlar",
                    "Ko'p filial boshqaruvi",
                    "O'qituvchi maoshi avtomatik hisob",
                    "Chuqur analytics va hisobotlar",
                    "Prioritet texnik yordam",
                    "Onboarding sessiya",
                ],
                "order": 3,
            },
        ]

        for plan_def in plan_defs:
            plan, created = PricingPlan.objects.get_or_create(
                name=plan_def["name"],
                student_range=plan_def["student_range"],
                duration_months=1,
                defaults={
                    "old_price": None,
                    "current_price": plan_def["base_price"],
                    "discount_label": "",
                    "badge_text": plan_def["badge_text"],
                    "is_recommended": plan_def["is_recommended"],
                    "is_active": True,
                    "order": plan_def["order"],
                },
            )

            if not plan.features.exists():
                for feature_order, feature_text in enumerate(plan_def["features"], start=1):
                    PricingFeature.objects.create(
                        pricing_plan=plan,
                        text=feature_text,
                        order=feature_order,
                    )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  PricingPlan yaratildi: {plan_def['name']}"))
            else:
                self.stdout.write(self.style.WARNING(f"  PricingPlan mavjud: {plan_def['name']}"))

        # Custom tarif — pricing page da qo'lda qo'shiladi, seed qilmaymiz
        self.stdout.write(self.style.SUCCESS("Pricing planlar yangilandi."))

    def _seed_faq(self):
        rows = [
            (
                1,
                "ChaqmoqApp nima va kim uchun mo'ljallangan?",
                "ChaqmoqApp — o'quv markazlar uchun bulutli boshqaruv tizimi. "
                "Direktor, administrator, o'qituvchi, ota-ona va o'quvchi uchun alohida panellar mavjud. "
                "Davomat, to'lov, qarzdorlik, guruhlar, Telegram va ko'p filiallarni bitta tizimda boshqarasiz.",
            ),
            (
                2,
                "Joriy qilish qancha vaqt oladi?",
                "Odatda 1–2 ish kuni ichida markazingizni to'liq ishga tushiramiz. "
                "Bizning jamoa sizga onboarding sessiya o'tkazib, barcha sozlamalarni bajaradi.",
            ),
            (
                3,
                "Narx qanday hisoblanadi — oyma-oy yoki yillik?",
                "Oylik abonement to'lovida ishlaymiz: Standart 400 000, Premium 600 000, Pro 900 000 so'm/oy. "
                "Uzoq muddatga to'lashda chegirma berilishi mumkin — menejerimiz bilan bog'laning.",
            ),
            (
                4,
                "Telegram integratsiyasi qanday ishlaydi?",
                "ChaqmoqApp o'z Telegram bot integratsiyasiga ega. "
                "To'lov eslatmalari, davomat xabarlari va qarzdorlik bildirishnomalarini avtomatik yuboramiz. "
                "Ota-onalar va o'quvchilar ham Telegram orqali o'z ma'lumotlarini ko'rishi mumkin.",
            ),
            (
                5,
                "Ma'lumotlarim xavfsizmi? Backup qilinadimi?",
                "Ha, barcha ma'lumotlar shifrlangan bulut serverda saqlanadi va kundalik backup qilinadi. "
                "Xodim ketsa ham, eski ma'lumotlar yo'qolmaydi. "
                "Biz ma'lumotlarni faqat siz bilan ishlashimiz uchun foydalanamiz.",
            ),
            (
                6,
                "Ko'p filial boshqarish mumkinmi?",
                "Ha, Pro tarifida bir nechta filiallarni yagona dashboarddan boshqarish mumkin. "
                "Har filial uchun alohida statistika, o'qituvchi va o'quvchilar bazasi saqlash imkoniyati bor.",
            ),
            (
                7,
                "Tarifni keyin o'zgartirish mumkinmi?",
                "Albatta. Markazingiz o'sishiga qarab tarifni istalgan vaqt yangilashingiz mumkin. "
                "Downgrade ham mumkin — menejerimizga xabar yuboring, biz bir kunda hal qilamiz.",
            ),
        ]

        for order, question, answer in rows:
            FAQ.objects.get_or_create(
                question=question,
                defaults={
                    "answer": answer,
                    "order": order,
                    "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS("FAQ'lar yangilandi (7 ta)."))

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
