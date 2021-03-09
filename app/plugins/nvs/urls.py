from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('corpus/<str:corpus_id>/NVSLines/<int:starting_line_no>/', nvs_views.lines),
    path('corpus/<str:corpus_id>/NVSLines/<int:starting_line_no>/<int:ending_line_no>/', nvs_views.lines),
    path('corpus/<str:corpus_id>/play-viewer/<str:play_prefix>/', nvs_views.design),
    path('api/corpus/<str:corpus_id>/PlayLine/<int:starting_line_no>/<int:ending_line_no>/', nvs_views.api_lines),
    path('corpus/<str:corpus_id>/commentary-viewer/<str:play_prefix>/', nvs_views.commentaries),
    path('corpus/<str:corpus_id>/play-minimap/<str:play_prefix>/', nvs_views.play_minimap),
    path('corpus/<str:corpus_id>/paratext-viewer/<str:paratext_id>/', nvs_views.paratext),
    path('nvs/witness-meter/<str:witness_flags>/<str:height>/<str:width>/<str:inactive_color_hex>/', nvs_views.witness_meter),
    path('api/corpus/<str:corpus_id>/nvs-search/<str:play_prefix>/', nvs_views.api_search)
]
