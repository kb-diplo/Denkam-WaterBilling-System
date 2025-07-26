from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import datetime
import re
from account.models import Account

# Import the Account model from the account app


class Metric(models.Model):
    """Model to store system metrics like consumption and penalty rates."""
    consump_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Amount charged per unit of water consumed'
    )
    penalty_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Additional amount charged for late payments'
    )

    class Meta:
        verbose_name = 'Metric'
        verbose_name_plural = 'Metrics'

    def __str__(self):
        return f"Consumption: {self.consump_amount}, Penalty: {self.penalty_amount}"

    def save(self, *args, **kwargs):
        # Ensure there's only one instance
        if Metric.objects.exists() and not self.pk:
            # Update the existing instance instead of creating a new one
            existing = Metric.objects.first()
            existing.consump_amount = self.consump_amount
            existing.penalty_amount = self.penalty_amount
            return existing.save(*args, **kwargs)
        return super().save(*args, **kwargs)


class Client(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='client_profile')
    meter_number = models.BigIntegerField(null=True, unique=True)
    middle_name = models.CharField(max_length=30, null=True, blank=True)
    contact_number = models.CharField(max_length=15, unique=True, null=True)
    address = models.CharField(max_length=250)
    status = models.CharField(
        max_length=15,
        choices=(
            ('Connected', 'Connected'),
            ('Disconnected', 'Disconnected'),
            ('Pending', 'Pending')
        ),
        default='Pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.account.last_name and self.account.first_name:
            return f"{self.account.last_name}, {self.account.first_name}"
        elif self.meter_number:
            return f"Client {self.meter_number}"
        return f"Client {self.id}"
    
    @property
    def first_name(self):
        return self.account.first_name if self.account else None
    
    @property
    def last_name(self):
        return self.account.last_name if self.account else None
    
    @property
    def email(self):
        return self.account.email if self.account else None
    
    def clean(self):
        super().clean()
        # Validate contact number format
        if self.contact_number and not re.match(r'^\+?1?\d{9,15}$', self.contact_number):
            raise ValidationError({
                'contact_number': _('Enter a valid phone number (e.g., +254712345678).')
            })
        
        # Ensure meter number is unique
        if self.meter_number and Client.objects.filter(
            meter_number=self.meter_number
        ).exclude(id=self.id).exists():
            raise ValidationError({
                'meter_number': _('A client with this meter number already exists.')
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class MeterReading(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='meter_readings')
    reading_value = models.DecimalField(max_digits=10, decimal_places=2)
    reading_date = models.DateField(auto_now_add=True)
    read_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    is_billed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-reading_date']
        verbose_name = 'Meter Reading'
        verbose_name_plural = 'Meter Readings'
        unique_together = ('client', 'reading_date')

    def __str__(self):
        client_str = str(self.client) if self.client else f"Client {self.client_id}"
        return f"Reading {self.reading_value} for {client_str} on {self.reading_date}"
    
    def clean(self):
        super().clean()
        # Prevent future-dated readings
        if self.reading_date and self.reading_date > datetime.date.today():
            raise ValidationError({
                'reading_date': _('Reading date cannot be in the future.')
            })
        
        # Ensure reading value is positive
        if self.reading_value and self.reading_value <= 0:
            raise ValidationError({
                'reading_value': _('Reading value must be positive.')
            })
        
        # Check for duplicate readings on the same day
        if self.reading_date and MeterReading.objects.filter(
            client=self.client,
            reading_date=self.reading_date
        ).exclude(pk=self.pk).exists():
            raise ValidationError({
                'reading_date': _('A reading already exists for this client on this date.')
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class WaterBill(models.Model):
    STATUS_CHOICES = (
        ('Paid', 'Paid'),
        ('Pending', 'Pending'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled')
    )
    
    created_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bills')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='bills', null=True)
    meter_reading = models.OneToOneField(MeterReading, on_delete=models.CASCADE, related_name='water_bill', null=True)
    consumption = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    billing_date = models.DateField(default=datetime.date.today)
    due_date = models.DateField(default=datetime.date.today)
    payment_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-billing_date', 'client']
        verbose_name = 'Water Bill'
        verbose_name_plural = 'Water Bills'

    def __str__(self):
        client_str = str(self.client) if self.client else f"Client {self.client_id}"
        return f'Bill {self.id} - {client_str} - {self.amount} ({self.status})'
    
    def clean(self):
        super().clean()
        # Ensure due date is after billing date
        if self.due_date and self.billing_date and self.due_date <= self.billing_date:
            raise ValidationError({
                'due_date': _('Due date must be after the billing date.')
            })
        
        # Ensure payment date is after billing date if provided
        if self.payment_date and self.billing_date and self.payment_date < self.billing_date:
            raise ValidationError({
                'payment_date': _('Payment date cannot be before the billing date.')
            })
        
        # Auto-calculate amount if not provided
        if not self.amount and self.consumption is not None and self.rate is not None:
            self.amount = self.consumption * self.rate
        
        # Calculate total amount
        self.total_amount = self.amount + (self.penalty_amount or 0)
        
        # Update status based on payment
        if self.payment_date:
            self.status = 'Paid'
        elif self.due_date and self.due_date < datetime.date.today() and self.status != 'Paid':
            self.status = 'Overdue'
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class BillingRate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, help_text='Rate per unit of consumption')
    min_consumption = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Minimum consumption for this rate tier')
    max_consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Maximum consumption for this rate tier (leave blank for no maximum)')
    effective_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['min_consumption']
        verbose_name = 'Billing Rate'
        verbose_name_plural = 'Billing Rates'

    def __str__(self):
        return f"{self.name} - {self.rate} per unit ({self.min_consumption}-{self.max_consumption or '∞'})"
    
    def clean(self):
        super().clean()
        # Ensure max_consumption is greater than min_consumption if provided
        if self.max_consumption is not None and self.max_consumption <= self.min_consumption:
            raise ValidationError({
                'max_consumption': _('Maximum consumption must be greater than minimum consumption.')
            })
        
        # Ensure date ranges are valid
        if self.end_date and self.end_date < self.effective_date:
            raise ValidationError({
                'end_date': _('End date must be after the effective date.')
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)