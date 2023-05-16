import os
import time
import polling
import json
import boto3
from boto3.s3.transfer import TransferConfig, S3Transfer
import botocore
import datetime
from multiprocessing import Process, Queue
import concurrent.futures
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from s3watcher import log
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

        # Initialize Boto3 Session
        self.session = (
            boto3.session.Session(profile_name=config.profile)
            if config.profile != ""
            else boto3.session.Session(region=os.getenv("AWS_REGION"))
        )

        self.sqs = self.session.client("sqs")

        # Set queue name
        self.queue_name = config.queue_name

        if ":" in os.getenv("SDC_AWS_USER"):
            self.user = os.getenv("SDC_AWS_USER").split(":")
            # convert to int
            self.user = [int(i) for i in self.user]
        else:
            self.user = [1000, 1000]

        self.queue = self.create_or_get_sqs_queue(self.queue_name)

        self.queue_url = self.queue.url

        # Check if bucket exists
        try:
            # Create S3 client
            self.s3 = self.session.client("s3")

            self.bucket_name, self.folder = self.extract_folder_from_bucket_name(
                config.bucket_name
            )
            # Check if bucket exists
            self.s3.head_bucket(Bucket=self.bucket_name)

            # Initialize S3 Transfer Manager with concurrency limit
            botocore_config = botocore.config.Config(max_pool_connections=10)
            s3client = self.session.client("s3", config=botocore_config)
            transfer_config = TransferConfig(
                use_threads=True,
                max_concurrency=10,
            )
            self.s3t = S3Transfer(s3client, transfer_config)

        except self.s3.exceptions.ClientError:
            log.error(f"Error getting bucket ({self.bucket_name})")
            raise ValueError(f"Error getting bucket ({self.bucket_name})")

        self.timestream_db = config.timestream_db
        self.timestream_table = config.timestream_table
        self.allow_delete = config.allow_delete

        try:
            # Initialize the slack client
            if config.slack_token:
                self.slack_client = WebClient(token=config.slack_token)
            else:
                self.slack_client = None
            # Initialize the slack channel
            self.slack_channel = config.slack_channel

        except SlackApiError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Slack Token ({config.slack_token}) is invalid",
                    }
                )

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
                        self._send_slack_notification(
                            slack_client=self.slack_client,
                            slack_channel=self.slack_channel,
                            slack_message=slack_message,
                        )

                    # Delete messages from AWS SQS queue
                    sqs_event.delete_message(self.sqs)

                    if self.timestream_db and self.timestream_table not in [None, ""]:
                        # Write file to Timestream
                        self._log(
                            boto3_session=self.session,
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
        if os.getenv("CHECK_S3") == "true":
            check_s3 = True
        else:
            check_s3 = False
        while True:
            if check_s3:
                # Get all keys in bucket
                keys = []
                try:
                    # with pagination with folder prefix
                    paginator = self.s3.get_paginator("list_objects_v2")
                    if self.folder not in [None, ""]:
                        prefix = f"{self.folder}/"
                    else:
                        prefix = ""
                    page_iterator = paginator.paginate(
                        Bucket=self.bucket_name, Prefix=prefix
                    )
                    for page in page_iterator:
                        if "Contents" in page:
                            for key in page["Contents"]:
                                # remove the first /folder/ from the key
                                if self.folder not in [None, ""]:
                                    key["Key"] = key["Key"].replace(
                                        f"{self.folder}/", "", 1
                                    )

                                if key["Key"] != "":
                                    keys.append(key["Key"])

                except Exception as e:
                    log.error(
                        f"Error getting keys from bucket ({self.bucket_name}): {e}"
                    )

                # Get all keys in download path
                downloaded_keys = []
                for root, _, files in os.walk(self.download_path):
                    for file in files:
                        downloaded_keys.append(os.path.join(root, file))
                        # remove the first /download/ from the path
                        downloaded_keys = [
                            key.replace(self.download_path, "", 1)
                            for key in downloaded_keys
                        ]

                # Get all keys in the s3 bucket that are not in the download path
                keys_to_download = list(set(keys) - set(downloaded_keys))

                # log all keys
                log.info(f"Keys in bucket ({self.bucket_name}): {len(keys)}")
                # log first 10 keys
                log.info(f"First 10 keys in bucket ({self.bucket_name}): {keys[:10]}")
                log.info(
                    f"Keys in download path ({self.download_path}): {len(downloaded_keys)}"
                )
                # log first 10 keys
                log.info(
                    f"First 10 keys in download path ({self.download_path}): {downloaded_keys[:10]}"
                )

                log.info(
                    f"Keys to download ({self.bucket_name}): {len(keys_to_download)}"
                )
                log.info(
                    f"First 10 keys to download ({self.bucket_name}): {keys_to_download[:10]}"
                )
                for key in keys_to_download:
                    # Download file from S3 Async
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        if self.folder not in [None, ""]:
                            key = f"{self.folder}/" + key
                        executor.submit(self.download_file_from_s3, key)

                check_s3 = False
            event = self.event_queue.get()
            self.process_message(event)

    def download_file_from_s3(self, file_key: str):
        """
        Function to download file from S3.
        """
        try:
            # Loop through file_key and create directory if it does not exist
            download_file_key = file_key
            # Replace first /{folder}/ from file_key
            if self.folder not in [None, ""]:
                file_key = file_key.replace(f"{self.folder}/", "", 1)
            file_key_split = file_key.split("/")
            for i in range(len(file_key_split) - 1):
                self.create_directory(
                    self.download_path + "/".join(file_key_split[: i + 1])
                )

            # Download file from S3
            self.s3t.download_file(
                self.bucket_name,
                download_file_key,
                self.download_path + file_key,
            )

            # Change file permissions
            os.chown(self.download_path + file_key, self.user[0], self.user[1])

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
                step=0.25,
                check_success=lambda x: x is not None,
                exception_handler=lambda x: log.error(
                    f"Error polling for messages on queue ({self.queue_name}): {x}"
                ),
            )

    @staticmethod
    def _send_slack_notification(
        slack_client,
        slack_channel: str,
        slack_message: str,
        alert_type: str = "success",
    ) -> None:
        """
        Function to send a Slack Notification
        """
        log.info(f"Sending Slack Notification to {slack_channel}")
        try:
            color = {
                "success": "#e67e22",
                "error": "#ff0000",
            }
            ct = datetime.datetime.now()
            ts = ct.strftime("%y-%m-%d %H:%M:%S")
            slack_client.chat_postMessage(
                channel=slack_channel,
                text=f"{ts} - {slack_message}",
                attachments=[
                    {
                        "color": color[alert_type],
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{ts} - {slack_message}",
                                },
                            }
                        ],
                    }
                ],
            )

        except SlackApiError as e:
            log.error(
                {"status": "ERROR", "message": f"Error sending Slack Notification: {e}"}
            )

    @staticmethod
    def _log(
        boto3_session,
        action_type,
        file_key,
        new_file_key=None,
        source_bucket=None,
        destination_bucket=None,
        timestream_db=None,
        timestream_table=None,
    ):
        """
        Function to Log to Timestream
        """
        log.info(f"Object ({new_file_key}) - Logging Event to Timestream")
        CURRENT_TIME = str(int(time.time() * 1000))
        try:
            # Initialize Timestream Client
            timestream = boto3_session.client("timestream-write")

            if not source_bucket and not destination_bucket:
                raise ValueError("A Source or Destination Buckets is required")

            # Write to Timestream
            timestream.write_records(
                DatabaseName=timestream_db if timestream_db else "sdc_aws_logs",
                TableName=timestream_table
                if timestream_table
                else "sdc_aws_s3_bucket_log_table",
                Records=[
                    {
                        "Time": CURRENT_TIME,
                        "Dimensions": [
                            {"Name": "action_type", "Value": action_type},
                            {
                                "Name": "source_bucket",
                                "Value": source_bucket or "N/A",
                            },
                            {
                                "Name": "destination_bucket",
                                "Value": destination_bucket or "N/A",
                            },
                            {"Name": "file_key", "Value": file_key},
                            {
                                "Name": "new_file_key",
                                "Value": new_file_key or "N/A",
                            },
                            {
                                "Name": "current file count",
                                "Value": "N/A",
                            },
                        ],
                        "MeasureName": "timestamp",
                        "MeasureValue": str(datetime.datetime.utcnow().timestamp()),
                        "MeasureValueType": "DOUBLE",
                    },
                ],
            )

            log.info(
                (f"Object ({new_file_key}) - Event Successfully Logged to Timestream")
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error logging to Timestream: {e}"}
            )

    def setup(self):
        self.add_permissions_to_sqs(self.queue, self.bucket_name)
        self.configure_s3_bucket_events(self.bucket_name, self.folder, self.queue)

        print(
            f"SQS queue '{self.queue_name}' is now configured to receive events from S3 bucket '{self.bucket_name}' with prefix '{self.folder}'."
        )

    def create_or_get_sqs_queue(self, queue_name):
        sqs = boto3.resource("sqs")
        try:
            queue = sqs.get_queue_by_name(QueueName=queue_name)
            log.info(f"Queue ({queue_name}) already exists")
            return queue
        except Exception:
            if os.getenv("SDC_AWS_SETUP") == "true":
                queue = sqs.create_queue(QueueName=queue_name)
                log.info(f"Creating SQS Queue ({queue_name})")
                return queue
            else:
                raise Exception(
                    f"Queue ({queue_name}) does not exist. Please pass SDC_AWS_SETUP as 'true' as an environment variable to automatically set it up."
                )

    @staticmethod
    def add_permissions_to_sqs(queue, bucket_name):
        queue_policy = {
            "Version": "2012-10-17",
            "Id": "S3EventsPolicy",
            "Statement": [
                {
                    "Sid": "S3Events",
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue.attributes["QueueArn"],
                    "Condition": {
                        "ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{bucket_name}"}
                    },
                }
            ],
        }
        queue.set_attributes(Attributes={"Policy": json.dumps(queue_policy)})

    @staticmethod
    def configure_s3_bucket_events(bucket_name, folder, queue):
        if folder.endswith("/"):
            folder = folder[:-1]

        s3 = boto3.client("s3")
        events_config = {
            "QueueConfigurations": [
                {
                    "Id": f"{bucket_name}-{folder}-events",
                    "QueueArn": queue.attributes["QueueArn"],
                    "Events": [
                        "s3:ObjectCreated:*",
                    ],
                    "Filter": {
                        "Key": {"FilterRules": [{"Name": "prefix", "Value": folder}]}
                    },
                }
            ]
        }
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name, NotificationConfiguration=events_config
        )

    @staticmethod
    def extract_folder_from_bucket_name(bucket_name):
        if "/" not in bucket_name:
            return bucket_name, ""

        if len(bucket_name.split("/")) > 2:
            return bucket_name.replace("/", "", 1), ""

        return bucket_name.split("/", 1)[0], bucket_name.split("/", 1)[-1]
