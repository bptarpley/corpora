from django.urls import path
from . import views as nvs_views


urlpatterns = [
    path('corpus/<str:corpus_id>/NVSLines/<int:starting_line_no>/', nvs_views.lines),
    path('corpus/<str:corpus_id>/NVSLines/<int:starting_line_no>/<int:ending_line_no>/', nvs_views.lines),
    path('corpus/<str:corpus_id>/nvs-design/<int:starting_line_no>/<int:ending_line_no>/', nvs_views.design),
    path('api/corpus/<str:corpus_id>/PlayLine/<int:starting_line_no>/<int:ending_line_no>/', nvs_views.api_lines),
    path('corpus/<str:corpus_id>/NVSCommentaries/', nvs_views.commentaries),
    path('corpus/<str:corpus_id>/play-minimap/', nvs_views.play_minimap)
]
