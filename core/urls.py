from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf.urls.static import static
from . import settings


urlpatterns = [
    path('', include("main.urls")),
    path('', include("account.urls")),
    path('admin/', admin.site.urls),
    path('mpesa/', include('mpesa.urls')),  
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
