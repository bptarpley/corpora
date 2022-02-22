from django.urls import path
from . import views as arc_views


urlpatterns = [
    path('api/arc/<str:corpus_id>/query/', arc_views.query),
    path('corpus/<str:corpus_id>/bigdiva/', arc_views.bigdiva),
    path('corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/UriAscription/', arc_views.uri_ascription),
    path('corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/LINCS/', arc_views.lincs_ttl)
]