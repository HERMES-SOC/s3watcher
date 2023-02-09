# S3Watcher Utility

This is a filewatcher utility that polls an SQS queue for bucket events and then downloads the files to a defined local directory. It is designed to be used and run within a docker container, but it is not required. To run it outside of docker, you will need to ensure you have the requirements defined below. It is also required that that you have the correct AWS credentials set up for the user that will be running the script, and a valid access policy for your SQS queue, that allows the S3 bucket to send messages to the queue.

## Table of Contents
- [S3Watcher Utility](#s3watcher-utility)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Configurable Variables](#configurable-variables)
  - [Installation](#installation)
    - [Requirements](#requirements)
    - [Infrastructure Setup](#infrastructure-setup)
    - [S3Watcher Setup](#s3watcher-setup)
  - [Uninstallation](#uninstallation)

## Features
* Polls an SQS queue for bucket events.
* Downloads files from the S3 bucket to a local directory.
* Has ability to log files to Timestream database.
* Can be run in a docker container.

## Configurable Variables
There are a multitude of configurable variables that can be set in the `config.json` file or in the docker run command. The variables and what they represent are as follows:

* `SDC_AWS_SQS_QUEUE_NAME` this is the name of the SQS queue that the bucket sends it's event to. (**Required**)

* `SDC_AWS_S3_BUCKET` is the S3 bucket that will be watched and files downloaded from. (**Required**)

* `SDC_AWS_DOWNLOAD_PATH` is the directory that will be used for downloads. (**Required**)

* `SDC_AWS_TIMESTREAM_DB` is the Timestream database that will be used to store the logs. (*Optional*)

* `SDC_AWS_TIMESTREAM_TABLE` is the Timestream table that will be used to store the logs. (*Optional*)

* `SDC_AWS_TIMESTREAM_TABLE` is the Region the timestream db is located in. (*Required if above two are added*)

* `AWS_REGION` is the AWS region both he SQS Queue and Timestream DB is in. (*Optional*)

* `SDC_AWS_CONCURRENCY_LIMIT` is the Concurrent uploads limit to S3. (*Optional*)

* `SDC_AWS_SLACK_TOKEN` is the Slack token to use for sending messages to Slack. (*Optional*)

* `SDC_AWS_SLACK_CHANNEL` is the Slack channel to send messages to. (*Optional*)


## Installation

### Requirements

* Python 3.9 or higher
* Pip
* AWS Credentials
* AWS SQS Queue
* AWS S3 Bucket
* Docker (Optional)

### Infrastructure Setup
These are the steps to ensure you have the correct AWS infrastructure in place to run the script.

1. Create an SQS Queue (If not created already)
2. Create an S3 Bucket (If not created already)
3. Ensure the SQS Queue has a policy that allows the S3 Bucket to send messages to the queue. (Example below)

    ```json
    {
        "Version": "2012-10-17",
        "Id": "arn:aws:sqs:us-east-1:123456789012:MyQueue/SQSDefaultPolicy",
        "Statement": [
            {
                "Sid": "Sid1581234567890",
                "Effect": "Allow",
                "Principal": {
                    "AWS": "*"
                },
                "Action": "SQS:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:123456789012:MyQueue",
                "Condition": {
                    "ArnEquals": {
                        "aws:SourceArn": "arn:aws:s3:::mybucket"
                    }
                }
            }
        ]
    }
    ```
4. Set up bucket events to send 'CREATE' and 'PUT' events to the SQS Queue.
5. Test the bucket events by adding a file to the bucket and checking the SQS Queue for a message.

### S3Watcher Setup
These steps are to run S3Watcher using the docker container.

1. Clone the repo to your local machine.

    ```bash
    git clone https://github.com/HERMES-SOC/s3watcher.git

    cd s3watcher
    ```
2. Build the docker image.

    ```bash
    docker build -t s3watcher .
    ```
3. Run the docker container with the correct configurations, modifying the `<VARIABLES>` as needed. Look at the Configurable Variables section for more information on the variables.

    ```bash
    docker run -d \
    --restart=always \
    -e SDC_AWS_S3_BUCKET='-b <SDC_AWS_S3_BUCKET>' \
    -e SDC_AWS_SQS_QUEUE_NAME='-q <SDC_AWS_SQS_QUEUE_NAME>'
    -e SDC_AWS_TIMESTREAM_DB='-t <SDC_AWS_TIMESTREAM_DB>' \
    -e SDC_AWS_TIMESTREAM_TABLE='-tt <SDC_AWS_TIMESTREAM_TABLE>' \
    -e SDC_AWS_SLACK_TOKEN='-s ' \
    -e SDC_AWS_SLACK_CHANNEL='-sc ' \
    -e SDC_AWS_CONCURRENCY_LIMIT='-c 10' \
    -e AWS_REGION='us-east-1' \
    -v /etc/passwd:/etc/passwd \
    -v <SDC_AWS_DOWNLOAD_PATH>:/download \
    -v ${HOME}/.aws/credentials:/root/.aws/credentials:ro \
    -u `id -u`:`id -g` \
    s3watcher:latest
    ```

4. Check the logs to ensure the script is running correctly.

    ```bash
    docker logs -f <CONTAINER_ID>
    ```

## Uninstallation
These steps are to remove the docker container and image, and the cloned repo.

1. Stop the docker container.

    ```bash
    docker stop <CONTAINER_ID>
    ```
2. Remove the docker container.

    ```bash
    docker rm <CONTAINER_ID>
    ```
3. Remove the docker image.

    ```bash
    docker rmi s3watcher
    ```
4. Remove the cloned repo.

    ```bash
    rm -rf s3watcher
    ```

