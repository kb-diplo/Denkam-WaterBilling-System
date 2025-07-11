from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

Account = get_user_model()

class Command(BaseCommand):
    help = 'Finds all superusers and ensures their role is set to ADMIN.'

    def handle(self, *args, **kwargs):
        superusers = Account.objects.filter(is_superuser=True)

        if not superusers.exists():
            self.stdout.write(self.style.WARNING('No superusers found. Please create one first.'))
            return

        updated_count = 0
        for user in superusers:
            if user.role != Account.Role.ADMIN:
                user.role = Account.Role.ADMIN
                user.save()
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f'Updated role for admin user: {user.email}'))

        if updated_count == 0:
            self.stdout.write(self.style.SUCCESS('All admin users already have the correct role.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} admin user(s).'))
