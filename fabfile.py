"""
Support for wwww service installation and management.
"""

from fabric.api import run, settings, env, put, abort, sudo
from fabric.contrib import files

from os import path
from twisted.python.util import sibpath

from braid import authbind, git, cron, archive
from braid.twisted import service
from braid.debian import equivs
from braid.tasks import addTasks
from braid.utils import confirm

from braid import config
__all__ = ['config']


class TwistedWeb(service.Service):
    def task_install(self):
        """
        Install t-web, a Twisted Web based server.
        """
        # Bootstrap a new service environment
        self.bootstrap()

        # Add to www-data group. Mailman depends on this.
        sudo('/usr/sbin/usermod -a -g www-data -G t-web {}'.format(self.serviceUser))

        # Setup authbind
        authbind.allow(self.serviceUser, 80)
        authbind.allow(self.serviceUser, 443)
        
        # Install httpd equiv, so apt doesn't try to install apache ever
        equivs.installEquiv(self.serviceName, 'httpd')

        with settings(user=self.serviceUser):
            run('/bin/ln -nsf {}/start {}/start'.format(self.configDir, self.binDir))
            run('/bin/ln -nsf {}/start-maintenance {}/start-maintenance'.format(self.configDir, self.binDir))
            self.update()
            cron.install(self.serviceUser, '{}/crontab'.format(self.configDir))

            run('/bin/mkdir -p ~/data')
            if env.get('installPrivateData'): 
                self.task_installSSLKeys() 
                run('/usr/bin/touch {}/production'.format(self.configDir))
            else:
                run('/bin/rm -f {}/production'.format(self.configDir))


    def task_installSSLKeys(self, key=sibpath(__file__, 'twistedmatrix.com.key'), cert=sibpath(__file__, 'twistedmatrix.com.crt')):
        """
        Install SSL keys.

        @param key: Local path to key
        @param cert: Local path to cert
        """

        with settings(user=self.serviceUser):
            run('mkdir -p ~/ssl')
            if path.exists(key):
                put(key, '~/ssl/twistedmatrix.com.key', mode=0600)
            elif not files.exists('~/ssl/twistedmatrix.com.key'):
                abort('Missing SSL key.')
            if path.exists(cert):
                put(cert, '~/ssl/twistedmatrix.com.crt')
            elif not files.exists('~/ssl/twistedmatrix.com.crt'):
                abort('Missing SSL certificate.')


    def update(self):
        """
        Update config.
        """
        with settings(user=self.serviceUser):
            git.branch('https://github.com/twisted-infra/t-web', self.configDir)

    def task_update(self):
        """
        Update config and restart.
        """
        self.update()
        self.task_restart()


    def task_dump(self, dump):
        """
        Dump non-versioned resources.
        """
        with settings(user=self.serviceUser):
            archive.dump({
                'data': 'data',
                }, dump)


    def task_restore(self, dump):
        """
        Resotre non-versioned resources.
        """
        msg = 'All non-versioned web resources will be replaced with the backup.'
        if confirm(msg):
            with settings(user=self.serviceUser):
                archive.restore({
                    'data': 'data',
                    }, dump)

    def task_startMaintenanceSite(self):
        """
        Start maintenance site.
        """
        with settings(user=self.serviceUser):
            run('{}/start-maintenance'.format(self.binDir))



addTasks(globals(), TwistedWeb('t-web').getTasks())
