from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import MeterReading, WaterBill, BillingRate
from decimal import Decimal, ROUND_HALF_UP
import datetime

class Command(BaseCommand):
    help = 'Generate a bill for a meter reading'

    def handle(self, *args, **options):
        # Check if we have any meter readings
        if not MeterReading.objects.exists():
            self.stdout.write(
                self.style.ERROR('No meter readings found')
            )
            return
        
        # Get the first meter reading
        reading = MeterReading.objects.first()
        self.stdout.write(f'Generating bill for reading: {reading}')
        
        # Check if a bill already exists for this reading
        if hasattr(reading, 'water_bill') and reading.water_bill:
            self.stdout.write(
                self.style.WARNING(f'Bill already exists for this reading: {reading.water_bill}')
            )
            return
        
        # Get or create a billing rate
        rate_obj, created = BillingRate.objects.get_or_create(
            name='Standard Rate',
            defaults={
                'rate': Decimal('10.00'),
                'min_consumption': Decimal('0.00'),
                'effective_date': timezone.now().date(),
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created new billing rate')
            )
        
        # Calculate consumption (for first reading, we'll use the reading value)
        consumption = reading.reading_value
        
        # Calculate amount and round to 2 decimal places
        amount = (consumption * rate_obj.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate due date (15 days from today)
        due_date = timezone.now().date() + datetime.timedelta(days=15)
        
        # Create the bill
        bill = WaterBill.objects.create(
            client=reading.client,
            meter_reading=reading,
            consumption=consumption.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            rate=rate_obj.rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            amount=amount,
            total_amount=amount,  # No penalty for now
            status='Pending',
            billing_date=timezone.now().date(),
            due_date=due_date,
            created_by=reading.read_by
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created bill: {bill}')
        )
