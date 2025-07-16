from django.contrib import admin
from .models import Client, WaterBill, Metric

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'meter_number', 'status', 'contact_number')
    search_fields = ('first_name', 'last_name', 'meter_number')
    list_filter = ('status',)

@admin.register(WaterBill)
class WaterBillAdmin(admin.ModelAdmin):
    list_display = ('name', 'reading', 'meter_consumption', 'status', 'duedate', 'payable')
    search_fields = ('name__first_name', 'name__last_name')
    list_filter = ('status', 'duedate')
    readonly_fields = ('payable',)

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('consump_amount', 'penalty_amount')

    def has_add_permission(self, request):
        # Prevent adding new metrics if one already exists
        return Metric.objects.count() == 0





