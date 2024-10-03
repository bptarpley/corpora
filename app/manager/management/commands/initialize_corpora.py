import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from elasticsearch_dsl import Boolean, normalizer
from corpus import *

initialized_file = '/corpora/initialized'


class Command(BaseCommand):
    def handle(self, *args, **options):
        initialized = False
        initialization_attempts = 0

        while not initialized and initialization_attempts < 2:
            try:
                initialized = self._initialize()
            except:
                initialization_attempts += 1
                print("\t-- ERROR INITIALIZING CORPORA:")
                print(traceback.format_exc())
                if initialization_attempts < 2:
                    print("\t-- TRYING AGAIN IN 10 SECONDS...")
                    time.sleep(10)
                else:
                    print("\t-- UNABLE TO INITIALIZE CORPORA:\n")
                    print(traceback.format_exc())

        settings.NEO4J.close()

    def _initialize(self):
        print("---------------------------")
        print(" INITIALIZING CORPORA")
        print("---------------------------\n")

        # Ensure NEO4J users/passwords set and constraints exist
        with settings.NEO4J.session() as neo:
            neo.run("CREATE CONSTRAINT s_Scholar IF NOT EXISTS FOR (s:_Scholar) REQUIRE s.uri IS UNIQUE")
            neo.run("CREATE CONSTRAINT cCorpus IF NOT EXISTS FOR (c:Corpus) REQUIRE c.uri IS UNIQUE")
            neo.run("CREATE CONSTRAINT f_File IF NOT EXISTS FOR (f:_File) REQUIRE f.uri IS UNIQUE")
            neo.run("CREATE INDEX corpus_id_File IF NOT EXISTS FOR (f:_File) ON (f.corpus_id)")
            neo.run("CREATE CONSTRAINT js_JobSite IF NOT EXISTS FOR (js:_JobSite) REQUIRE js.uri IS UNIQUE")
            neo.run("CREATE CONSTRAINT t_Task IF NOT EXISTS FOR (t:_Task) REQUIRE t.uri IS UNIQUE")
            neo.run("CREATE CONSTRAINT j_Job IF NOT EXISTS FOR (j:_Job) REQUIRE j.uri IS UNIQUE")
            neo.run("CREATE CONSTRAINT p_Process IF NOT EXISTS FOR (p:_Process) REQUIRE p.uri IS UNIQUE")

            print("\t-- NEO4J CONSTRAINTS EXIST :)")

        local_jobsite = None
        try:
            local_jobsite = JobSite.objects(type="HUEY", name="Local")[0]
            print("\t-- LOCAL JOB SITE EXISTS :)")
        except:
            local_jobsite = None

        # Ensure local jobsite exists
        if not local_jobsite:
            local_jobsite = JobSite()
            local_jobsite.name = "Local"
            local_jobsite.type = "HUEY"
            local_jobsite.job_dir = "/corpora"
            local_jobsite.max_jobs = 10
            local_jobsite.save()
            print("\t-- LOCAL JOB SITE CREATED :)")

        # Ensure Corpora Elasticsearch index exists
        if Index('corpora').exists():
            print("\t-- CORPORA INDEX EXISTS :)")
        else:
            # Create Corpora Elasticsearch index
            corpora_analyzer = analyzer(
                'corpora_analyzer',
                tokenizer='classic',
                filter=['stop', 'lowercase', 'classic']
            )

            mapping = Mapping()
            mapping.field('name', 'text', analyzer=corpora_analyzer, fields={'raw': Keyword()})
            mapping.field('description', 'text', analyzer=corpora_analyzer)
            mapping.field('open_access', Boolean())
            corpora_index = Index('corpora')
            corpora_index.mapping(mapping)
            corpora_index.save()
            print("\t-- CORPORA INDEX CREATED :)")

        # Ensure Scholar Elasticsearch index exists
        if Index('scholar').exists():
            print("\t-- SCHOLAR INDEX EXISTS :)")
        else:
            # Create Scholar Elasticsearch index
            corpora_normalizer = normalizer(
                'corpora_normalizer',
                filter=['lowercase']
            )

            mapping = Mapping()
            mapping.field('username', Keyword(normalizer=corpora_normalizer))
            mapping.field('fname', Keyword(normalizer=corpora_normalizer))
            mapping.field('lname', Keyword(normalizer=corpora_normalizer))
            mapping.field('email', Keyword(normalizer=corpora_normalizer))
            mapping.field('is_admin', Boolean())
            mapping.field('available_corpora', Keyword())
            scholar_index = Index('scholar')
            scholar_index.mapping(mapping)
            scholar_index.save()
            print("\t-- SCHOLAR INDEX CREATED :)")

        # Ensure ContentView Elasticsearch index exists
        if Index('content_view').exists():
            print("\t-- CONTENT VIEW INDEX EXISTS :)")
        else:
            # Create ContentView Elasticsearch index
            mapping = Mapping()
            mapping.field('ids', 'keyword')
            content_view_index = Index('content_view')
            content_view_index.mapping(mapping)
            content_view_index.save()
            print("\t-- CONTENT VIEW INDEX CREATED :)")

        # Ensure a user exists
        if User.objects.filter(username=settings.DEFAULT_USER_USERNAME).count() > 0 and Scholar.objects(username=settings.DEFAULT_USER_USERNAME).count() > 0:
            print("\t-- USERS EXIST :)")
        else:
            user = None

            if User.objects.filter(username=settings.DEFAULT_USER_USERNAME).count() == 0:
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

            if Scholar.objects(username=settings.DEFAULT_USER_USERNAME).count() == 0:
                if not user:
                    user = User.objects.get(username=settings.DEFAULT_USER_USERNAME)

                scholar = Scholar()
                scholar.username = settings.DEFAULT_USER_USERNAME
                scholar.fname = settings.DEFAULT_USER_FNAME
                scholar.lname = settings.DEFAULT_USER_LNAME
                scholar.email = settings.DEFAULT_USER_EMAIL
                scholar.is_admin = True

                token, created = Token.objects.get_or_create(user=user)
                scholar.auth_token = token.key
                scholar.save()

            print("\t-- DEFAULT USER CREATED :)")

        # Register new plug-in tasks (or update existing with new version)
        jobsites = JobSite.objects()
        tasks = Task.objects()
        existing_task_ids = []
        apps = [app for app in settings.INSTALLED_APPS if app.startswith('plugins.')]
        apps.append('manager')

        for app in apps:
            if app == 'manager' or os.path.exists("{0}/plugins/{1}/tasks.py".format(settings.BASE_DIR, app.split('.')[1])):
                task_module = importlib.import_module(app + '.tasks')
                if hasattr(task_module, 'REGISTRY'):
                    for name, plugin_task in task_module.REGISTRY.items():
                        old_version = None
                        found_existing_task = False
                        new_task = None

                        for existing_task in tasks:
                            if existing_task.name == name and existing_task.jobsite_type == 'HUEY':
                                found_existing_task = True
                                existing_task_ids.append(str(existing_task.id))
                                if existing_task.version != plugin_task['version']:
                                    old_version = existing_task.version
                                    existing_task.version = plugin_task['version']
                                    existing_task.content_type = plugin_task['content_type']
                                    existing_task.track_provenance = plugin_task['track_provenance']
                                    existing_task.create_report = plugin_task.get('create_report', False)
                                    existing_task.configuration = deepcopy(plugin_task['configuration'])
                                    existing_task.save()
                                break

                        if not found_existing_task:
                            new_task = Task()
                            new_task.name = name
                            new_task.jobsite_type = 'HUEY'
                            new_task.version = plugin_task['version']
                            new_task.content_type = plugin_task['content_type']
                            new_task.track_provenance = plugin_task['track_provenance']
                            new_task.create_report = plugin_task.get('create_report', False)
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
                                    print("\t-- TASK {0}: {1} REGISTERED :)".format(app, name))
                        elif old_version:
                            for jobsite in jobsites:
                                if jobsite.type == 'HUEY':
                                    jobsite.task_registry[name]['module'] = plugin_task['module']
                                    jobsite.task_registry[name]['functions'] = plugin_task['functions']
                                    jobsite.save()
                                    print("\t-- UPDATED {0}: {1} FROM VERSION {2} TO {3} :)".format(
                                        app,
                                        name,
                                        old_version,
                                        plugin_task['version']
                                    ))

        # delete stale tasks
        for task in tasks:
            if str(task.id) not in existing_task_ids:
                print(f'\nDeleting stale task {task.name}...')

                for jobsite in jobsites:
                    if task.name in jobsite.task_registry:
                        del jobsite.task_registry[task.name]
                        jobsite.save()

                task.delete()


        print("\n---------------------------")
        print(" CORPORA INITIALIZED")
        print("---------------------------\n")
        return True
