from billing.models import PlanFeature, SubscriptionPlan
from django.db import transaction

@transaction.atomic
def run():
    # 1. Clear existing features
    # NOTE: This might affect existing plans, but user asked for a clean-up.
    PlanFeature.objects.all().delete()

    # 2. Define the Top 10 Features
    features_to_create = [
        # CORE
        {
            "code": "dashboard",
            "name": "Asosiy Dashboard",
            "description": "Tizimning umumiy holati va KPI ko'rsatkichlari",
            "category": "core",
            "is_core": True,
            "order": 1
        },
        {
            "code": "students",
            "name": "O'quvchilar va Guruhlar",
            "description": "Talabalar bazasini yuritish va guruhlarga taqsimlash",
            "category": "core",
            "is_core": True,
            "order": 2
        },
        {
            "code": "attendance",
            "name": "Davomat va Jadval",
            "description": "Darslarga keldi-ketdi hisobi va dars jadvali",
            "category": "core",
            "is_core": True,
            "order": 3
        },
        # FINANCE
        {
            "code": "finance",
            "name": "Moliya va To'lovlar",
            "description": "To'lovlarni qabul qilish va qarzdorlar nazorati",
            "category": "finance",
            "is_core": True,
            "order": 4
        },
        {
            "code": "salaries",
            "name": "Xodimlar va Ish xaqi",
            "description": "O'qituvchilar kabineti va foizli ish xaqi",
            "category": "finance",
            "is_core": False,
            "order": 5
        },
        {
            "code": "analytics",
            "name": "Biznes Analitika",
            "description": "Daromadlar tahlili va moliya hisobotlari",
            "category": "finance",
            "is_core": False,
            "order": 6
        },
        # MARKETING
        {
            "code": "sms",
            "name": "SMS va Bildirishnomalar",
            "description": "Ommaviy va avtomatik SMS xabarnomalar",
            "category": "marketing",
            "is_core": False,
            "order": 7
        },
        {
            "code": "leads",
            "name": "CRM Huni (Lidlar)",
            "description": "Yangi kelib tushayotgan so'rovlar bilan ishlash",
            "category": "marketing",
            "is_core": False,
            "order": 8
        },
        # TEAM
        {
            "code": "roles",
            "name": "Rollar va Huquqlar",
            "description": "Xodimlar uchun alohida ruxsatlar to'plami",
            "category": "team",
            "is_core": False,
            "order": 9
        },
        # ADVANCED
        {
            "code": "branches",
            "name": "Filiallar Boshqaruvi",
            "description": "Bir nechta filialni bitta tizimda boshqarish",
            "category": "advanced",
            "is_core": False,
            "order": 10
        }
    ]

    for f_data in features_to_create:
        PlanFeature.objects.create(**f_data)

    print(f"Successfully created {len(features_to_create)} key features.")

    # 3. Setup Default SaaS Tiers
    # Standard | Premium | Pro
    
    # Prices: 400k | 600k | 900k
    plans = [
        {
            "code": "STANDARD",
            "tier": 10,
            "title": "Standard (Kichik markaz)",
            "monthly_price": 400000,
            "price_3m": 1050000,
            "price_6m": 1800000,
            "price_9m": 2300000,
            "price_12m": 2760000,
            "max_students": 70,
            "is_popular": False,
            "features_to_add": ["dashboard", "students", "attendance", "finance"]
        },
        {
            "code": "PREMIUM",
            "tier": 20,
            "title": "Premium (O'sib borayotgan)",
            "monthly_price": 600000,
            "price_3m": 1500000,
            "price_6m": 2700000,
            "price_9m": 3500000,
            "price_12m": 4200000,
            "max_students": 200,
            "is_popular": True,
            "features_to_add": ["dashboard", "students", "attendance", "finance", "salaries", "analytics", "sms"]
        },
        {
            "code": "PRO",
            "tier": 30,
            "title": "PRO (Professional)",
            "monthly_price": 900000,
            "price_3m": 2400000,
            "price_6m": 4200000,
            "price_9m": 5200000,
            "price_12m": 6000000,
            "max_students": 99999, # Unlimited
            "is_popular": False,
            "features_to_add": ["dashboard", "students", "attendance", "finance", "salaries", "analytics", "sms", "leads", "roles", "branches"]
        }
    ]

    for p_data in plans:
        f_codes = p_data.pop("features_to_add")
        # Ensure groups/users are unlimited
        p_data["max_groups"] = 9999
        p_data["max_users"] = 9999
        
        plan, created = SubscriptionPlan.objects.update_or_create(
            code=p_data["code"],
            defaults=p_data
        )
        plan.plan_features.set(PlanFeature.objects.filter(code__in=f_codes))
        print(f"Set up plan: {plan.code}")

if __name__ == "__main__":
    run()
