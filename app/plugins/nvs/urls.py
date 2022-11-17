from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('corpus/<str:corpus_id>/home/', nvs_views.home),
    path('corpus/<str:corpus_id>/frontmatter/', nvs_views.frontmatter),
    path('corpus/<str:corpus_id>/appendix/', nvs_views.appendix),
    path('corpus/<str:corpus_id>/bibliography/', nvs_views.bibliography),
    path('corpus/<str:corpus_id>/about/', nvs_views.info_about),
    path('corpus/<str:corpus_id>/contributors/', nvs_views.info_contributors),
    path('corpus/<str:corpus_id>/print/', nvs_views.info_print_editions),
    path('corpus/<str:corpus_id>/how-to/', nvs_views.info_how_to),
    path('corpus/<str:corpus_id>/faqs/', nvs_views.info_faqs),
    path('corpus/<str:corpus_id>/tools/', nvs_views.tools_about),
    path('corpus/<str:corpus_id>/search/', nvs_views.tools_advanced_search),
    path('corpus/<str:corpus_id>/data/', nvs_views.tools_data_extraction),
    path('corpus/<str:corpus_id>/play-viewer/<str:play_prefix>/', nvs_views.playviewer),
    path('corpus/<str:corpus_id>/play-minimap/<str:play_prefix>/', nvs_views.play_minimap),
    path('corpus/<str:corpus_id>/play-bibliography/<str:play_prefix>/', nvs_views.bibliography),
    path('corpus/<str:corpus_id>/paratext-viewer/<str:play_prefix>/<str:section>/', nvs_views.paratext),
    path('nvs/witness-meter/<str:witness_flags>/<str:height>/<str:width>/<str:inactive_color_hex>/<str:label_buffer>/', nvs_views.witness_meter),
    path('api/corpus/<str:corpus_id>/nvs-search/<str:play_prefix>/', nvs_views.api_search),
    path('api/corpus/<str:corpus_id>/nvs-lines/<str:play_prefix>/', nvs_views.api_lines),
    path('api/corpus/<str:corpus_id>/nvs-lines/<str:play_prefix>/<str:starting_line_id>/', nvs_views.api_lines),
    path('api/corpus/<str:corpus_id>/nvs-lines/<str:play_prefix>/<str:starting_line_id>/<str:ending_line_id>/', nvs_views.api_lines),
]
