#! /bin/bash

# Script to update the S3Watcher docker container with the latest version of the code from the repo https://github.com/HERMES-SOC/s3watcher

# Get variables
source s3watcher.config

# Perform a git pull to get the latest version of the code
git pull

# If the script is not located in the scripts directory, then change the path to the scripts directory
if [ "$(basename $SCRIPT_PATH)" != "scripts" ]; then
    SCRIPT_PATH="$SCRIPT_PATH/scripts"
fi

# Print Script path
echo "Script path: $SCRIPT_PATH"

# Use the run_docker_container.sh script to build and run the docker container
$SCRIPT_PATH/run_docker_container.sh

# Path: scripts/update_docker_container.sh