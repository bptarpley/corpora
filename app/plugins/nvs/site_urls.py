from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('', nvs_views.splash),
    path('play/<str:play_prefix>/', nvs_views.playviewer),
    path('minimap/<str:play_prefix>/', nvs_views.play_minimap),
    path('paratext/<str:play_prefix>/<str:section>/', nvs_views.paratext),
    path('witnessmeter/<str:witness_flags>/<str:height>/<str:width>/<str:inactive_color_hex>/', nvs_views.witness_meter),
    path('search/<str:play_prefix>/', nvs_views.api_search),
    path('search/', nvs_views.api_search),
]
