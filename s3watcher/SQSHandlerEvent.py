import json
from typing import Any
from sdc_aws_utils.logging import log


class SQSHandlerEvent:
    def __init__(self, sqs_client: Any, sqs_message: dict, queue_url: str) -> None:
        """
        Initialize an SQSHandlerEvent instance.
        """
        self.message_id = sqs_message.get("MessageId")
        self.receipt_handle = sqs_message.get("ReceiptHandle")
        message_body = json.loads(sqs_message.get("Body"))
        self.queue_url = queue_url
        self.file_key = self.get_file_key(sqs_client, message_body)
        self.event_type = self.get_event_type(sqs_client, message_body)

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

    def get_file_key(self, sqs_client: Any, message_body: str) -> str:
        """
        Retrieve the S3 Object Key from the message body.
        """
        # Parse S3 Object Key from Body
        try:
            file_key = message_body.get("Records")[0].get("s3").get("object").get("key")
        except Exception:
            file_key = None

        # Check if file_key is not None
        if not file_key:
            self.delete_message(sqs_client)
            raise ValueError(
                "Error Parsing S3 Object Key from SQS Message Body - Removed Event"
            )

        return file_key

    def get_event_type(self, sqs_client: Any, message_body: str) -> str:
        """
        Retrieve the S3 Event Type from the message body.
        """
        # Parse S3 Event Type from Body
        try:
            event_type = message_body.get("Records")[0].get("eventName")
        except Exception:
            event_type = None

        # Check if event_type is not None
        if not event_type:
            self.delete_message(sqs_client)
            raise ValueError(
                "Error Parsing S3 Event Type from SQS Message Body - Removed Event"
            )

        # Check if it is an Object Created/Updated/Deleted Event
        if "ObjectCreated" in event_type:
            return "CREATE"
        elif "ObjectRemoved" in event_type:
            return "DELETE"
        else:
            self.delete_message(sqs_client)
            raise ValueError(
                "Error Parsing S3 Event Type from SQS Message Body - Removed Event"
            )

    def delete_message(self, sqs_client: Any):
        """
        Delete the received message from the queue.
        """
        try:
            # Delete received message from queue
            response = sqs_client.delete_message(
                QueueUrl=self.queue_url, ReceiptHandle=self.receipt_handle
            )

            if response.get("ResponseMetadata").get("HTTPStatusCode") == 200:
                log.info(f"Deleted message from queue ({self.queue_url})")

            else:
                log.error(f"Error deleting message from queue ({self.queue_url})")

        except Exception as e:
            log.error(f"Error deleting message from queue ({self.queue_url}): {e}")
