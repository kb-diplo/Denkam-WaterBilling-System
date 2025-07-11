from django.urls import path
from . import views

urlpatterns = [
    path('initiate/<int:bill_id>/', views.initiate_payment, name='initiate_mpesa_payment'),
    path('callback/', views.mpesa_callback, name='mpesa_callback'),
]
