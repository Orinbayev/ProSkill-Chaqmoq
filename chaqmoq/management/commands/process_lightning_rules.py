from django.core.management.base import BaseCommand
from chaqmoq.services import apply_payment_discipline_penalties

class Command(BaseCommand):
    help = 'Processes automatic lightning rules (attendance and payment discipline)'

    def handle(self, *args, **options):
        self.stdout.write("Processing lightning rules...")
        
        # 1. Payment Discipline Penalties
        # This will check all centers and apply penalties if deadline is passed
        count = apply_payment_discipline_penalties()
        
        self.stdout.write(self.style.SUCCESS(f"Applied {count} payment discipline penalties."))
        self.stdout.write("Finished processing.")
