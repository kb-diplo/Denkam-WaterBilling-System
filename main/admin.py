from django.contrib import admin
from .models import *


admin.site.register(WaterBill)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'meter_number', 'status', 'contact_number')
    search_fields = ('first_name', 'last_name', 'meter_number')
    list_filter = ('status',)

admin.site.register(Client, ClientAdmin)
admin.site.register(Metric)


