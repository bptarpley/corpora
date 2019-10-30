import time
import importlib
import traceback
from copy import deepcopy
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.conf import settings
from elasticsearch_dsl import Index, Mapping, Keyword, Text, Boolean
from corpus import *

initialized_file = '/corpora/initialized'


class Command(BaseCommand):
    def handle(self, *args, **options):
        
        if not os.path.exists(initialized_file):
            print("---------------------------")
            print(" INITIALIZING CORPORA")
            print("---------------------------")

            # Create local jobsite
            local_jobsite = JobSite()
            local_jobsite.name = "Local"
            local_jobsite.type = "HUEY"
            local_jobsite.job_dir = "/corpora"
            local_jobsite.max_jobs = 10
            local_jobsite.save()
            print("Local jobsite created.")

            # Create default user
            user = User.objects.create_user(
                settings.DEFAULT_USER_USERNAME,
                settings.DEFAULT_USER_EMAIL,
                settings.DEFAULT_USER_PASSWORD
            )
            user.first_name = settings.DEFAULT_USER_FNAME
            user.last_name = settings.DEFAULT_USER_LNAME
            user.is_superuser = True
            user.save()

            scholar = Scholar()
            scholar.username = settings.DEFAULT_USER_USERNAME
            scholar.fname = settings.DEFAULT_USER_FNAME
            scholar.lname = settings.DEFAULT_USER_LNAME
            scholar.email = settings.DEFAULT_USER_EMAIL
            scholar.is_admin = True

            token, created = Token.objects.get_or_create(user=user)
            scholar.auth_token = token.key
            scholar.save()
            print("Default user created.")

            # Create Corpora Elasticsearch index
            mapping = Mapping()
            mapping.field('corpus_id', Keyword())
            mapping.field('name', Text(), fields={ 'raw': Keyword() })
            mapping.field('description', Text())
            mapping.field('open_access', Boolean())
            corpora_index = Index('/corpora')
            corpora_index.mapping(mapping)
            corpora_index.save()

            with open(initialized_file, 'w') as init_out:
                init_out.write(time.strftime("%Y-%m-%d %H:%M"))
        
        jobsites = JobSite.objects()
        tasks = Task.objects()
        apps = [app for app in settings.INSTALLED_APPS if app.startswith('plugins.')]
        apps.append('manager')

        for app in apps:
            try:
                task_module = importlib.import_module(app + '.tasks')
                for name, plugin_task in task_module.REGISTRY.items():
                    old_version_task_id = None
                    found_existing_task = False
                    new_task = None

                    for existing_task in tasks:
                        if existing_task.name == name and existing_task.jobsite_type == 'HUEY':
                            found_existing_task = True
                            if existing_task.version != plugin_task['version']:
                                old_version_task_id = existing_task.id

                    if not found_existing_task or old_version_task_id:
                        new_task = Task()
                        new_task.name = name
                        new_task.jobsite_type = 'HUEY'
                        new_task.version = plugin_task['version']
                        new_task.configuration = deepcopy(plugin_task['configuration'])
                        new_task.save()

                    if new_task:
                        for jobsite in jobsites:
                            if jobsite.type == 'HUEY':
                                jobsite.task_registry[name] = {
                                    'task_id': new_task.id,
                                    'module': plugin_task['module'],
                                    'functions': deepcopy(plugin_task['functions'])
                                }
                                jobsite.save()
                                print("Task {0}: {1} registered.".format(app, name))
                        if old_version_task_id:
                            for existing_task in tasks:
                                if str(existing_task.id) == str(old_version_task_id):
                                    existing_task.delete()
                                    print("Updated task version from {0} to {1}".format(existing_task.version, new_task.version))

            except:
                print("Error registering tasks for {0} plugin:".format(app))
                print(traceback.format_exc())
