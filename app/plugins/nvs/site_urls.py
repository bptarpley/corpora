from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('play/<str:play_prefix>/', nvs_views.design),
]
