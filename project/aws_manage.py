import requests
import os
from dotenv import load_dotenv

load_dotenv()

def download_s3_image(s3_url, local_filename):
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    # Generate the authorization header
    auth_header = {'Authorization': f'AWS {access_key}:{secret_key}'}

    # Download the image
    response = requests.get(s3_url, headers=auth_header, stream=True)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Save the image locally
        with open(local_filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=128):
                file.write(chunk)
        print(f"Image downloaded successfully as {local_filename}")
    else:
        print(f"Failed to download image. Status code: {response.status_code}")

# Example usage
s3_url = 'your_private_s3_url'
local_filename = 'downloaded_image.jpg'
download_s3_image(s3_url, local_filename)
