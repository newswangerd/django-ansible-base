import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand

from ansible_base.oauth2_provider.models import OAuth2AccessToken, OAuth2RefreshToken


class Command(BaseCommand):
    def init_logging(self):
        log_levels = dict(enumerate([logging.ERROR, logging.INFO, logging.DEBUG, 0]))
        self.logger = logging.getLogger('ansible_base.oauth2_provider.commands.cleanup_tokens')
        self.logger.setLevel(log_levels.get(self.verbosity, 0))
        handler = logging.StreamHandler(stream=self.stream)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def execute(self, *args, **options):
        self.verbosity = int(options.get('verbosity', 1))
        self.stream = options.get('stderr')
        self.init_logging()
        total_accesstokens = OAuth2AccessToken.objects.all().count()
        total_refreshtokens = OAuth2RefreshToken.objects.all().count()
        call_command("cleartokens")
        self.logger.info("Expired OAuth 2 Access Tokens deleted: {}".format(total_accesstokens - OAuth2AccessToken.objects.all().count()))
        self.logger.info("Expired OAuth 2 Refresh Tokens deleted: {}".format(total_refreshtokens - OAuth2RefreshToken.objects.all().count()))
