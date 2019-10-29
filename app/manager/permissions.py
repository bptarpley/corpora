from rest_framework import permissions
from corpus import *


class IsCorpusScholar(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        scholar = Scholar.objects(username=request.user.username)[0]
        print(request.user.username)
        return (obj.open_access or (scholar and scholar.is_admin) or (scholar and obj in scholar.avialable_corpora))
