from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps

class Command(BaseCommand):
    help = 'Create missing database tables'

    def handle(self, *args, **options):
        # Get the models that need tables
        Client = apps.get_model('main', 'Client')
        MeterReading = apps.get_model('main', 'MeterReading')
        WaterBill = apps.get_model('main', 'WaterBill')
        BillingRate = apps.get_model('main', 'BillingRate')
        Metric = apps.get_model('main', 'Metric')
        
        # Check which tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
        self.stdout.write(f'Existing tables: {existing_tables}')
        
        # Try to create tables that don't exist
        models_to_check = [Client, MeterReading, WaterBill, BillingRate, Metric]
        table_names = ['main_client', 'main_meterreading', 'main_waterbill', 'main_billingrate', 'main_metric']
        
        for model, table_name in zip(models_to_check, table_names):
            if table_name not in existing_tables:
                try:
                    # Create the table using Django's schema editor
                    with connection.schema_editor() as schema_editor:
                        schema_editor.create_model(model)
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully created table {table_name}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error creating table {table_name}: {e}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Table {table_name} already exists')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Database table creation attempt completed')
        )
