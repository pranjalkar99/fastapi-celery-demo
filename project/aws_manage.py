import requests
import os, time
from PIL import Image
import base64
from io import BytesIO
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

import logging
logging.basicConfig(filename='logs/aws_manage.log', format='%(asctime)s %(message)s',
                    filemode='a')


logger = logging.getLogger()

load_dotenv()
ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

def upload_to_s3(local_filename, s3_bucket, s3_folder):
    ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
    SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    
    s3 = boto3.client('s3', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

    try:
        s3.upload_file(local_filename, s3_bucket, f"{s3_folder}/{os.path.basename(local_filename)}")
        logger.info('s3 upload success')
        s3_url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_folder}/{os.path.basename(local_filename)}"
        logger.info(f"Uploaded {local_filename} to {s3_url}")
        return s3_url
    except Exception as e:
        error_message = f"Failed to upload to S3: {e}"
        logger.error(error_message)
        raise e 

def upload_images_to_s3(input_folder, output_folder, s3_bucket):
    s3_urls = []

    for filename in os.listdir(input_folder):
        local_filepath = os.path.join(input_folder, filename)
        try:
            s3_url = upload_to_s3(local_filepath, s3_bucket, output_folder)
            if s3_url:
                s3_urls.append(s3_url)
            else:
                error_message = f"Failed to upload {local_filepath} to S3"
                logger.error(error_message)
                raise Exception(error_message)
        except Exception as e:
            logger.error(f"Error during S3 upload for {local_filepath}: {e}")
            raise e

    logger.info(f"All files in {input_folder} successfully uploaded to S3. URLs: {s3_urls}")
    return s3_urls

    
def save_image(processed_image, folder_id, model, aws_bucket, s3_folder_name):
    try:
        timestamp = int(time.time())

        # Check if the folder exists, if not, create it
        current_directory = os.getcwd()
        folder_path = os.path.join(current_directory, folder_id)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        image_data = base64.b64decode(processed_image.split(',')[1])
        image = Image.open(BytesIO(image_data))

        image_name = f'output_image_{model}_{timestamp}.jpg'
        image_path = os.path.join(folder_path, image_name)

        image.save(image_path, 'JPEG')
        logger.info(f"Image saved successfully: {image_path}")

        # Processing success, now going for upload...
        s3_url = upload_to_s3(image_path, aws_bucket, s3_folder_name)

        return image_path, s3_url
    except Exception as e:
        logger.error(f"Error saving/uploading image: {str(e)}")
        
        return None, None


if __name__ =="__main__":
    upload_images_to_s3('him2pk','pk_out_debug_2','ovvy-ml-output')