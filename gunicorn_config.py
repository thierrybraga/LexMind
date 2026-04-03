"""
Gunicorn Configuration - IA Juridica
Para deploy no Heroku e producao
"""

import os
import multiprocessing

# Server Socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker Processes
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Process Naming
proc_name = "ia-juridica"

# Server Mechanics
preload_app = True
daemon = False
