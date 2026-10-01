#!/bin/bash
set -eu
umask 077
if [ ! -e /app/data/api-key ]; then
    /app/code/venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))' > /app/data/api-key.tmp
    mv /app/data/api-key.tmp /app/data/api-key
fi
chown cloudron:cloudron /app/data/api-key
chmod 600 /app/data/api-key
exec /usr/local/bin/gosu cloudron:cloudron /app/code/venv/bin/python /app/code/app.py
