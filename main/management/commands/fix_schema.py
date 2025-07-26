from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix database schema issues by adding missing columns'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Add updated_at column to main_client table if it doesn't exist
            try:
                cursor.execute("""
                    ALTER TABLE main_client 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE
                """)
                self.stdout.write(
                    self.style.SUCCESS('Successfully added updated_at column to main_client table')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error adding updated_at column to main_client: {e}')
                )
            
            # Add updated_at column to main_metric table if it doesn't exist
            try:
                cursor.execute("""
                    ALTER TABLE main_metric 
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE
                """)
                self.stdout.write(
                    self.style.SUCCESS('Successfully added updated_at column to main_metric table')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error adding updated_at column to main_metric: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Database schema fix attempt completed')
        )
