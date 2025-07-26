from django.core.management.base import BaseCommand
from django.utils import timezone
from main.models import WaterBill
from mpesa.models import MpesaPayment
from decimal import Decimal

class Command(BaseCommand):
    help = 'Record a payment for a bill'

    def handle(self, *args, **options):
        # Check if we have any bills
        if not WaterBill.objects.exists():
            self.stdout.write(
                self.style.ERROR('No bills found')
            )
            return
        
        # Get the first bill
        bill = WaterBill.objects.first()
        self.stdout.write(f'Recording payment for bill: {bill}')
        
        # Check if a payment already exists for this bill
        if MpesaPayment.objects.filter(bill=bill).exists():
            self.stdout.write(
                self.style.WARNING(f'Payment already exists for this bill')
            )
            return
        
        # Create a payment
        payment = MpesaPayment.objects.create(
            bill=bill,
            phone_number='254700123456',
            amount=bill.total_amount,
            transaction_id='TEST_TRANSACTION_001',
            is_successful=True
        )
        
        # Update the bill status to 'Paid'
        bill.status = 'Paid'
        bill.payment_date = timezone.now().date()
        bill.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully recorded payment: {payment}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Bill status updated to: {bill.status}')
        )
