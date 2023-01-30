import json


class SQSHandlerEvent():

    def __init__(self, sqs_message: dict) -> None:
        """
        Class Constructor
        """
        self.message_id = sqs_message.get("MessageId")
        self.receipt_handle = sqs_message.get("ReceiptHandle")
        message_body = json.loads(sqs_message.get("Body"))
        self.file_key = self.get_file_key(message_body)
        self.event_type = self.get_event_type(message_body)
        # Check if class attributes are not None
        if not self.message_id:
            raise ValueError("Error Parsing SQS Message ID")
        if not self.receipt_handle:
            raise ValueError("Error Parsing SQS Receipt Handle")
        if not self.file_key:
            raise ValueError("Error Parsing S3 Object Key from SQS Message Body")
        if not self.event_type:
            raise ValueError("Error Parsing S3 Event Type from SQS Message Body")
            


    def __repr__(self) -> str:
        return f"SQSHandlerEvent({self.message_id}, {self.receipt_handle}, {self.file_key}, {self.event_type})"

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, SQSHandlerEvent):
            return self.message_id == __o.message_id and self.receipt_handle == __o.receipt_handle and self.file_key == __o.file_key and self.event_type == __o.event_type
        else:
            return False

    @staticmethod
    def get_file_key(message_body: str) -> str:
        
        # Parse S3 Object Key from Body
        file_key = message_body.get("Records")[0].get("s3").get("object").get("key")

        # Check if file_key is not None
        if not file_key:
            raise ValueError("Error Parsing S3 Object Key from SQS Message Body")

        return file_key
    
    @staticmethod
    def get_event_type(message_body: str) -> str:
        
        # Parse S3 Event Type from Body
        event_type = message_body.get("Records")[0].get("eventName")

        # Check if event_type is not None
        if not event_type:
            raise ValueError("Error Parsing S3 Event Type from SQS Message Body")
        
        # Check if it is a Object Created/Updated/Deleted Event
        if 'ObjectCreated' in event_type:
            return 'CREATE'
        elif 'ObjectRemoved' in event_type:
            return 'DELETE'
        else:
            raise ValueError("Error Parsing S3 Event Type from SQS Message Body")
