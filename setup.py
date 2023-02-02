from setuptools import setup


setup(
    name="s3watcher",
    version="0.1.0",
    description="S3 Watcher",
    author="Damian Barrous-Dume",
    packages=["s3watcher"],
    include_package_data=True,
    install_requires=["boto3", "pyyaml", "polling"],
    entry_points={
        "console_scripts": [
            "s3watcher = s3watcher.s3watcher:main",
        ]
    },
)
