from django.contrib import admin
from .models import Client, WaterBill, BillingRate, MeterReading, Metric

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'meter_number', 'status', 'contact_number', 'created_at')
    search_fields = ('first_name', 'last_name', 'meter_number', 'contact_number')
    list_filter = ('status', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('client', 'reading_value', 'reading_date', 'is_billed')
    search_fields = ('client__first_name', 'client__last_name', 'client__meter_number')
    list_filter = ('is_billed', 'reading_date')
    date_hierarchy = 'reading_date'
    raw_id_fields = ('client', 'read_by')

@admin.register(WaterBill)
class WaterBillAdmin(admin.ModelAdmin):
    list_display = ('client', 'billing_date', 'due_date', 'consumption', 'amount', 'status')
    search_fields = ('client__first_name', 'client__last_name', 'id')
    list_filter = ('status', 'billing_date', 'due_date')
    date_hierarchy = 'billing_date'
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('client', 'meter_reading', 'created_by')

@admin.register(BillingRate)
class BillingRateAdmin(admin.ModelAdmin):
    list_display = ('name', 'rate', 'min_consumption', 'max_consumption', 'effective_date', 'is_active')
    list_filter = ('is_active', 'effective_date')
    search_fields = ('name',)
    date_hierarchy = 'effective_date'



@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('consump_amount', 'penalty_amount')
    readonly_fields = ()

    def has_add_permission(self, request):
        # Allow only one instance of Metric
        return not Metric.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the only instance
        return False




