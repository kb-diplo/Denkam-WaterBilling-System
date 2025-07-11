from django.urls import path
from . import views
from .views import meter_reader_register_user_view
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('meter-reader/register-client/', meter_reader_register_user_view, name='meter_reader_register_user'),
    path('', views.landingpage, name="landingpage"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),

    path('register/', views.customer_register_view, name='register'),
    path('register/meter-reader/', views.meter_reader_register_view, name='meter_reader_register'),
    path('register/admin/', views.admin_register_view, name='admin_register'),
    path('verify', views.verify, name="verify"),
    path('dashboard/meter-reader/', views.meter_reader_dashboard, name='meter_reader_dashboard'),
    path('admin/register_user/', views.admin_register_user_view, name='admin_register_user'),

    # Password reset
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='account/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='account/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='account/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='account/password_reset_complete.html'), name='password_reset_complete'),
]
