import os
import shutil
import git
import mongoengine
from datetime import datetime


class GitRepo(mongoengine.EmbeddedDocument):

    name = mongoengine.StringField()
    path = mongoengine.StringField()
    remote_url = mongoengine.StringField()
    remote_branch = mongoengine.StringField()
    last_pull = mongoengine.DateTimeField()
    error = mongoengine.BooleanField(default=False)

    def pull(self, parent, username=None, password=None):
        if self.path and self.remote_url and self.remote_branch:
            repo = None

            # need to clone
            if not os.path.exists(self.path):
                os.makedirs(self.path)
                os.system(f"git config --global --add safe.directory {self.path}")
                repo = git.Repo.init(self.path)

                url = self.remote_url
                if username and password and 'https://' in url:
                    url = url.replace('https://', f'https://{username}:{password}@')

                origin = repo.create_remote('origin', url)
                assert origin.exists()
                assert origin == repo.remotes.origin == repo.remotes['origin']
                origin.fetch()
                repo.create_head(self.remote_branch, origin.refs[self.remote_branch])
                repo.heads[self.remote_branch].set_tracking_branch(origin.refs[self.remote_branch])
                repo.heads[self.remote_branch].checkout()

            elif self.last_pull:
                repo = git.Repo(self.path)
                assert not repo.bare
                assert repo.remotes.origin.exists()
                repo.remotes.origin.fetch()

            if repo:
                repo.remotes.origin.pull()
                self.last_pull = datetime.now()
                self.error = False
                parent.save()

    def clear(self):
        if self.path and os.path.exists(self.path):
            shutil.rmtree(self.path)

    @classmethod
    def from_dict(cls, repo_dict):
        repo = GitRepo()
        valid = True
        for attr in ['name', 'path', 'remote_url', 'remote_branch', 'last_pull', 'error']:
            if attr in repo_dict:
                if attr == 'last_pull':
                    repo.last_pull = datetime.fromtimestamp(repo_dict['last_pull'])
                else:
                    setattr(repo, attr, repo_dict[attr])
            else:
                valid = False

        if valid:
            return repo

        return None

    def to_dict(self):
        return {
            'name': self.name,
            'path': self.path,
            'remote_url': self.remote_url,
            'remote_branch': self.remote_branch,
            'last_pull': int(datetime.combine(self.last_pull, datetime.min.time()).timestamp()) if self.last_pull else None,
            'error': self.error
        }