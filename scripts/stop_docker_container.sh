#! /bin/bash

# Script to stop S3Watcher docker container

# Get variables
source s3watcher.config

# Stop the docker container if it is already running
if [ "$(docker ps | grep $CONTAINER_NAME)" ]; then
    echo "Stopping existing container $CONTAINER_NAME"
    docker stop $CONTAINER_NAME
fi

# Remove the docker container if it already exists
if [ "$(docker ps -a | grep $CONTAINER_NAME)" ]; then
    echo "Removing existing container $CONTAINER_NAME"
    docker rm $CONTAINER_NAME
fi

# Remove the docker image if it already exists
if [ "$(docker images -q $IMAGE_NAME)" ]; then
    echo "Removing existing image $IMAGE_NAME"
    docker rmi $IMAGE_NAME
fi


# Path: scripts/stop_docker_container.sh