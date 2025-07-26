from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Inspect database schema for main app tables'

    def handle(self, *args, **options):
        tables = ['main_client', 'main_meterreading', 'main_waterbill', 'main_billingrate', 'main_metric']
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' AND table_schema = 'public'
                        ORDER BY ordinal_position
                    """)
                    columns = cursor.fetchall()
                    
                    self.stdout.write(f'\nTable: {table}')
                    self.stdout.write('-' * 40)
                    for column in columns:
                        self.stdout.write(f'{column[0]}: {column[1]}')
                except Exception as e:
                    self.stdout.write(f'Error inspecting {table}: {e}')
