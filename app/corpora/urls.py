import os
import importlib
import django_eventstream
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from manager import views as manager_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', manager_views.corpora),
    path('scholar', manager_views.scholar),
    path('scholars', manager_views.scholars),
    path('backups', manager_views.backups),
    path('backups/download/<str:backup_id>/', manager_views.download_backup),
    path('export/<str:corpus_id>/<str:content_type>/', manager_views.export),
    path('corpus/<str:corpus_id>/', manager_views.corpus),
    path('corpus/<str:corpus_id>/get-file/', manager_views.get_corpus_file),
    path('corpus/<str:corpus_id>/event-dispatcher/', manager_views.get_corpus_event_dispatcher),
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

    re_path(r'^fp/', include('django_drf_filepond.urls')),
    path('file/uri/<str:file_uri>/', manager_views.get_file),
    path('repo-file/<str:corpus_id>/<str:repo_name>/', manager_views.get_repo_file),
    path('image/uri/<str:image_uri>/', manager_views.get_image),
    path('image/uri/<str:image_uri>/info.json', manager_views.get_image),
    path('image/uri/<str:image_uri>/<str:region>/<str:size>/<str:rotation>/<str:quality>.<str:format>', manager_views.get_image),
    path('iiif/2/<path:req_path>', manager_views.iiif_passthrough),
    path('render/<str:field_type>/<str:mode>/<str:language>/<str:field_name>/<int:suffix>/', manager_views.render_field_component),

    path('jobs/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/<str:content_type>/', manager_views.job_widget),
    path('jobs/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.job_widget),

    path('api/jobsites/', manager_views.api_jobsites),
    path('api/tasks/', manager_views.api_tasks),
    path('api/tasks/<str:content_type>/', manager_views.api_tasks),
    path('api/jobs/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/submit/', manager_views.api_submit_jobs),
    path('api/jobs/corpus/<str:corpus_id>/job/<str:job_id>/', manager_views.api_job),
    path('api/jobs/corpus/<str:corpus_id>/<str:content_type>/', manager_views.api_jobs),
    path('api/jobs/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.api_jobs),

    path('api/scholar/', manager_views.api_scholar),
    path('api/scholar/<str:scholar_id>/', manager_views.api_scholar),
    path('api/plugin-schema/', manager_views.api_plugin_schema),

    path('api/corpus/', manager_views.api_corpora),
    path('api/corpus/<str:corpus_id>/', manager_views.api_corpus),
    path('api/corpus/<str:corpus_id>/files/', manager_views.api_content_files),
    path('api/corpus/<str:corpus_id>/content-view/', manager_views.api_content_view),
    path('api/corpus/<str:corpus_id>/content-view/<str:content_view_id>/', manager_views.api_content_view),

    path('api/corpus/<str:corpus_id>/<str:content_type>/', manager_views.api_content),
    path('api/corpus/<str:corpus_id>/<str:content_type>/files/', manager_views.api_content_files),
    path('api/corpus/<str:corpus_id>/<str:content_type>/suggest/', manager_views.api_suggest),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/', manager_views.api_content),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/files/', manager_views.api_content_files),
    path('api/corpus/<str:corpus_id>/<str:content_type>/<str:content_id>/network-json/', manager_views.api_network_json),
    path('api/scholar/preference/<str:content_type>/<str:preference>/', manager_views.api_scholar_preference),
    path('api/publish/<str:corpus_id>/<str:event_type>/', manager_views.api_publish),

    path('events/<channel>/', include(django_eventstream.urls), {}),
]
