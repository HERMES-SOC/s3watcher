"""
Main File for the AWS File System Watcher
"""

from s3watcher.SQSQueueHandler import SQSQueueHandler
from s3watcher.SQSQueueHandlerConfig import get_config

# Main Function
def main() -> None:
    """
    Main Function
    """

    # Get the Configuration
    config = get_config()

    queue_handler = SQSQueueHandler(
        config=config,
    )

    # Start the Queue Handler
    queue_handler.start()


# Main Function
if __name__ == "__main__":
    main()
