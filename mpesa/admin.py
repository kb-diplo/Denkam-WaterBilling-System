from django.contrib import admin

from main.models import MpesaPayment

@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'bill', 'amount', 'phone_number', 'created_at')
    search_fields = ('transaction_id', 'bill__name__first_name', 'bill__name__last_name')
    list_filter = ('created_at',)

    # Payments should be read-only in the admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
