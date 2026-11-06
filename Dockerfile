# syntax=docker/dockerfile:1
# HAT on top of the official ERPNext image.
# BuildKit is required: the base image declares sites/ as a VOLUME, and the legacy
# builder would throw away the apps.txt / assets changes made below.
#
# Build (from the root of this repo):
#   docker build -t hat:latest .
#   docker build --build-arg ERPNEXT_VERSION=v16.37.0 -t hat:v16.37.0 .
#
# The result is a drop-in replacement for frappe/erpnext in frappe_docker's
# compose files (pwd.yml / compose.yaml): set the image to hat:latest, then
#   bench --site <site> install-app hat
# on a new site, or `bench --site <site> migrate` on an existing one.

ARG ERPNEXT_VERSION=v16.37.0
FROM frappe/erpnext:${ERPNEXT_VERSION}

USER frappe
WORKDIR /home/frappe/frappe-bench

COPY --chown=frappe:frappe . apps/hat

# Install the app into the bench virtualenv, register it, and build its assets.
RUN env/bin/pip install --no-cache-dir -e apps/hat \
    && ls -1 apps > sites/apps.txt \
    && bench build --app hat
