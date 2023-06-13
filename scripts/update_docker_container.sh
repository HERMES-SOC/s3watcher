#! /bin/bash

# Script to update the S3Watcher docker container with the latest version of the code from the repo https://github.com/HERMES-SOC/s3watcher

# Default config file
CONFIG_FILE="s3watcher.config"

# Parse the options
while getopts "c:" opt; do
    case $opt in
        c)
            CONFIG_FILE=$OPTARG
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Verify the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file $CONFIG_FILE does not exist"
    exit 1
fi

# Get variables
source $CONFIG_FILE

# Perform a git pull to get the latest version of the code
git pull

# If the script is not located in the scripts directory, then change the path to the scripts directory
if [ "$(basename $SCRIPT_PATH)" != "scripts" ]; then
    SCRIPT_PATH="$SCRIPT_PATH/scripts"
fi

# Print Script path
echo "Script path: $SCRIPT_PATH"

# Use the run_docker_container.sh script to build and run the docker container
$SCRIPT_PATH/run_docker_container.sh -c $CONFIG_FILE

# Path: scripts/update_docker_container.sh