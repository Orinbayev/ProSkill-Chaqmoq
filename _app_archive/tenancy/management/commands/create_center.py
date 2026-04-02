from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from django_tenants.utils import schema_context

from tenancy.models import EducationCenter, CenterDomain, Plan


class Command(BaseCommand):
    help = "Create tenant (EducationCenter) + domain + director(superuser) inside tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Center name (display)")
        parser.add_argument("--schema", required=True, help="Schema name ex: olimp")
        parser.add_argument("--domain", required=True, help="Domain ex: olimp.localhost or olimp.chaqmoq.uz")

        # Director
        parser.add_argument("--email", required=True, help="Director login email")
        parser.add_argument("--password", required=True, help="Director password")

        # Director profile fields (sizning User modelga mos)
        parser.add_argument("--ism", default="Admin", help="Director ism")
        parser.add_argument("--familya", default="Adminov", help="Director familya")
        parser.add_argument("--telefon1", default="+998900000000", help="Director telefon1")
        parser.add_argument("--manzil", default="Markaz manzili kiritilmagan", help="Center manzil")

        # Billing/Plan
        parser.add_argument("--plan", default="Basic", help="Plan name (creates if missing)")
        parser.add_argument("--paid_days", type=int, default=30, help="Paid days from today")

    def handle(self, *args, **options):
        name = options["name"].strip()
        schema = options["schema"].strip().lower()
        domain = options["domain"].strip().lower()

        email = options["email"].strip().lower()
        password = options["password"]

        ism = options["ism"].strip()
        familya = options["familya"].strip()
        telefon1 = options["telefon1"].strip()
        manzil = options["manzil"].strip()

        plan_name = options["plan"].strip()
        paid_days = options["paid_days"]

        if schema == "public":
            raise CommandError("Schema 'public' ishlatib bo‘lmaydi.")

        # Plan
        plan, _ = Plan.objects.get_or_create(name=plan_name)

        paid_until = timezone.now().date() + timezone.timedelta(days=paid_days)

        # 1) Tenant yaratamiz (schema ham auto yaratadi)
        tenant = EducationCenter.objects.create(
            name=name,
            schema_name=schema,
            plan=plan,
            paid_until=paid_until,
            is_active=True,
        )

        # 2) Domain bog‘laymiz
        CenterDomain.objects.create(
            domain=domain,
            tenant=tenant,
            is_primary=True,
        )

        # 3) Tenant schema ichida director user yaratamiz + Center row yaratamiz
        User = get_user_model()

        with schema_context(tenant.schema_name):
            # tenant ichidagi accounts.Center modelini import qilamiz
            from accounts.models import Center, Roles  # noqa

            # Center row (sizning eski logikangiz buzilmasin deb)
            center_obj = Center.objects.create(nom=name, manzil=manzil)

            if User.objects.filter(email=email).exists():
                raise CommandError(f"User {email} allaqachon bor (tenant ichida).")

            director = User.objects.create_superuser(
                email=email,
                password=password,
                ism=ism,
                familya=familya,
                telefon1=telefon1,
                role=Roles.DIREKTOR,
                center=center_obj,
                lavozim="Direktor",
            )
            director.save()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Center created: {name} | schema={schema} | domain={domain} | director={email}"
        ))
