#!/bin/bash
cd /home/la/workspace/onto
source .venv/bin/activate
python -m app.consumer &
python -m app.main