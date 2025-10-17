from django.urls import path
from . import views as document_views


urlpatterns = [
    path('corpus/<str:corpus_id>/Document/<str:document_id>/', document_views.document),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/tei-skeleton', document_views.tei_skeleton),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/transcribe/<str:project_id>/', document_views.transcribe),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/transcribe/<str:project_id>/<str:ref_no>/', document_views.transcribe),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/draw-page-regions/<str:ref_no>/', document_views.draw_page_regions),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/iiif-manifest.json', document_views.get_document_iiif_manifest),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/page-file-collection/<str:collection>/iiif-manifest.json', document_views.get_document_iiif_manifest),
    path('corpus/<str:corpus_id>/Document/<str:document_id>/page-file-collection/<str:collection>/page-set/<str:pageset>/iiif-manifest.json', document_views.get_document_iiif_manifest),
    path('api/corpus/<str:corpus_id>/Document/<str:document_id>/page-file-collections/', document_views.api_document_page_file_collections),
    path('api/corpus/<str:corpus_id>/Document/<str:document_id>/page-file-collection/<str:pfc_slug>', document_views.api_document_page_file_collections),
    path('api/corpus/<str:corpus_id>/Document/<str:document_id>/page/get-region-content/<str:ref_no>/<int:x>/<int:y>/<int:width>/<int:height>/', document_views.api_page_region_content),
]