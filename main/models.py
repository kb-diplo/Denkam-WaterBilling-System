from django.db import models
from account.models import *
import datetime
import string, secrets


class Client(models.Model):
    name = models.OneToOneField(Account, on_delete=models.CASCADE, null=True)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    meter_number = models.BigIntegerField(null=True)
    middle_name = models.CharField(max_length=30, null=True, blank=True)
    contact_number = models.CharField(null=True, unique=True, max_length=13)
    address = models.CharField(max_length=250)
    status = models.TextField(choices=(('Connected', 'Connected'), ('Disconnected', 'Disconnected'), ('Pending', 'Pending')))
    account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Generate account number only when creating a new client
        if self._state.adding and not self.account_number:
            # Find the highest existing account number to avoid collisions
            last_client = Client.objects.all().order_by('id').last()
            if last_client:
                # Increment the last ID to create a new one
                new_id = last_client.id + 1
            else:
                # If no clients exist, start from 1
                new_id = 1
            self.account_number = f'DWB-{new_id:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        # Prioritize Client model's own name fields, fallback to Account if needed
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.name and self.name.first_name and self.name.last_name:
            return f"{self.name.first_name} {self.name.last_name}"
        return f"Client {self.id}" # Fallback if no name is available


class WaterBill(models.Model):
    created_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bills')
    name = models.ForeignKey(Client, on_delete=models.CASCADE)
    reading = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    meter_consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    status = models.TextField(choices=(('Paid','Paid'),('Pending', 'Pending'),('Partially Paid', 'Partially Paid')), default='Pending', null=True)
    duedate = models.DateField(null=True)
    penaltydate = models.DateField(null=True)
    created_on = models.DateTimeField(auto_now_add=True, null=True)
    checkout_request_id = models.CharField(max_length=100, null=True, blank=True)

    
    @property
    def metrics(self):
        if not hasattr(self, '_metrics'):
            self._metrics = Metric.objects.first()
        return self._metrics

    def compute_bill(self):
        if self.metrics and self.metrics.consump_amount and self.meter_consumption is not None:
            return self.meter_consumption * self.metrics.consump_amount
        return 0

    def penalty(self):
        if self.metrics and self.metrics.penalty_amount and self.penaltydate == datetime.date.today():
            return self.metrics.penalty_amount
        return 0

    
    def payable(self):
        bill = self.compute_bill()
        pen = self.penalty()
        return bill + pen


    def total_cash_paid(self):
        return self.cash_payments.aggregate(total=models.Sum('amount_paid'))['total'] or 0

    @property
    def total_paid(self):
        cash_paid = self.total_cash_paid()
        mpesa_paid = self.mpesa_payments.aggregate(total=models.Sum('amount'))['total'] or 0
        return cash_paid + mpesa_paid

    @property
    def balance_due(self):
        return self.payable() - self.total_paid

    def update_status_based_on_payments(self):
        """Update bill status based on actual payment records"""
        total_paid = self.total_paid
        total_due = self.payable()
        
        if total_paid <= 0:
            # No payments made
            self.status = 'Pending'
        elif total_paid >= total_due:
            # Fully paid or overpaid
            self.status = 'Paid'
        else:
            # Partially paid
            self.status = 'Partially Paid'
        
        self.save()
        return self.status

    def has_payment_records(self):
        """Check if bill has any payment records (cash or mpesa)"""
        has_cash = self.cash_payments.exists()
        has_mpesa = self.mpesa_payments.filter(result_code=0).exists()
        return has_cash or has_mpesa

    def __str__(self):
        return f'{self.name}'


class Metric(models.Model):
    consump_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)



import uuid

class CashPayment(models.Model):
    bill = models.ForeignKey(WaterBill, on_delete=models.CASCADE, related_name='cash_payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.CharField(max_length=100, unique=True, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey('account.Account', on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = f'CASH-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Cash Payment {self.reference_id} for Bill {self.bill.id}'


class MpesaPayment(models.Model):
    bill = models.ForeignKey(WaterBill, on_delete=models.CASCADE, related_name='mpesa_payments', null=True)
    transaction_id = models.CharField(max_length=50, unique=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    phone_number = models.CharField(max_length=15, null=True)
    checkout_request_id = models.CharField(max_length=100)
    result_code = models.IntegerField()
    result_desc = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.transaction_id} for bill {self.bill.id if self.bill else 'N/A'}"