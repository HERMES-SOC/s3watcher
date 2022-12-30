"""
Main File for the AWS File System Watcher
"""

from SQSQueueHandler import SQSQueueHandler
from SQSQueueHandlerConfig import get_config

# Main Function
def main() -> None:
    """
    Main Function
    """

    # Get the Configuration
    config = get_config()

    queue_handler = SQSQueueHandler(
        queue_url=config.queue_url,
        bucket_name=config.bucket_name,
        download_path=config.path,
        timestream_db=config.timestream_db,
        timestream_table=config.timestream_table,
        profile=config.profile,
        concurrency_limit=config.concurrency_limit,
        allow_delete=config.allow_delete,
    )

    # Start the Queue Handler
    queue_handler.start()



# Main Function
if __name__ == "__main__":
    main()
