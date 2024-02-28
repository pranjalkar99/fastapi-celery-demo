import requests
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
load_dotenv()




def upload_to_s3(local_filename, s3_bucket, s3_folder):
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    s3 = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    try:
        s3.upload_file(local_filename, s3_bucket, f"{s3_folder}/{os.path.basename(local_filename)}")
        s3_url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_folder}/{os.path.basename(local_filename)}"
        print(f"Uploaded {local_filename} to {s3_url}")
        return s3_url
    except NoCredentialsError:
        print("Credentials not available")
        return None

def upload_images_to_s3(input_folder, output_folder, s3_bucket):
    s3_urls = []

    for filename in os.listdir(input_folder):
        local_filepath = os.path.join(input_folder, filename)
        s3_url = upload_to_s3(local_filepath, s3_bucket, output_folder)
        if s3_url:
            s3_urls.append(s3_url)

    return s3_urls

