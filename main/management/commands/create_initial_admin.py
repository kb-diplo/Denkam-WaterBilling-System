from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

Account = get_user_model()

class Command(BaseCommand):
    help = 'Creates the initial administrator user.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help="The admin user's email address.")
        parser.add_argument('password', type=str, help="The admin user's password.")

    def handle(self, *args, **kwargs):
        if Account.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('An admin user already exists. Aborting.'))
            return

        email = kwargs['email']
        password = kwargs['password']

        try:
            Account.objects.create_superuser(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Successfully created admin user: {email}'))
        except Exception as e:
            raise CommandError(f'An error occurred: {e}')
