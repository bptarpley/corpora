from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('', nvs_views.home),
    path('edition/<str:play_prefix>/', nvs_views.playviewer),
    path('minimap/<str:play_prefix>/', nvs_views.play_minimap),
    path('appendix/<str:play_prefix>/', nvs_views.paratext, {'section': 'Appendix'}),
    path('front/<str:play_prefix>/', nvs_views.paratext, {'section': 'Front Matter'}),
    path('witnessmeter/<str:witness_flags>/<str:height>/<str:width>/<str:inactive_color_hex>/<str:label_buffer>/', nvs_views.witness_meter),
    path('search/<str:play_prefix>/', nvs_views.api_search),
    path('search/', nvs_views.api_search),
]
