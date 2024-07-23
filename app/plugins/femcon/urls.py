from django.urls import path
from . import views as femcon_views


urlpatterns = [
    path('corpus/<str:corpus_id>/Document/<str:document_id>/booknlp-widget/', femcon_views.booknlp_widget),
    path('api/corpus/<str:corpus_id>/Document/<str:document_id>/booknlp-characters/', femcon_views.api_booknlp_characters),
]