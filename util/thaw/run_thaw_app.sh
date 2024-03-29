#!/bin/bash

# run_thaw_app.sh
#
# Copyright (C) 2011-2021 Vas Vasiliadis
# University of Chicago
#
# Runs the Glacier thawing utility Flask app
#
##

# SSL with uWSGI not usable due to SNS subscription confirmation
# not working for HTTPS endpoints with letsencrypt wildcard certs
# Use plain ol' Flask dev server instead

# SSL_CERT_PATH=/usr/local/src/ssl/ucmpcs.org.crt
# SSL_KEY_PATH=/usr/local/src/ssl/ucmpcs.org.key

# export SOURCE_HOST=0.0.0.0
# export HOST_PORT=4433
export THAW_APP_HOME=/home/ubuntu/gas/util/thaw
cd /home/ubuntu/gas/util/thaw

# /home/ubuntu/.virtualenvs/mpcs/bin/uwsgi \
#   --manage-script-name \
#   --enable-threads \
#   --vacuum \a
#   --log-master \
#   --chdir $THAW_APP_HOME \
#   --socket /tmp/thaw_app.sock \
#   --mount /thaw_app=thaw_app:app \
#   --https $SOURCE_HOST:$HOST_PORT,$SSL_CERT_PATH,$SSL_KEY_PATH

source /usr/local/bin/virtualenvwrapper.sh
source /home/ubuntu/.virtualenvs/mpcs/bin/activate
python /home/ubuntu/gas/util/thaw/thaw_app.py

### EOF