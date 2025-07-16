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

    def __str__(self):
        return f"{self.last_name}, {self.first_name}"


class WaterBill(models.Model):
    created_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bills')
    name = models.ForeignKey(Client, on_delete=models.CASCADE)
    reading = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    meter_consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    status = models.TextField(choices=(('Paid','Paid'),('Pending', 'Pending')), default='Pending', null=True)
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


    def __str__(self):
        return f'{self.name}'


class Metric(models.Model):
    consump_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True)


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