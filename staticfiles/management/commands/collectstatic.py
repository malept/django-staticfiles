import os
import sys
import shutil
from optparse import make_option

from django.core.files.storage import get_storage_class
from django.core.management.base import CommandError, NoArgsCommand

from ... import finders, settings

class Command(NoArgsCommand):
    """
    Command that allows to copy or symlink media files from different
    locations to the settings.STATICFILES_ROOT.
    """
    option_list = NoArgsCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive',
            default=True, help="Do NOT prompt the user for input of any "
                "kind."),
        make_option('-i', '--ignore', action='append', default=[],
            dest='ignore_patterns', metavar='PATTERN',
            help="Ignore files or directories matching this glob-style "
                "pattern. Use multiple times to ignore more."),
        make_option('-n', '--dry-run', action='store_true', dest='dry_run',
            default=False, help="Do everything except modify the filesystem."),
        make_option('-l', '--link', action='store_true', dest='link',
            default=False, help="Create a symbolic link to each file instead of copying."),
        make_option('--no-default-ignore', action='store_false',
            dest='use_default_ignore_patterns', default=True,
            help="Don't ignore the common private glob-style patterns 'CVS', "
                "'.*' and '*~'."),
    )
    help = "Collect static files from apps and other locations in a single location."

    STATUS_COPY = 0
    STATUS_SKIP = 1

    REASON_ALREADY_COPIED = 1
    REASON_ALREADY_LINKED = 3
    REASON_NOT_MODIFIED = 2

    REASONS = {
        REASON_ALREADY_COPIED: 'already copied earlier',
        REASON_ALREADY_LINKED: 'already linked earlier',
        REASON_NOT_MODIFIED: 'not modified',
    }

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.destination_storage = get_storage_class(settings.STORAGE)()

        try:
            self.destination_storage.path('')
        except NotImplementedError:
            self.destination_local = False
        else:
            self.destination_local = True

    def handle_noargs(self, **options):
        symlink = options['link']
        ignore_patterns = options['ignore_patterns']
        if options['use_default_ignore_patterns']:
            ignore_patterns += ['CVS', '.*', '*~']
        ignore_patterns = list(set(ignore_patterns))
        self.copied_files = set()
        self.symlinked_files = set()
        self.unmodified_files = set()
        self._verbosity = int(options.get('verbosity', 1))
        self._dry_run = options['dry_run']

        if symlink:
            if sys.platform == 'win32':
                raise CommandError("Symlinking is not supported by this "
                                   "platform (%s)." % sys.platform)
            if not self.destination_local:
                raise CommandError("Can't symlink to a remote destination.")

        # Warn before doing anything more.
        if options.get('interactive'):
            confirm = raw_input("""
You have requested to collate static files and collect them at the destination
location as specified in your settings file.

This will overwrite existing files.
Are you sure you want to do this?

Type 'yes' to continue, or 'no' to cancel: """)
            if confirm != 'yes':
                raise CommandError("Static files build cancelled.")

        for finder in finders.get_finders():
            for source, prefix, storage in finder.list(ignore_patterns):
                self.copy_file(source, prefix, storage, **options)

        actual_count = len(self.copied_files) + len(self.symlinked_files)
        unmodified_count = len(self.unmodified_files)
        if self._verbosity >= 1:
            self.stdout.write("\n%s static file%s %s to '%s'%s.\n"
                              % (actual_count, actual_count != 1 and 's' or '',
                                 symlink and 'symlinked' or 'copied',
                                 settings.ROOT,
                                 unmodified_count and ' (%s unmodified)'
                                 % unmodified_count or ''))

    def copy_file(self, source, prefix, source_storage, **options):
        """
        Attempt to copy (or symlink) ``source`` to ``destination``,
        returning True if successful.
        """
        source_path = source_storage.path(source)
        if prefix:
            destination = '/'.join([prefix, source])
        else:
            destination = source
        self._symlink = options['link']

        status, detail = self.file_status(source_storage, source, destination)

        if status == self.STATUS_SKIP:
            if self._verbosity >= 2:
                self.stdout.write('Skipping "%s" (%s)\n' % \
                                  (destination, self.REASONS[detail]))
            if detail == self.REASON_NOT_MODIFIED:
                self.unmodified_files.add(destination)
            return False

        if self._dry_run:
            if self._verbosity >= 2:
                self.stdout.write("Pretending to delete '%s'\n"
                                  % destination)
        else:
            if self._verbosity >= 2:
                self.stdout.write("Deleting '%s'\n" % destination)
            self.destination_storage.delete(destination)

        if self._symlink:
            destination_path = self.destination_storage.path(destination)
            if self._dry_run:
                if self._verbosity >= 1:
                    self.stdout.write("Pretending to symlink '%s' to '%s'\n"
                                      % (source_path, destination_path))
            else:
                if self._verbosity >= 1:
                    self.stdout.write("Symlinking '%s' to '%s'\n"
                                      % (source_path, destination_path))
                try:
                    os.makedirs(os.path.dirname(destination_path))
                except OSError:
                    pass
                os.symlink(source_path, destination_path)
            self.symlinked_files.add(destination)
        else:
            if self._dry_run:
                if self._verbosity >= 1:
                    self.stdout.write("Pretending to copy '%s' to '%s'\n"
                                      % (source_path, destination))
            else:
                if self.destination_local:
                    destination_path = self.destination_storage.path(destination)
                    try:
                        os.makedirs(os.path.dirname(destination_path))
                    except OSError:
                        pass
                    shutil.copy2(source_path, destination_path)
                    if self._verbosity >= 1:
                        self.stdout.write("Copying '%s' to '%s'\n"
                                          % (source_path, destination_path))
                else:
                    source_file = source_storage.open(source)
                    self.destination_storage.save(destination, source_file)
                    if self._verbosity >= 1:
                        self.stdout.write("Copying %s to %s\n"
                                          % (source_path, destination))
            self.copied_files.add(destination)
        return True

    def file_status(self, source_storage, source, destination):
        '''Determines the status of the file (one of ``STATUS_COPY`` or
        ``STATUS_SKIP``), with an optional detail (e.g., the reason for
        skipping).
        '''
        if destination in self.copied_files:
            return self.STATUS_SKIP, self.REASON_ALREADY_COPIED
        elif destination in self.symlinked_files:
            return self.STATUS_SKIP, self.REASON_ALREADY_LINKED
        elif self.destination_storage.exists(destination):
            if self.file_has_changed(source_storage, source, destination):
                destination_is_link = os.path.islink(
                    self.destination_storage.path(destination))
                if (not self._symlink and not destination_is_link):
                    return self.STATUS_SKIP, self.REASON_NOT_MODIFIED
        return self.STATUS_COPY, None

    def file_has_changed(self, source_storage, source, destination):
        try:
            source_last_modified = source_storage.modified_time(source)
        except (OSError, NotImplementedError, AttributeError):
            source_last_modified = 0
        try:
            destination_last_modified = \
                self.destination_storage.modified_time(destination)
        except (OSError, NotImplementedError, AttributeError):
            # storage doesn't support ``modified_time`` or failed, assume True
            return True
        else:
            return source_last_modified > destination_last_modified
