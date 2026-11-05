from django_eventstream.channelmanager import DefaultChannelManager
from corpus import Scholar
from .utilities import scholar_can_access_corpus


class CorpusChannelManager(DefaultChannelManager):
    # Each SSE channel is named for a corpus, so a stream follows the same access rule as the corpus itself, with one
    # exception: anonymous requests are refused even for open access corpora. Browsers only open a stream once a
    # scholar is logged in, and a stream is otherwise something anyone could hold open against nginx and Daphne.
    def can_read_channel(self, user, channel):
        if not user:
            return False

        # Unlike a page view this reads the Scholar rather than the copy cached in the session, since the session
        # isn't on hand here: django_eventstream only passes along the user.
        scholar = Scholar.objects(username=user.username).first()
        return bool(scholar and scholar_can_access_corpus(channel, scholar))
