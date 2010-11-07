from django.conf import settings

def setdefaultattr(obj, attr, default):
    if hasattr(obj, attr):
        return getattr(obj, attr)
    else:
        setattr(obj, attr, default)
        return default

# The directory in which the static files are collected in
ROOT = setdefaultattr(settings, 'STATICFILES_ROOT', '')

# The URL path to STATIC_ROOT
URL = setdefaultattr(settings, 'STATICFILES_URL', '/static')

# A tuple of two-tuples with a name and the path of additional directories
# which hold static files and should be taken into account
DIRS = setdefaultattr(settings, 'STATICFILES_DIRS', ())

# Destination storage
STORAGE = setdefaultattr(settings, 'STATICFILES_STORAGE',
                         'staticfiles.storage.StaticFilesStorage')

# List of resolver classes that know how to find static files in
# various locations.
FINDERS = setdefaultattr(settings, 'STATICFILES_FINDERS', (
    'staticfiles.finders.FileSystemFinder',
    'staticfiles.finders.AppDirectoriesFinder',
    #'staticfiles.finders.DefaultStorageFinder',
))
