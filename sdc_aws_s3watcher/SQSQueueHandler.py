import boto3
import boto3.s3.transfer as s3transfer
import botocore
import datetime
import concurrent.futures
from multiprocessing import Process, Queue

from sdc_aws_s3watcher import log
from SQSHandlerEvent import SQSHandlerEvent
from SQSQueueHandlerConfig import SQSQueueHandlerConfig

"""
Utility functions for sdc_aws_fswatcher.
"""
import os
import time
import polling

class SQSQueueHandler():

    event_queue = Queue()
    event_history = []
    event_history_limit = 10000

    def __init__(self, config: SQSQueueHandlerConfig) -> None:
        
        # Set download path
        self.download_path = config.path if config.path.endswith("/") else config.path + "/"

        # Set concurrency limit
        self.concurrency_limit = config.concurrency_limit

        # Check if queue exists
        try:
            # Initialize Boto3 Session
            self.session = (
                boto3.session.Session(profile_name=config.profile)
                if config.profile != ""
                else boto3.session.Session()
            )

            # Create SQS client
            self.sqs = self.session.client('sqs')

            # Check if queue exists
            self.sqs.get_queue_url(QueueName=config.queue_url)

            # Set queue url
            self.queue_url = config.queue_url

            # Set queue name
            self.queue_name = config.queue_url.split('/')[-1]


        except self.sqs.exceptions.QueueDoesNotExist:

            log.error(f'Error getting queue ({config.queue_url})')
            raise ValueError(f'Error getting queue ({config.queue_url})')

        except self.sqs.exceptions.ClientError:
                
                log.error(f'Error getting queue ({config.queue_url})')
                raise ValueError(f'Error getting queue ({config.queue_url})')

        # Check if bucket exists
        try:
            # Create S3 client
            self.s3 = self.session.client('s3')

            # Check if bucket exists
            self.s3.head_bucket(Bucket=config.bucket_name)

            # Set bucket name
            self.bucket_name = config.bucket_name

             # Initialize S3 Transfer Manager with concurrency limit
            botocore_config = botocore.config.Config(
                max_pool_connections=self.concurrency_limit
            )
            s3client = self.session.client("s3", config=botocore_config)
            transfer_config = s3transfer.TransferConfig(
                use_threads=True,
                max_concurrency=self.concurrency_limit,
            )
            self.s3t = s3transfer.create_transfer_manager(s3client, transfer_config)

        except self.s3.exceptions.ClientError:

            log.error(f'Error getting bucket ({self.bucket_name})')
            raise ValueError(f'Error getting bucket ({self.bucket_name})')
        
        self.timestream_db = config.timestream_db
        self.timestream_table = config.timestream_table
        self.allow_delete = config.allow_delete

        log.info(f'Queue ({self.queue_name}) found')
        log.info('S3Watcher initialized successfully')

    def get_messages(self, max_batch_size:int = 10) -> SQSHandlerEvent:
        try:
            # Receive message from SQS queue
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                AttributeNames=[
                    'SentTimestamp'
                ],
                MaxNumberOfMessages=max_batch_size,
                MessageAttributeNames=[
                    'All'
                ],
                VisibilityTimeout=0,
                WaitTimeSeconds=0,

            )

            messages = response.get('Messages')

            if messages:
               
                # Queue messages
                sqs_events = self.queue_messages(messages)

                return sqs_events

            return None

        except Exception as e:

            log.error(f'Error getting messages from queue ({self.queue_url}): {e}')


    def queue_messages(self, messages: list):
        """
        Function to queue messages.
        """
        # Initialize SQSHandlerEvent objects
        sqs_events = [SQSHandlerEvent(message) for message in messages]

        # Delete messages from AWS SQS queue
        [self.delete_message(event) for event in sqs_events]

        # Concatenate message batch to event array if events don't already exist in it
        for event in sqs_events:
            if event.message_id not in self.event_history:
                self.event_history.append(event.message_id)
                self.event_queue.put(event)

        # Clear event history if limit is reached
        self.clean_event_history()

        return sqs_events


    def clean_event_history(self)-> None:
        """
        Function to clean event history.
        """
        if len(self.event_history) > self.event_history_limit:
            self.event_history = self.event_history[int(self.event_history_limit/2):]


    def process_message(self, sqs_event: SQSHandlerEvent):
        """
        Function to process sqs event messages.
        """
        try:
            if sqs_event.event_type == 'CREATE':
                file_key = sqs_event.file_key

                if file_key:
                    # Download file from S3
                    self.download_file_from_s3(file_key)

                    if self.timestream_db and self.timestream_table not in [None, '']:
                        # Write file to Timestream
                        self._log(boto3_session=self.session, timestream_db=self.timestream_db, timestream_table=self.timestream_table, file_key=file_key, source_bucket=self.bucket_name, action_type=sqs_event.event_type)


        except Exception as e:
            log.error(f'Error getting file key from message: {e}')


    def process_messages(self):
        """
        Function to process batch of sqs events.
        """

        while True:
            
            # Threadpool executor
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                event = self.event_queue.get()

                if event is None:
                    return

                # Get messages from queue
                executor.submit(self.process_message(event))



    def delete_message(self, sqs_event: SQSHandlerEvent) :
        try:

            # Delete received message from queue
            response = self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=sqs_event.receipt_handle
            )

            if response.get('ResponseMetadata').get('HTTPStatusCode') == 200:
                log.info(f'Deleted message from queue ({self.queue_url})')

            else:
                log.error(f'Error deleting message from queue ({self.queue_url})')
            

        except Exception as e:
            log.error(f'Error deleting message from queue ({self.queue_url}): {e}')

    def download_file_from_s3(self, file_key: str):
        """
        Function to download file from S3.
        """
        try:
            # Loop through file_key and create directory if it does not exist
            file_key_split = file_key.split('/')
            for i in range(len(file_key_split) - 1):
                self.create_directory(self.download_path + '/'.join(file_key_split[:i+1]))

            # Download file from S3
            self.s3t.download(self.bucket_name, file_key, self.download_path + file_key)

            log.info(f'Downloaded file ({file_key}) from S3 bucket ({self.bucket_name})')

        except Exception as e:
            log.error(f'Error downloading file ({file_key}) from S3 bucket ({self.bucket_name}): {e}')
            

    def create_directory(self, directory: str):
        """
        Function to create directory if it does not exist.
        """
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
                log.info(f'Created directory ({directory})')
        except Exception as e:
            log.error(f'Error creating directory ({directory}): {e}')
        


    def start(self):
        """
        Function to start polling for messages.
        """
        # Poll on 10 threads

        
        p1 = Process(target = self.process_messages)
        p1.start()
        p2 = Process(target = self.poll)
        p2.start()



    def poll(self, delay: int = 1):

        log.info(f'Polling for messages on queue ({self.queue_name})')
        
        while True:
            # Threadpool executor
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:

                def thread_poll():
                    # Poll for messages
                    polling.poll(
                        lambda: self.get_messages(),
                        step=delay,
                        poll_forever=True,
                        check_success=lambda x: x is not None,
                        exception_handler=lambda x: log.error(f'Error polling for messages on queue ({self.queue_name}): {x}')
                    )


                executor.submit(thread_poll)
                time.sleep(delay)            
            
            
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
                        "MeasureValue": str(datetime.utcnow().timestamp()),
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