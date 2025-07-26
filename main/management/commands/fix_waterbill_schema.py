from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import ProgrammingError

class Command(BaseCommand):
    help = 'Fix WaterBill table schema to match the Django model'

    def handle(self, *args, **options):
        # List of columns that should exist in the main_waterbill table
        required_columns = {
            'client_id': 'bigint',
            'meter_reading_id': 'bigint',
            'consumption': 'numeric(10,2)',
            'rate': 'numeric(10,2)',
            'amount': 'numeric(12,2)',
            'penalty_amount': 'numeric(12,2)',
            'total_amount': 'numeric(12,2)',
            'status': 'character varying(15)',
            'billing_date': 'date',
            'due_date': 'date',
            'payment_date': 'date',
            'notes': 'text',
            'created_at': 'timestamp with time zone',
            'updated_at': 'timestamp with time zone'
        }
        
        with connection.cursor() as cursor:
            # Get existing columns
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'main_waterbill' AND table_schema = 'public'
            """)
            existing_columns = {row[0]: row[1] for row in cursor.fetchall()}
            
            self.stdout.write(f'Existing columns: {list(existing_columns.keys())}')
            
            # Add missing columns
            for column_name, data_type in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        # Special handling for columns with default values or constraints
                        if column_name in ['consumption', 'rate', 'amount', 'penalty_amount', 'total_amount']:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type} DEFAULT 0.00")
                        elif column_name in ['status']:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type} DEFAULT 'Pending'")
                        elif column_name in ['created_at', 'updated_at']:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type} DEFAULT NOW()")
                        elif column_name in ['billing_date', 'due_date', 'payment_date']:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type}")
                        elif column_name in ['notes']:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type}")
                        else:
                            cursor.execute(f"ALTER TABLE main_waterbill ADD COLUMN {column_name} {data_type}")
                        
                        self.stdout.write(
                            self.style.SUCCESS(f'Added column {column_name} ({data_type})')
                        )
                    except ProgrammingError as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error adding column {column_name}: {e}')
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Column {column_name} already exists')
                    )
            
            # Remove old columns that are no longer needed
            old_columns = ['reading', 'meter_consumption', 'duedate', 'penaltydate', 'created_on', 'checkout_request_id', 'name_id']
            for column_name in old_columns:
                if column_name in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE main_waterbill DROP COLUMN {column_name}")
                        self.stdout.write(
                            self.style.SUCCESS(f'Removed old column {column_name}')
                        )
                    except ProgrammingError as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error removing column {column_name}: {e}')
                        )
        
        self.stdout.write(
            self.style.SUCCESS('WaterBill table schema update completed')
        )
