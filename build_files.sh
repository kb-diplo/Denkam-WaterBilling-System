#!/bin/bash

# Collect static files
echo "Collecting static files..."
python3.9 manage.py collectstatic --noinput --clear
