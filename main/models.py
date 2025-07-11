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
    reading = models.BigIntegerField(null=True)
    meter_consumption = models.BigIntegerField(null=True)
    status = models.TextField(choices=(('Paid','Paid'),('Pending', 'Pending')), default='Pending', null=True)
    duedate = models.DateField(null=True)
    penaltydate = models.DateField(null=True)
    created_on = models.DateTimeField(auto_now_add=True, null=True)
    checkout_request_id = models.CharField(max_length=100, null=True, blank=True)

    
    def compute_bill(self):
        metric = Metric.objects.get(id=1)
        consump_amount = metric.consump_amount
        return self.meter_consumption * consump_amount

    def penalty(self):
        if self.penaltydate == datetime.date.today():
            metric = Metric.objects.get(id=1)
            penalty_cost = metric.penalty_amount
            return penalty_cost
        else:
            return 0

    
    def payable(self):
        if self.penalty:
            return self.compute_bill() + self.penalty()
        else:
            return self.compute_bill()


    def __str__(self):
        return f'{self.name}'


class Metric(models.Model):
    consump_amount = models.FloatField(default=1, null=True)
    penalty_amount = models.FloatField(default=1, null=True)