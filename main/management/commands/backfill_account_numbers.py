from django.core.management.base import BaseCommand
from django.db import transaction
from main.models import Client

class Command(BaseCommand):
    help = 'Assigns a unique account number to existing clients who do not have one.'

    @transaction.atomic
    def handle(self, *args, **options):
        clients_to_update = Client.objects.filter(account_number__isnull=True)
        if not clients_to_update.exists():
            self.stdout.write(self.style.SUCCESS('All clients already have an account number. No action needed.'))
            return

        self.stdout.write(f'Found {clients_to_update.count()} clients without an account number. Updating now...')

        updated_count = 0
        for client in clients_to_update:
            # Generate the account number using the client's primary key
            client.account_number = f'DWB-{client.id:05d}'
            client.save()
            updated_count += 1
            self.stdout.write(f'  - Updated client ID {client.id} with account number {client.account_number}')

        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} clients.'))
