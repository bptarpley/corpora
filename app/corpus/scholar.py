import secrets
import traceback

import mongoengine
from typing import TYPE_CHECKING
from elasticsearch_dsl import Search
from elasticsearch_dsl.connections import get_connection
from django.contrib.auth.models import User
from .utilities import run_neo
from .job import Task, JobSite, JobTracker


# to avoid circular dependency between Scholar and Corpus classes:
if TYPE_CHECKING:
    from .corpus import Corpus
    from .content import ContentView


class Scholar(mongoengine.Document):
    username = mongoengine.StringField(unique=True)
    fname = mongoengine.StringField()
    lname = mongoengine.StringField()
    email = mongoengine.EmailField()
    available_corpora = mongoengine.DictField()  # corpus_id: Viewer|Editor
    available_tasks = mongoengine.ListField(mongoengine.LazyReferenceField(Task, reverse_delete_rule=mongoengine.PULL))
    available_jobsites = mongoengine.ListField(
        mongoengine.LazyReferenceField(JobSite, reverse_delete_rule=mongoengine.PULL))
    is_admin = mongoengine.BooleanField(default=False)
    auth_token = mongoengine.StringField(default=secrets.token_urlsafe(32))
    auth_token_ips = mongoengine.ListField(mongoengine.StringField())

    def save(self, index_pages=False, **kwargs):
        super().save(**kwargs)
        permissions = ""

        # Create/update scholar node
        run_neo('''
                MERGE (s:_Scholar { uri: $scholar_uri })
                SET s.username = $scholar_username
                SET s.name = $scholar_name
                SET s.email = $scholar_email
                SET s.is_admin = $scholar_is_admin
            ''',
                {
                    'scholar_uri': "/scholar/{0}".format(self.id),
                    'scholar_username': self.username,
                    'scholar_name': "{0} {1}".format(self.fname, self.lname),
                    'scholar_email': self.email,
                    'scholar_is_admin': self.is_admin
                }
                )

        # Wire up permissions (not relevant if user is admin)
        for corpus_id, role in self.available_corpora.items():
            permissions += "{0}:{1},".format(corpus_id, role)

        # Add this scholar to Scholar Elasticsearch index
        if permissions:
            permissions = permissions[:-1]

        get_connection().index(
            index='scholar',
            id=str(self.id),
            body={
                'username': self.username,
                'fname': self.fname,
                'lname': self.lname,
                'email': self.email,
                'is_admin': self.is_admin,
                'available_corpora': permissions
            }
        )

    def get_preference(self, content_type, content_uri, preference):
        results = run_neo(
            '''
                MATCH (s:_Scholar {{ uri: $scholar_uri }}) -[prefs:hasPreferences]-> (c:{content_type} {{ uri: $content_uri }})
                RETURN prefs.{preference} as preference
            '''.format(content_type=content_type, preference=preference),
            {
                'scholar_uri': "/scholar/{0}".format(self.id),
                'content_uri': content_uri
            }
        )

        if results and 'preference' in results[0].keys():
            return results[0]['preference']
        return None

    def set_preference(self, content_type, content_uri, preference, value):
        run_neo(
            '''
                MATCH (s:_Scholar {{ uri: $scholar_uri }})
                MATCH (c:{content_type} {{ uri: $content_uri }})
                MERGE (s) -[prefs:hasPreferences]-> (c) 
                SET prefs.{preference} = $value
            '''.format(content_type=content_type, preference=preference),
            {
                'scholar_uri': "/scholar/{0}".format(self.id),
                'content_uri': content_uri,
                'value': value
            }
        )

    def to_dict(self):
        from .corpus import Corpus # importing in method to avoid circular dependency between Scholar and Corpus

        scholar_dict = {
            'username': self.username,
            'fname': self.fname,
            'lname': self.lname,
            'email': self.email,
            'is_admin': self.is_admin,
            'available_corpora': {},

        }
        if self.is_admin:
            for corpus in Corpus.objects:
                scholar_dict['available_corpora'][str(corpus.id)] = {
                    'name': corpus.name,
                    'role': 'Admin'
                }

            scholar_dict['available_jobsites'] = [str(js.id) for js in JobSite.objects]
            scholar_dict['available_tasks'] = [str(task.id) for task in Task.objects]

        else:
            if self.available_corpora:
                corpora = Corpus.objects(id__in=list(self.available_corpora.keys())).only('id', 'name')
                for corpus in corpora:
                    scholar_dict['available_corpora'][str(corpus.id)] = {
                        'name': corpus.name,
                        'role': self.available_corpora[str(corpus.id)]
                    }

            scholar_dict['available_jobsites'] = [str(js.id) for js in self.available_jobsites]
            scholar_dict['available_tasks'] = [str(task.id) for task in self.available_tasks]

        return scholar_dict

    @classmethod
    def _post_delete(cls, sender, document, **kwargs):
        # ---------------------------------------------------- #
        # Handle any content that might reference this scholar #
        # ---------------------------------------------------- #
        from .content import ContentView # importing here to prevent circular dependencies
        corpora_scholar = None
        def get_corpora_scholar(corpora_scholar):
            if corpora_scholar:
                return corpora_scholar
            else:
                corpora_scholar = Scholar.objects.filter(username='corpora')
                if corpora_scholar.count():
                    return corpora_scholar[0]
            return None

        # JobTrackers
        jobs = JobTracker.objects.filter(scholar=document.id)
        if jobs.count():
            # Reassign to Corpora scholar
            corpora_scholar = get_corpora_scholar(corpora_scholar)
            if corpora_scholar:
                for job in jobs:
                    job.scholar = corpora_scholar.id
                    job.save()

        # ContentViews
        content_views = ContentView.objects.filter(created_by=document.id)
        if content_views.count():
            corpora_scholar = get_corpora_scholar(corpora_scholar)
            if corpora_scholar:
                for content_view in content_views:
                    content_view.created_by = corpora_scholar.id

        # ------------------------------------ #
        # Remove from Neo4J graph and ES index #
        # ------------------------------------ #

        # Delete Neo4J nodes
        run_neo('''
                MATCH (s:_Scholar { uri: $scholar_uri })
                DETACH DELETE s
            ''',
                {
                    'scholar_uri': "/scholar/{0}".format(document.id),
                }
                )

        # Remove scholar from ES index
        es_scholar = Search(index='scholar').query("match", _id=str(document.id))
        es_scholar.delete()

        # ---------------------------------------------- #
        # Delete corresponding user from Django Admin DB #
        # ---------------------------------------------- #
        try:
            user_to_delete = User.objects.get(username=document.username)
            if user_to_delete:
                user_to_delete.delete()
        except:
            print(f'Unable to delete user {document.username} from Django Admin DB:')
            print(traceback.format_exc())


# rig up post delete signal for Scholar
mongoengine.signals.post_delete.connect(Scholar._post_delete, sender=Scholar)
