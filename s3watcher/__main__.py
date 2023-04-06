"""
AWS File System Watcher Main File
"""

from s3watcher.SQSQueueHandler import SQSQueueHandler
from s3watcher.SQSQueueHandlerConfig import get_config


def main() -> None:
    """
    Main function that initializes and starts the SQS Queue Handler.

    Retrieves the necessary configuration for the SQS Queue Handler and
    starts the queue handler to process incoming messages.
    """
    # Retrieve the configuration
    config = get_config()

    # Initialize the SQS Queue Handler with the given configuration
    queue_handler = SQSQueueHandler(config=config)

    # Start the Queue Handler to process incoming messages
    queue_handler.start()


if __name__ == "__main__":
    main()
