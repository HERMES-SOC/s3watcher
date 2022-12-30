"""
Utility functions for sdc_aws_fswatcher.
"""

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create log file handler
file_handler = logging.FileHandler("sdc_aws_fswatcher.log")
file_handler.setLevel(logging.INFO)

# Log to file and console

# Create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the handlers to the logger
log.addHandler(file_handler)
