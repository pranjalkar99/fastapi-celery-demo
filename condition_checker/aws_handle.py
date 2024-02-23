import os
import requests
from flask import request,jsonify
from dotenv import load_dotenv
import boto3
from boto3.s3.transfer import S3Transfer

import logging
logging.basicConfig(format="[%(process)d] %(levelname)s %(filename)s:%(lineno)s | %(message)s")

load_dotenv()


def download_from_s3(bucket_name, folder_name, destination_directory):
    s3 = boto3.client("s3")
    transfer = S3Transfer(s3)

    response = s3.list_objects(Bucket=bucket_name, Prefix=folder_name)

    for obj in response.get('Contents', []):
        file_name = obj['Key']
        local_file_path = os.path.join(destination_directory, os.path.basename(file_name))

        try:
            transfer.download_file(bucket_name, file_name, local_file_path)
            print("Downloaded: {}".format(file_name))
        except Exception as e:
            print("Error downloading file {}: {}".format(file_name, e))

    return os.listdir(destination_directory)


def download_files(folder_name):
    try:
        # Specify the directory path
        directory_path = os.path.join(os.getcwd(), 'downloads')

        # Define the permissions (in octal representation)
        permissions = 0o755

        try:
            # Create the directory with the specified permissions
            os.makedirs(directory_path, mode=permissions)
            print("Directory '{}' created with permissions {}".format(directory_path, oct(permissions)))
        except OSError as e:
            if e.errno == os.errno.EEXIST:
                print("Directory '{}' already exists.".format(directory_path))
            else:
                print("Error creating directory '{}': {}".format(directory_path, e))

        # Load environment variables from .env file
        

        # Specify your S3 bucket name
        bucket_name = 'oovy-ml-input-bucket'

        # Download files from S3
        downloaded_files = download_from_s3(bucket_name, folder_name, directory_path)

        logging.info("Downloaded files: {} successfully".format(downloaded_files))

        # Respond with the list of downloaded files
        response_data = {
            'message': 'Download successful',
            'downloaded_files': downloaded_files
        }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
