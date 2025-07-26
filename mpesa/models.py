from django.db import models
from django.utils import timezone
from main.models import WaterBill

class MpesaPayment(models.Model):
    bill = models.ForeignKey(WaterBill, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transaction_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    is_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Payment for {self.bill} - {self.transaction_id}"
