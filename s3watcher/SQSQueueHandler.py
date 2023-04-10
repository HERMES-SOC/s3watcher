import os
import time
import polling
import boto3
import boto3.s3.transfer as s3transfer
import botocore
from multiprocessing import Process, Queue

from aws_sdc_utils.aws import (
    create_timestream_client_session,
    log_to_timestream,
)
from aws_sdc_utils.slack import get_slack_client, send_slack_notification
from sdc_aws_utils.logging import log

from s3watcher.SQSHandlerEvent import SQSHandlerEvent
from s3watcher.SQSQueueHandlerConfig import SQSQueueHandlerConfig

"""
Utility functions for s3watcher.
"""


class SQSQueueHandler:
    event_queue = Queue()
    event_history = []
    event_history_limit = 100000

    def __init__(self, config: SQSQueueHandlerConfig) -> None:
        # Set download path
        self.download_path = (
            config.path if config.path.endswith("/") else config.path + "/"
        )

        # Set concurrency limit
        self.concurrency_limit = config.concurrency_limit

        # Check if queue exists
        try:
            # Initialize Boto3 Session
            self.session = (
                boto3.session.Session(profile_name=config.profile)
                if config.profile != ""
                else boto3.session.Session(region=os.getenv("AWS_REGION"))
            )

            # Create SQS client
            self.sqs = self.session.client("sqs")
            # Set queue name
            self.queue_name = config.queue_name

            # Check if queue exists
            self.queue_url = self.sqs.get_queue_url(QueueName=config.queue_name)[
                "QueueUrl"
            ]

        except self.sqs.exceptions.QueueDoesNotExist:
            log.error(f"Error getting queue ({config.queue_name})")
            raise ValueError(f"Error getting queue ({config.queue_name})")

        except self.sqs.exceptions.ClientError:
            log.error(f"Error getting queue ({config.queue_name})")
            raise ValueError(f"Error getting queue ({config.queue_name})")

        # Check if bucket exists
        try:
            # Create S3 client
            self.s3 = self.session.client("s3")

            # Check if bucket exists
            self.s3.head_bucket(Bucket=config.bucket_name)

            # Set bucket name
            self.bucket_name = config.bucket_name

            # Initialize S3 Transfer Manager with concurrency limit
            botocore_config = botocore.config.Config(max_pool_connections=10)
            self.s3client = self.session.client("s3", config=botocore_config)
            transfer_config = s3transfer.TransferConfig(
                use_threads=True,
                max_concurrency=10,
            )
            self.s3t = s3transfer.create_transfer_manager(
                self.s3client, transfer_config
            )

            if config.timestream_db != "" and config.timestream_table != "":
                # Create Timestream client
                self.timestream_client = create_timestream_client_session()

        except self.s3.exceptions.ClientError:
            log.error(f"Error getting bucket ({self.bucket_name})")
            raise ValueError(f"Error getting bucket ({self.bucket_name})")

        self.timestream_db = config.timestream_db
        self.timestream_table = config.timestream_table
        self.allow_delete = config.allow_delete

        try:
            # Initialize the slack client
            self.slack_client = get_slack_client(config.slack_token)

            # Initialize the slack channel
            self.slack_channel = config.slack_channel

        except Exception as e:
            log.error(f"Error initializing slack client: {e}")

        log.info(f"Queue ({self.queue_name}) found")
        log.info("S3Watcher initialized successfully")

    def get_messages(self, max_batch_size: int = 10) -> None:
        try:
            # Receive message from SQS queue
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                AttributeNames=["SentTimestamp"],
                MaxNumberOfMessages=max_batch_size,
                MessageAttributeNames=["All"],
                VisibilityTimeout=5,
                WaitTimeSeconds=0,
            )

            messages = response.get("Messages")

            if messages is not None:
                # Queue messages
                sqs_events = self.queue_messages(messages)

                return sqs_events

            return None

        except Exception as e:
            log.error(f"Error getting messages from queue ({self.queue_url}): {e}")

    def queue_messages(self, messages: list):
        """
        Function to queue messages.
        """
        # Initialize SQSHandlerEvent objects
        sqs_events = [
            SQSHandlerEvent(self.sqs, message, self.queue_url) for message in messages
        ]

        # Concatenate message batch to event array if events don't already exist in it
        for event in sqs_events:
            if event.message_id not in self.event_history:
                self.event_history.append(event.message_id)
                self.event_queue.put(event)

        # Clear event history if limit is reached
        self.clean_event_history()

        return sqs_events

    def clean_event_history(self) -> None:
        """
        Function to clean event history.
        """
        if len(self.event_history) > self.event_history_limit:
            self.event_history = self.event_history[int(self.event_history_limit / 2) :]

    def process_message(self, sqs_event: SQSHandlerEvent):
        """
        Function to process sqs event messages.
        """
        try:
            if sqs_event.event_type == "CREATE":
                file_key = sqs_event.file_key

                if file_key:
                    # Download file from S3
                    self.download_file_from_s3(file_key)

                    # Send Slack Notification about the event
                    if self.slack_client is not None:
                        slack_message = f"S3Watcher: New file downloaded from bucket {self.bucket_name} - ({file_key}) :bucket:"
                        send_slack_notification(
                            slack_client=self.slack_client,
                            slack_channel=self.slack_channel,
                            slack_message=slack_message,
                        )

                    # Delete messages from AWS SQS queue
                    sqs_event.delete_message(self.sqs)

                    if self.timestream_client:
                        # Write file to Timestream
                        log_to_timestream(
                            self.timestream_client,
                            timestream_db=self.timestream_db,
                            timestream_table=self.timestream_table,
                            file_key=file_key,
                            new_file_key=file_key,
                            source_bucket=self.bucket_name,
                            action_type="PUT",
                            destination_bucket="External Server",
                        )

        except Exception as e:
            log.error(f"Error getting file key from message: {e}")

    def process_messages(self):
        """
        Function to process batch of sqs events.
        """

        while True:
            event = self.event_queue.get()

            if event is None:
                return

            self.process_message(event)

    def download_file_from_s3(self, file_key: str):
        """
        Function to download file from S3.
        """
        try:
            # Loop through file_key and create directory if it does not exist
            file_key_split = file_key.split("/")
            for i in range(len(file_key_split) - 1):
                self.create_directory(
                    self.download_path + "/".join(file_key_split[: i + 1])
                )

            # Download file from S3
            self.s3t.download(self.bucket_name, file_key, self.download_path + file_key)

            log.info(
                f"Downloaded file ({file_key}) from S3 bucket ({self.bucket_name})"
            )

        except Exception as e:
            log.error(
                f"Error downloading file ({file_key}) from S3 bucket ({self.bucket_name}): {e}"
            )

    def create_directory(self, directory: str):
        """
        Function to create directory if it does not exist.
        """
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
                log.info(f"Created directory ({directory})")
        except Exception as e:
            log.error(f"Error creating directory ({directory}): {e}")

    def start(self):
        """
        Function to start polling for messages.
        """
        # Poll on 10 threads

        p1 = Process(target=self.process_messages)
        p1.start()
        p2 = Process(target=self.poll)
        p2.start()

    def poll(self):
        log.info(f"Polling for messages on queue ({self.queue_name})")

        while True:
            # Poll for messages
            polling.poll(
                lambda: self.get_messages(),
                poll_forever=True,
                step=1,
                check_success=lambda x: x is not None,
                exception_handler=lambda x: log.error(
                    f"Error polling for messages on queue ({self.queue_name}): {x}"
                ),
            )
