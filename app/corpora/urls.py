"""corpora URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from manager import views as manager_views
from rest_framework_mongoengine import routers


router = routers.DefaultRouter()
router.register(r'corpus', manager_views.CorpusViewSet)
router.register('corpus/(?P<corpus_id>.+)/document', manager_views.DocumentViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', manager_views.corpora),
    path('scholar', manager_views.scholar),
    path('corpus/<str:corpus_id>/', manager_views.corpus),
    path('corpus/<str:corpus_id>/document/<str:document_id>/', manager_views.document),
    path('corpus/<str:corpus_id>/document/<str:document_id>/edit-xml/', manager_views.edit_xml),
    path('corpus/<str:corpus_id>/document/<str:document_id>/tei-skeleton', manager_views.tei_skeleton),
    path('corpus/<str:corpus_id>/document/<str:document_id>/draw-page-regions/<str:ref_no>/', manager_views.draw_page_regions),
    path('corpus/<str:corpus_id>/document/<str:document_id>/files/<str:file_basename>', manager_views.get_document_file),
    path('corpus/<str:corpus_id>/document/<str:document_id>/pages/<str:ref_no>/files/<str:file_basename>', manager_views.get_document_page_file),
    path('corpus/<str:corpus_id>/document/<str:document_id>/pages/<str:ref_no>/images/<str:image_basename>', manager_views.get_document_page_image),
    path('corpus/<str:corpus_id>/document/<str:document_id>/pages/<str:ref_no>/images/<str:image_basename>/<str:region>/<str:size>/<str:rotation>/<str:quality>.<str:format>', manager_views.get_document_page_image),
    path('api/corpora/', manager_views.api_corpora),
    path('api/corpus/<str:corpus_id>/', manager_views.api_corpus),
    path('api/search/', manager_views.api_search),
    path('api/corpus/<str:corpus_id>/search/', manager_views.api_search),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/search/', manager_views.api_search),
    path('api/corpus/<str:corpus_id>/documents/', manager_views.api_documents),
    path('api/corpus/<str:corpus_id>/jobs/', manager_views.api_corpus_jobs),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/', manager_views.api_document),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/jobs/', manager_views.api_document_jobs),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/kvp/<str:key>', manager_views.api_document_kvp),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/page-file-collections/', manager_views.api_document_page_file_collections),
    path('api/corpus/<str:corpus_id>/document/<str:document_id>/page/get-region-content/<str:ref_no>/<int:x>/<int:y>/<int:width>/<int:height>/', manager_views.api_page_region_content),
    path('api/jobsites/', manager_views.api_jobsites),
    path('api/tasks/', manager_views.api_tasks),
    path('get-image', manager_views.get_image),
    path('get-file', manager_views.get_file),
    path('drf/', include(router.urls))
]
