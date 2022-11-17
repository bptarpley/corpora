from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('', nvs_views.home),
    path('about/', nvs_views.info_about),
    path('contributors/', nvs_views.info_contributors),
    path('print-editions/', nvs_views.info_print_editions),
    path('how-to/', nvs_views.info_how_to),
    path('faqs/', nvs_views.info_faqs),
    path('tools/', nvs_views.tools_about),
    path('advanced-search/', nvs_views.tools_advanced_search),
    path('data/', nvs_views.tools_data_extraction),
    path('edition/<str:play_prefix>/', nvs_views.playviewer),
    path('minimap/<str:play_prefix>/', nvs_views.play_minimap),
    path('appendix/<str:play_prefix>/', nvs_views.paratext, {'section': 'Appendix'}),
    path('front/<str:play_prefix>/', nvs_views.paratext, {'section': 'Front Matter'}),
    path('bibliography/<str:play_prefix>/', nvs_views.paratext, {'section': 'Bibliography'}),
    path('witnessmeter/<str:witness_flags>/<str:height>/<str:width>/<str:inactive_color_hex>/<str:label_buffer>/', nvs_views.witness_meter),
    path('search/<str:play_prefix>/', nvs_views.api_search),
    path('search/', nvs_views.api_search),
    path('lines/<str:play_prefix>/', nvs_views.api_lines),
    path('lines/<str:play_prefix>/<str:starting_line_id>/', nvs_views.api_lines),
    path('lines/<str:play_prefix>/<str:starting_line_id>/<str:ending_line_id>/', nvs_views.api_lines),
]
