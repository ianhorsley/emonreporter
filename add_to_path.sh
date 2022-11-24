#!/bin/bash
# -------------------------------------------------------------
# emonReporter install src to python path
# -------------------------------------------------------------
# Assumes emonreporter repository installed via git:
# git clone https://github.com/ianhorsley/emonreporter.git

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
usrdir=${DIR/\/emonreporter/}



# find directory
SITEDIR=$(python3 -m site --user-site)

# create if it doesn't exist
mkdir -p "$SITEDIR"

# create new .pth file with our path
echo "$usrdir/emonreporter/src" > "$SITEDIR/emonrep.pth"