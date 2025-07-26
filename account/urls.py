from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'account'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.customer_register_view, name='register'),
    path('register/admin/', views.admin_register_view, name='admin_register'),
    path('', views.landingpage, name="landingpage"),
    path('dashboard/meter-reading/', views.meter_reading_dashboard, name='meter_reading_dashboard'),
    path('admin/register_user/', views.admin_register_user_view, name='admin_register_user'),

    # Password reset
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='account/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='account/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='account/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='account/password_reset_complete.html'), name='password_reset_complete'),
]
