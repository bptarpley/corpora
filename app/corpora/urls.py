import os
import importlib
from django.contrib import admin
from django.urls import path
from django.conf import settings
from manager import views as manager_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', manager_views.corpora),
    path('scholar', manager_views.scholar),
    path('scholars', manager_views.scholars),
    path('corpus/<str:corpus_id>/', manager_views.corpus),
    path('corpus/<str:corpus_id>/get-file/', manager_views.get_corpus_file),
    path('corpus/<str:corpus_id>/<str:content_type>/explore/', manager_views.explore_content),
    path('corpus/<str:corpus_id>/<str:content_type>/merge/', manager_views.merge_content),
    path('corpus/<str:corpus_id>/<str:content_type>/bulk-job-manager/', manager_views.bulk_job_manager),
]

plugins = [app for app in settings.INSTALLED_APPS if app.startswith('plugins.')]
for plugin in plugins:
    if os.path.exists("{0}/plugins/{1}/urls.py".format(settings.BASE_DIR, plugin.split('.')[1])):
        url_module = importlib.import_module(plugin + '.urls')
        if hasattr(url_module, 'urlpatterns'):
            urlpatterns += url_module.urlpatterns

urlpatterns += [
    path('corpus/<str:corpus_id>/<str:content_type>/', manager_views.edit_content),
    path('corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.view_content),
    path('corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/edit/', manager_views.edit_content),
    path('corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/<str:content_field>/iiif-image/', manager_views.iiif_widget),

    path('file/uri/<str:file_uri>/', manager_views.get_file),
    path('repo-file/<str:corpus_id>/<str:repo_name>/', manager_views.get_repo_file),
    path('image/uri/<str:image_uri>/', manager_views.get_image),
    path('image/uri/<str:image_uri>/<str:region>/<str:size>/<str:rotation>/<str:quality>.<str:format>', manager_views.get_image),

    path('jobs/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/<str:content_type>/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.job_widget),

    path('api/jobsites/', manager_views.api_jobsites),
    path('api/tasks/', manager_views.api_tasks),
    path('api/tasks/<str:content_type>/', manager_views.api_tasks),
    path('api/jobs/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/<str:content_type>/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.api_jobs),

    path('api/scholar/', manager_views.api_scholar),
    path('api/scholar/<str:scholar_id>/', manager_views.api_scholar),

    path('api/corpus/', manager_views.api_corpora),
    path('api/corpus/<str:corpus_id>/', manager_views.api_corpus),
    path('api/corpus/<str:corpus_id>/jobs/', manager_views.api_corpus_jobs),
    path('api/corpus/<str:corpus_id>/files/', manager_views.api_content_files),

    path('api/corpus/<str:corpus_id>/<str:content_type>/', manager_views.api_content),
    path('api/corpus/<str:corpus_id>/<str:content_type>/files/', manager_views.api_content_files),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.api_content),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/files/', manager_views.api_content_files),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/jobs/', manager_views.api_content_jobs),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/network-json/', manager_views.api_network_json),
    path('api/scholar/preference/<str:content_type>/<str:preference>/', manager_views.api_scholar_preference)
]
