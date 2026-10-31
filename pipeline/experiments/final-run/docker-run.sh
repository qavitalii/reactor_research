#!/usr/bin/env bash
# Start the final test run in a detached container so it survives this agent session.
# Credentials are read from the env file and passed as variables; nothing is printed.
set -u
. "$HOME/.config/memchal/reactor.env"
docker rm -f memchal-final >/dev/null 2>&1
docker run -d --name memchal-final \
  -v /home/alex/code/personal/memory-challenge:/work -w /work/pipeline \
  -e HOME=/tmp -e PYTHONPATH=/work/.venv/lib/python3.12/site-packages -e PY=python \
  -e REACTOR_BASE_URL -e REACTOR_AGENT_ID -e REACTOR_ACCESS_KEY -e INSTRUCTIONS=instructions/reactor_instructions.txt \
  python:3.12-slim bash -c 'mkdir -p /tmp/.config/memchal && : > /tmp/.config/memchal/reactor.env && exec bash runs/test-final/run.sh' \
  && echo "container started; follow with: docker logs -f memchal-final"
