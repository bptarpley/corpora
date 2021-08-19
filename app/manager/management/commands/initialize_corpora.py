import time
import importlib
import traceback
from copy import deepcopy
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from neo4j import GraphDatabase
from django.conf import settings
from elasticsearch_dsl import Index, Mapping, Keyword, Text, Boolean, normalizer
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
        if not settings.NEO4J:
            # attempting to connect with default creds.
            initial_neo = GraphDatabase.driver(
                "bolt://{0}".format(os.environ['CRP_NEO4J_HOST']),
                auth=('neo4j', 'neo4j')
            )
            temp_default_pwd = 'initpwd'

            with initial_neo.session() as neo:
                # change default password (must do in order to proceed with new account creation)
                neo.run(
                    "CALL dbms.security.changePassword('{0}')".format(temp_default_pwd)
                )

            initial_neo.close()
            initial_neo = GraphDatabase.driver(
                "bolt://{0}".format(os.environ['CRP_NEO4J_HOST']),
                auth=('neo4j', temp_default_pwd)
            )

            with initial_neo.session() as neo:
                # create admin account
                neo.run(
                    "CALL dbms.security.createUser",
                    username=os.environ['CRP_NEO4J_USER'],
                    password=os.environ['CRP_NEO4J_PWD'],
                    requirePasswordChange=False
                )

                # BELOW COMMENTED OUT FOR Neo4J Community
                '''
                # grant admin account admin privs
                neo.run(
                    "CALL dbms.security.addRoleToUser",
                    roleName="admin",
                    username=os.environ['CRP_NEO4J_USER']
                )

                # create read-only user
                neo.run(
                    "CALL dbms.security.createUser",
                    username=os.environ['CRP_NEO4J_RO_USER'],
                    password=os.environ['CRP_NEO4J_RO_PWD'],
                    requirePasswordChange=False
                )

                # grant read-only account privs
                neo.run(
                    "CALL dbms.security.addRoleToUser",
                    roleName="reader",
                    username=os.environ['CRP_NEO4J_RO_USER']
                )
                '''

            initial_neo.close()

            # setup NEO4J default connection
            settings.NEO4J = GraphDatabase.driver(
                "bolt://{0}".format(os.environ['CRP_NEO4J_HOST']),
                auth=(os.environ['CRP_NEO4J_USER'], os.environ['CRP_NEO4J_PWD'])
            )

            # delete default user
            with settings.NEO4J.session() as neo:
                neo.run(
                    "CALL dbms.security.deleteUser",
                    username="neo4j"
                )

            print("\t-- NEO4J USERS INITIALIZED :)")
        else:
            print("\t-- NEO4J USERS INITIALIZED :)")

        with settings.NEO4J.session() as neo:
            constraints = ' '.join([r.get("description") for r in neo.run("CALL db.constraints")])
            constraint_created = False

            if ":Scholar" not in constraints:
                neo.run("CREATE CONSTRAINT ON(s:Scholar) ASSERT s.uri IS UNIQUE")
                constraint_created = True
            if ":Corpus" not in constraints:
                neo.run("CREATE CONSTRAINT ON(c:Corpus) ASSERT c.uri IS UNIQUE")
                constraint_created = True
            if ":_File" not in constraints:
                neo.run("CREATE CONSTRAINT ON(f:_File) ASSERT f.uri IS UNIQUE")
                neo.run("CREATE INDEX ON :_File(corpus_id)")
                constraint_created = True
            if ":_JobSite" not in constraints:
                neo.run("CREATE CONSTRAINT ON(js:_JobSite) ASSERT js.uri IS UNIQUE")
                constraint_created = True
            if ":_Task" not in constraints:
                neo.run("CREATE CONSTRAINT ON(t:_Task) ASSERT t.uri IS UNIQUE")
                constraint_created = True
            if ":_Job" not in constraints:
                neo.run("CREATE CONSTRAINT ON(j:_Job) ASSERT j.uri IS UNIQUE")
                constraint_created = True
            if ":_Process" not in constraints:
                neo.run("CREATE CONSTRAINT ON(p:_Process) ASSERT p.uri IS UNIQUE")
                constraint_created = True

            if constraint_created:
                print("\t-- NEO4J CONSTRAINTS CREATED :)")
            else:
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

        print("\n---------------------------")
        print(" CORPORA INITIALIZED")
        print("---------------------------\n")
        return True
