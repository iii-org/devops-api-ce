#!/bin/sh

set -e

export PYTHONPATH=/usr/src/app/apis

# If arguments are passed to docker, run them instead
if [ ! "$#" -gt 0 ]; then
  gunicorn --worker-class gevent -w 1 'apis.api:start_prod()' --timeout 120  -b 0.0.0.0:10009
fi

exec "$@"
