import json
import botocore
from typing import Any
from s3watcher import log


class SQSHandlerEvent:
    def __init__(
        self, sqs_client: botocore.client.SQS, sqs_message: dict, queue_url: str
    ) -> None:
        """
        Class Constructor
        """

        self.message_id = sqs_message.get("MessageId")
        self.receipt_handle = sqs_message.get("ReceiptHandle")
        message_body = json.loads(sqs_message.get("Body"))
        self.file_key = self.get_file_key(sqs_client, message_body)
        self.event_type = self.get_event_type(sqs_client, message_body)
        self.queue_url = queue_url

    def __repr__(self) -> str:
        return f"SQSHandlerEvent({self.message_id}, {self.receipt_handle}, {self.file_key}, {self.event_type})"

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, SQSHandlerEvent):
            return (
                self.message_id == __o.message_id
                and self.receipt_handle == __o.receipt_handle
                and self.file_key == __o.file_key
                and self.event_type == __o.event_type
            )
        else:
            return False

    @staticmethod
    def get_file_key(sqs_client: Any, message_body: str) -> str:

        # Parse S3 Object Key from Body
        try:
            file_key = message_body.get("Records")[0].get("s3").get("object").get("key")
        except Exception:
            file_key = None

        # Check if file_key is not None
        if not file_key:
            print(message_body)
            raise ValueError("Error Parsing S3 Object Key from SQS Message Body")

        return file_key

    @staticmethod
    def get_event_type(sqs_client: Any, message_body: str) -> str:

        # Parse S3 Event Type from Body
        try:
            event_type = message_body.get("Records")[0].get("eventName")
        except Exception:
            event_type = None

        # Check if event_type is not None
        if not event_type:
            print(message_body)
            raise ValueError("Error Parsing S3 Event Type from SQS Message Body")

        # Check if it is a Object Created/Updated/Deleted Event
        if "ObjectCreated" in event_type:
            return "CREATE"
        elif "ObjectRemoved" in event_type:
            return "DELETE"
        else:
            raise ValueError("Error Parsing S3 Event Type from SQS Message Body")

    def delete_message(self, sqs_client: Any, receipt_handle: str):

        try:

            # Delete received message from queue
            response = sqs_client.delete_message(
                QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
            )

            if response.get("ResponseMetadata").get("HTTPStatusCode") == 200:
                log.info(f"Deleted message from queue ({self.queue_url})")

            else:
                log.error(f"Error deleting message from queue ({self.queue_url})")

        except Exception as e:
            log.error(f"Error deleting message from queue ({self.queue_url}): {e}")
