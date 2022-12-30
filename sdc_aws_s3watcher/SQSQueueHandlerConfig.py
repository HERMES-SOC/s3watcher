"""
File System Handler Configuration Module
"""

from argparse import ArgumentParser
import os
from sdc_aws_s3watcher import log


class SQSQueueHandlerConfig:
    """
    Dataclass to hold the FileSystemHandler Configuration
    """

    def __init__(
        self,
        bucket_name: str,
        queue_url: str,
        path: str = os.getcwd(),
        timestream_db: str = "",
        timestream_table: str = "",
        profile: str = "",
        concurrency_limit: int = 20,
        allow_delete: bool = False,
    ) -> None:
        """
        Class Constructor
        """

        self.path = path
        self.bucket_name = bucket_name
        self.queue_url = queue_url
        self.timestream_db = timestream_db
        self.timestream_table = timestream_table
        self.profile = profile
        self.concurrency_limit = concurrency_limit
        self.allow_delete = allow_delete


def create_argparse() -> ArgumentParser:
    """
    Function to initialize the Argument Parser and with the arguments to be parsed and return the Arguments Parser

    :return: Argument Parser
    :rtype: argparse.ArgumentParser
    """
    # Initialize Argument Parser
    parser = ArgumentParser()

    # Add Argument to parse directory path to be watched
    parser.add_argument("-d", "--directory", help="Directory Path to Download Files to")

    # Add Argument to parse S3 Bucket Name to upload files to
    parser.add_argument("-b", "--bucket_name", help="User name")

    # Add Argument to parse SQS Queue URL
    parser.add_argument("-q", "--queue_url", help="Queue URL")

    # Add Argument to parse Timestream Database Name
    parser.add_argument("-t", "--timestream_db", help="Timestream Database Name")

    # Add Argument to parse Timestream Table Name
    parser.add_argument("-tt", "--timestream_table", help="Timestream Table Name")

    # Add Argument to profile to use when connecting to AWS
    parser.add_argument(
        "-p", "--profile", help="AWS Profile to use when connecting to AWS"
    )

    # Add Argument to parse the concurrency limit
    parser.add_argument(
        "-c",
        "--concurrency_limit_limit",
        type=int,
        help="Concurrency Limit for the File System Watcher",
    )

    # Add Argument to parse the allow delete flag
    parser.add_argument(
        "-a",
        "--allow_delete",
        action="store_true",
        help="Allow Delete Flag for the File System Watcher",
    )

    # Return the Argument Parser
    return parser


def get_args(args: ArgumentParser) -> dict:
    """
    Function to get the parsed arguments and return them as a dictionary

    :param args: Arguments Parser
    :type args: argparse.ArgumentParser
    :return: Dictionary of arguments
    :rtype: dict
    """
    # Parse the arguments
    args = args.parse_args()

    # Initialize the arguments dictionary
    args_dict = {}

    # Add the arguments to the dictionary
    args_dict["SDC_AWS_WATCH_PATH"] = args.directory
    args_dict["SDC_AWS_S3_BUCKET"] = args.bucket_name
    args_dict["SDC_AWS_SQS_QUEUE_URL"] = args.queue_url
    args_dict["SDC_AWS_TIMESTREAM_DB"] = args.timestream_db
    args_dict["SDC_AWS_TIMESTREAM_TABLE"] = args.timestream_table
    args_dict["SDC_AWS_PROFILE"] = args.profile
    args_dict["SDC_AWS_CONCURRENCY_LIMIT"] = args.concurrency_limit_limit
    args_dict["SDC_AWS_ALLOW_DELETE"] = args.allow_delete

    # Return the arguments dictionary
    return args_dict


def get_envvars() -> dict:
    """
    Function to get the environment variables and return them as a dictionary

    :return: Dictionary of environment variables
    :rtype: dict
    """
    # Initialize the environment variables dictionary
    env_vars = {}

    # Get the environment variables
    variables = [vars for vars in os.environ if "SDC_AWS" in vars]
    for var in variables:
        env_vars[var] = os.environ[var]

    # Return the environment variables dictionary
    return env_vars


def validate_config_dict(config: dict) -> bool:
    """
    Function to validate the configuration and return True if the configuration is valid, False otherwise

    :param args: Arguments dictionary
    :type args: dict
    :return: True if the arguments dictionary is valid, False otherwise
    :rtype: bool
    """

    # Check if the directory path and bucket name are provided
    if config.get("SDC_") and config.get("SDC_AWS_S3_BUCKET"):
        return True
    else:
        return False


def get_config() -> SQSQueueHandlerConfig:
    """
    Function to generate the SQSQueueHandlerConfig object from the arguments and environment variables. If the arguments are valid, the SQSQueueHandlerConfig object is generated from the arguments. If the arguments are not valid, the SQSQueueHandlerConfig object is generated from the environment variables. If both are supplied, the arguments take precedence. If neither are supplied or are invalid, the program exits.

    :return: SQSQueueHandlerConfig object
    :rtype: SQSQueueHandlerConfig
    """

    # Get the arguments and environment variables
    args = get_args(create_argparse())
    env_vars = get_envvars()

    if validate_config_dict(args):
        config = SQSQueueHandlerConfig(
            path=args.get("SDC_AWS_WATCH_PATH"),
            bucket_name=args.get("SDC_AWS_S3_BUCKET"),
            queue_url=args.get("SDC_AWS_SQS_QUEUE_URL"),
            timestream_db=args.get("SDC_AWS_TIMESTREAM_DB"),
            timestream_table=args.get("SDC_AWS_TIMESTREAM_TABLE"),
            profile=args.get("SDC_AWS_PROFILE"),
            concurrency_limit=args.get("SDC_AWS_CONCURRENCY_LIMIT"),
            allow_delete=args.get("SDC_AWS_ALLOW_DELETE"),
        )

    # Check if the environment variables are valid
    elif validate_config_dict(env_vars):
        config = SQSQueueHandlerConfig(
            path=env_vars.get("SDC_AWS_WATCH_PATH"),
            bucket_name=env_vars.get("SDC_AWS_S3_BUCKET"),
            queue_url=env_vars.get("SDC_AWS_SQS_QUEUE_URL"),
            timestream_db=env_vars.get("SDC_AWS_TIMESTREAM_DB"),
            timestream_table=env_vars.get("SDC_AWS_TIMESTREAM_TABLE"),
            profile=env_vars.get("SDC_AWS_PROFILE"),
            concurrency_limit=env_vars.get("SDC_AWS_CONCURRENCY_LIMIT"),
            allow_delete=env_vars.get("SDC_AWS_ALLOW_DELETE"),
        )
    # If neither are valid, exit the program
    else:
        log.error(
            "Invalid configuration, please provide a directory path and S3 bucket name"
        )
        exit(1)

    # Return the SQSQueueHandlerConfig object
    return config
