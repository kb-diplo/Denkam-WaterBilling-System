from django.urls import path
from .views import (
    landingpage, dashboard, client_dashboard, meter_reader_dashboard, ongoing_bills, history_bills, update_bills, delete_bills, profile, 
    users, add_as_client, update_user, delete_user, register_customer, clients, client_update, client_delete, metrics, metricsupdate, meter_reading, add_meter_reading,
    client_bill_history, manage_billing, reports, initiate_mpesa_payment, mpesa_callback, payment_records, generate_bill_pdf, generate_client_list_pdf, delete_bill, admin_send_stk_push, generate_bills, select_client_for_payment, record_cash_payment, view_receipt, select_payment_method, record_cash_payment_for_bill, unified_billing_management, download_billing_history, bulk_download_receipts
)

urlpatterns = [
    path('', landingpage, name='landingpage'),
    path('dashboard/', dashboard, name='dashboard'),

    path('client/dashboard/', client_dashboard, name='client_dashboard'),
    path('dashboard/meter-reader/', meter_reader_dashboard, name='meter_reader_dashboard'),

    path('profile/<int:pk>/', profile, name='profile'),

    path('users/', users, name='users'),
    path('user/add/', register_customer, name='register_customer'),
    path('user/update/<int:pk>/', update_user, name='update_user'),
    path('user/delete/<int:pk>/', delete_user, name='delete_user'),

    path('clients/', clients, name='clients'),
    path('client/add_as_client/<int:pk>/', add_as_client, name='add_as_client'),
    path('client/update/<int:pk>/', client_update, name='client_update'),
    path('client/delete/<int:pk>/', client_delete, name='client_delete'),
    path('client/<int:pk>/history/', client_bill_history, name='client_billing_history'),
    path('clients/pdf/', generate_client_list_pdf, name='generate_client_list_pdf'),

    path('bills/ongoing/', ongoing_bills, name='ongoing_bills'),
    path('bills/history/', history_bills, name='history_bills'),
    path('bills/history/download/', download_billing_history, name='download_billing_history'),
    path('billing/generate/', generate_bills, name='generate_bills'),
    path('billing/management/', unified_billing_management, name='unified_billing_management'),
    path('billing/record_payment/', select_client_for_payment, name='select_client_for_payment'),
    path('billing/record_payment/<int:client_id>/', record_cash_payment, name='record_cash_payment'),
    path('bill/delete/<int:bill_id>/', delete_bill, name='delete_bill'),
    path('admin/send_stk/<int:bill_id>/', admin_send_stk_push, name='admin_send_stk_push'),
    path('bill/update/<int:pk>/', update_bills, name='update_bills'),
    path('bill/delete/<int:pk>/', delete_bills, name='delete_bills'),
    path('bill/pdf/<int:bill_id>/', generate_bill_pdf, name='generate_bill_pdf'),

    path('meter-reading/', meter_reading, name='meter_reading'),
    path('add-meter-reading/<int:client_id>/', add_meter_reading, name='add_meter_reading'),
    path('billing/manage/<int:client_id>/', manage_billing, name='manage_billing'),

    path('metrics/', metrics, name='metrics'),
    path('metrics/update/<int:pk>/', metricsupdate, name='metrics_update'),

    path('reports/', reports, name='reports'),
    path('receipt/<int:bill_id>/', view_receipt, name='view_receipt'),
    path('bulk-download-receipts/', bulk_download_receipts, name='bulk_download_receipts'),

    path('payment-records/', payment_records, name='payment_records'),
    path('initiate-mpesa-payment/<int:bill_id>/', initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('mpesa/callback/', mpesa_callback, name='mpesa_callback'),
    
    # New payment method selection URLs
    path('payment/select-method/<int:bill_id>/', select_payment_method, name='select_payment_method'),
    path('payment/cash/<int:bill_id>/', record_cash_payment_for_bill, name='record_cash_payment_for_bill'),
]
