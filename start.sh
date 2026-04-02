#!/bin/bash
cd /app
exec python -m gunicorn run:app --bind "0.0.0.0:${PORT:-5000}" --workers 1 --threads 2 --timeout 120
