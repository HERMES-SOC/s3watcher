"""
Utility functions for s3watcher.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Mute boto3 logging
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)

# Create log file handler
file_handler = logging.FileHandler("s3watcher.log")
file_handler.setLevel(logging.INFO)

# Log to file and console

# Create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the handlers to the logger
log.addHandler(file_handler)
