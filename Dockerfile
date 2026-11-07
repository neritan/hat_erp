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
# The base image keeps built assets in /home/frappe/frappe-bench/assets and its entrypoint links
# sites/assets to that folder on every start (sites/ is a volume). Build HAT through the same link,
# so hat.bundle.js and /assets/hat/... land in the baked folder next to frappe and erpnext.
RUN env/bin/pip install --no-cache-dir -e apps/hat \
    && ls -1 apps > sites/apps.txt \
    && rm -rf sites/assets \
    && ln -s /home/frappe/frappe-bench/assets sites/assets \
    && bench build --app hat \
    && test -e /home/frappe/frappe-bench/assets/hat/images/hat_icon.png \
    && grep -q '"hat.bundle.js"' /home/frappe/frappe-bench/assets/assets.json \
    && grep -q '"desk.bundle.js"' /home/frappe/frappe-bench/assets/assets.json
