from django.contrib import admin
from django.urls import path, include, reverse
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Redirect for incorrect admin register user URL
    path('admin/register_user/', lambda request: redirect(reverse('account:admin_register_user'))),
    
    path('admin/', admin.site.urls),
    path('', include('main.urls', namespace='main')),
    path('', include('account.urls', namespace='account')),
    path('mpesa/', include('mpesa.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
