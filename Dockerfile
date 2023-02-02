## Dockerfile for building a container that runs s3watcher

# Base image
FROM python:3.11

# Install Curl
RUN apt-get update && \
    apt-get install -y curl

# Install Unzip
RUN apt-get install -y unzip

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install

# Add files to the container
ADD . /s3watcher

# Set the working directory
WORKDIR /s3watcher

# Change where boto3 looks for credentials
ENV AWS_SHARED_CREDENTIALS_FILE=/s3watcher/.aws/credentials

# Install dependencies
RUN pip install -r /s3watcher/requirements.txt

# Install s3watcher
RUN pip install .

# Run s3watcher
CMD python s3watcher/__main__.py -d /download $SDC_AWS_SQS_QUEUE_NAME $SDC_AWS_S3_BUCKET $SDC_AWS_TIMESTREAM_DB $SDC_AWS_TIMESTREAM_TABLE $SDC_AWS_CONCURRENCY_LIMIT
