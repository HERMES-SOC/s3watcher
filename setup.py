from setuptools import setup, find_packages


setup(
    name="sdc_aws_s3watcher",
    version="0.1.0",
    description="S3 Watcher",
    author="Damian Barrous-Dume",
    packages=["sdc_aws_s3watcher"],
    include_package_data=True,
    install_requires=[
        "boto3",
        "pyyaml",
    ],

)
