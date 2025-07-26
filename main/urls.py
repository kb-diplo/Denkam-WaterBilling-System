from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    # Landing Page
    path('', views.landingpage, name='landingpage'),

    # Dashboard URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('meter-reader-dashboard/', views.meter_reader_requirements, name='meter_reader_dashboard'),
    path('meter-reader-requirements/', views.meter_reader_requirements, name='meter_reader_requirements'),
    path('client-dashboard/', views.client_dashboard, name='client_dashboard'),

    # User and Profile URLs
    path('profile/<int:pk>/', views.profile, name='profile'),
    path('users/', views.users, name='users'),
    path('users/update/<int:pk>/', views.update_user, name='update_user'),
    path('users/delete/<int:pk>/', views.delete_user, name='delete_user'),
    path('users/add_as_client/<int:pk>/', views.add_as_client, name='add_as_client'),

    # Client URLs
    path('clients/', views.clients, name='clients'),
    path('clients/delete/<int:pk>/', views.client_delete, name='client_delete'),
    path('clients/update/<int:pk>/', views.client_update, name='client_update'),
    path('clients/billing-history/<int:pk>/', views.client_billing_history, name='client_billing_history'),
    path('clients/register/', views.register_customer, name='register_customer'),

    # Bill URLs
    path('bills/ongoing/', views.ongoing_bills, name='ongoingbills'),
    path('bills/history/', views.history_bills, name='billshistory'),
    path('bills/update/<int:pk>/', views.update_bills, name='update_bills'),
    path('bills/delete/<int:pk>/', views.delete_bills, name='delete_bills'),

    # Meter Reading URLs
    path('meter-reading/', views.meter_reading, name='meter_reading'),
    path('meter-reading/add/<int:client_id>/', views.add_meter_reading, name='add_meter_reading'),
    path('meter-reading/manage/<int:client_id>/', views.manage_billing, name='manage_billing'),
    path('client-bill-history/<int:pk>/', views.client_bill_history, name='client_bill_history'),

    # Metrics URLs
    path('metrics/', views.metrics, name='metrics'),
    path('metrics/update/<int:pk>/', views.metricsupdate, name='metricsupdate'),

    # Payment URLs
    path('payment/initiate/<int:bill_id>/', views.initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('payment/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('payment/records/', views.payment_records, name='payment_records'),
    path('payment/record/<int:bill_id>/', views.record_payment, name='record_payment'),

    # Report URLs
    path('reports/', views.reports, name='reports'),
    path('reports/pdf/bill/<int:bill_id>/', views.generate_bill_pdf, name='generate_bill_pdf'),
    path('reports/pdf/clients/', views.generate_client_list_pdf, name='generate_client_list_pdf'),
]
