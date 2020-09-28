from django.urls import path
from . import views as arc_views


urlpatterns = [
    path('corpus/<str:corpus_id>/query/', arc_views.query),
]