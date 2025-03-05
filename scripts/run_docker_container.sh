#! /bin/bash

# Script to build and run the S3Watcher docker container

#!/bin/bash

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

# Verify that the directory to be watched exists
if [ ! -d "$DOWNLOAD_DIR" ]; then
    echo "Directory $DOWNLOAD_DIR does not exist"
    exit 1
fi

# If the script is not located in the scripts directory, then change the path to the scripts directory
if [ "$(basename $SCRIPT_PATH)" != "scripts" ]; then
    SCRIPT_PATH="$SCRIPT_PATH/scripts"
fi

# Print Script path
echo "Script path: $SCRIPT_PATH"

# Get path of the dockerfile which is in the upper directory
DOCKERFILE_PATH=$(dirname $SCRIPT_PATH)

# Print Dockerfile path
echo "Dockerfile path: $DOCKERFILE_PATH"

# Stop the docker container using the stop_docker_container.sh script
$SCRIPT_PATH/stop_docker_container.sh -c $CONFIG_FILE

# Build the docker image
echo "Building docker image $IMAGE_NAME"
docker build --network host -t $IMAGE_NAME $DOCKERFILE_PATH

# Run the docker container
echo "Running docker container $CONTAINER_NAME"

# Unset all the environment variables
unset SDC_AWS_S3_BUCKET
unset SDC_AWS_SQS_QUEUE_NAME
unset SDC_AWS_CONCURRENCY_LIMIT
unset SDC_AWS_TIMESTREAM_DB
unset SDC_AWS_TIMESTREAM_TABLE
unset SDC_AWS_SLACK_TOKEN
unset SDC_AWS_SLACK_CHANNEL
unset SDC_AWS_ALLOW_DELETE
unset SDC_AWS_USER
unset SDC_AWS_SETUP
unset SDC_AWS_CHECK_S3


# Docker environment variables
SDC_AWS_S3_BUCKET="-b $S3_BUCKET_NAME"

SDC_AWS_SQS_QUEUE_NAME="-q $SQS_QUEUE_NAME"

SDC_AWS_CONCURRENCY_LIMIT="-c $CONCURRENCY_LIMIT"

# If TimeStream database name is not "", then add it to the environment variables else make it empty
if [ "$TIMESTREAM_DB" != "" ]; then
    SDC_AWS_TIMESTREAM_DB="-t $TIMESTREAM_DB"
else
    SDC_AWS_TIMESTREAM_DB=""
fi


# If Timestream table name is not "", then add it to the environment variables else make it empty
if [ "$TIMESTREAM_TABLE" != "" ]; then
    SDC_AWS_TIMESTREAM_TABLE="-tt $TIMESTREAM_TABLE"
else
    SDC_AWS_TIMESTREAM_TABLE=""
fi

# If Slack token is not "", then add it to the environment variables else make it empty
if [ "$SLACK_TOKEN" != "" ]; then
    SDC_AWS_SLACK_TOKEN="-s $SLACK_TOKEN"
else
    SDC_AWS_SLACK_TOKEN=""
fi

# If Slack channel is not "", then add it to the environment variables else make it empty
if [ "$SLACK_CHANNEL" != "" ]; then
    SDC_AWS_SLACK_CHANNEL="-sc $SLACK_CHANNEL"
else
    SDC_AWS_SLACK_CHANNEL=""
fi

# If USER is not "", then perform an id -u and id -g and add each of them to the environment variables else make it empty
if [ "$USER" != "" ]; then
    SDC_AWS_USER=$(id -u $USER):$(id -g $USER)
else
    SDC_AWS_USER=$(id -u):$(id -g)
fi

# If ALLOW_DELETE is true, then add it to the environment variables else make it empty
if [ "$ALLOW_DELETE" = true ]; then
    SDC_AWS_ALLOW_DELETE="-a"
else
    SDC_AWS_ALLOW_DELETE=""
fi

# If SETUP is true, then add it to the environment variables else make it empty
if [ "$SETUP" = true ]; then
    SDC_AWS_SETUP="true"
else
    SDC_AWS_SETUP=""
fi

# If CHECK_S3 is true, then add it to the environment variables else make it empty
if [ "$CHECK_S3" = true ]; then
    SDC_AWS_CHECK_S3="true"
else
    SDC_AWS_CHECK_S3=""
fi


# Print all the environment variables
echo "Passed Arguments:"
echo "SDC_AWS_S3_BUCKET: $SDC_AWS_S3_BUCKET"
echo "SDC_AWS_CONCURRENCY_LIMIT: $SDC_AWS_CONCURRENCY_LIMIT"
echo "SDC_AWS_TIMESTREAM_DB: $SDC_AWS_TIMESTREAM_DB"
echo "SDC_AWS_TIMESTREAM_TABLE: $SDC_AWS_TIMESTREAM_TABLE"
echo "SDC_AWS_SLACK_TOKEN: $SDC_AWS_SLACK_TOKEN"
echo "SDC_AWS_SLACK_CHANNEL: $SDC_AWS_SLACK_CHANNEL"
echo "SDC_AWS_ALLOW_DELETE: $SDC_AWS_ALLOW_DELETE"
echo "SDC_AWS_USER": $SDC_AWS_USER
echo "AWS_REGION: $AWS_REGION"
echo "FILE_LOGGING: $FILE_LOGGING"
echo "BOTO3_LOGGING: $BOTO3_LOGGING"
echo "TEST_IAM_POLICY: $TEST_IAM_POLICY"
echo "BACKTRACK: $BACKTRACK"
echo "BACKTRACK_DATE: $BACKTRACK_DATE"
echo "USE_FALLBACK: $USE_FALLBACK"


docker run -d \
    --restart=always \
    --network host \
    --name=$CONTAINER_NAME \
    -e SDC_AWS_S3_BUCKET="$SDC_AWS_S3_BUCKET" \
    -e SDC_AWS_SQS_QUEUE_NAME="$SDC_AWS_SQS_QUEUE_NAME" \
    -e SDC_AWS_CONCURRENCY_LIMIT="$SDC_AWS_CONCURRENCY_LIMIT" \
    -e AWS_DEFAULT_REGION="$AWS_REGION" \
    -e SDC_AWS_TIMESTREAM_DB="$SDC_AWS_TIMESTREAM_DB" \
    -e SDC_AWS_TIMESTREAM_TABLE="$SDC_AWS_TIMESTREAM_TABLE" \
    -e SDC_AWS_SLACK_TOKEN="$SDC_AWS_SLACK_TOKEN" \
    -e SDC_AWS_SLACK_CHANNEL="$SDC_AWS_SLACK_CHANNEL" \
    -e SDC_AWS_USER="$SDC_AWS_USER" \
    -e SDC_AWS_SETUP="$SDC_AWS_SETUP" \
    -e CHECK_S3="$SDC_AWS_CHECK_S3" \
    -v /etc/passwd:/etc/passwd \
    -v $DOWNLOAD_DIR:/download \
    -v ${HOME}/.aws/credentials:/s3watcher/.aws/credentials:ro \
    $IMAGE_NAME
# Print the docker logs
echo "Docker logs"

# Docker ps
docker ps

# Path: scripts/run_docker_container.sh
