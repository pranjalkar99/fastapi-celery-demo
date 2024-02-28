import os
import datetime
import time
from typing import List
import requests, json
import base64
from io import BytesIO
from PIL import Image
import time, logging

from db_utils import *
from aws_manage import *

logger = logging.getLogger(__name__)

from celery import Celery, group, chord, chain
import random
from celery.result import AsyncResult

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")



def save_image(base64_image, folder_id, model):
    timestamp = int(time.time())

    # Check if the folder exists, if not, create it
    if not os.path.exists(folder_id):
        os.makedirs(folder_id)

    image_data = base64.b64decode(base64_image.split(',')[1])
    image = Image.open(BytesIO(image_data))

    image_name = f'output_image_{model}_{timestamp}.jpg'
    image_path = os.path.join(folder_id, image_name)

    try:
        image.save(image_path, 'JPEG')
        print(f"Image saved successfully: {image_path}")
    except Exception as e:
        print(f"Error saving image: {str(e)}")

    return image_path 



@celery.task(name="process_image")
def process_image(folder_id, image, parent_task_id):
    # This is the classification logic...

    # container_choices = ["http://localhost:8084", "http://localhost:5001"]
    container_choices = ["http://34.138.136.100:8084","http://34.138.136.100:5001"]
    selected_container ="http://34.138.136.100:8084"# random.choice(container_choices)

    # Make a request to the selected container

    if selected_container == "http://34.138.136.100:8084":
        print("Request for Bread model...")

        endpoint_url = f"{selected_container}/predictions"
        payload = {"input": {"gamma": 0.9, "image": image, "strength": 0.05}}

        try:
            celery.current_task.update_state(state='PROGRESS', meta={'image_filename': image, 'status': 'Processing'})
            response = requests.post(endpoint_url, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Image {image} processed successfully by container {selected_container}")
                print(f"Image {image} processed successfully by container {selected_container}")

                image_path = save_image(response.json()['output'], folder_id, model="bread")

                celery.current_task.update_state(state='SUCCESS', meta={'image_filename': image, 'status': 'Success', "parent": parent_task_id})
                return {"status": "success", "image_path": image_path}
            else:
                print(f"Error processing image {image} by container {selected_container}")
                logger.error(f"Error processing image {image} by container {selected_container}")
                return False
        except Exception as e:
            print(f"Exception while processing image {image} by container {selected_container}: {str(e)}")
            celery.current_task.update_state(state='FAILURE', meta={'image_filename': image, 'status': 'Error', 'error_message': str(e)})
            return {"status": "error", "error_message": str(e)}

    # else:
    #     print("Request for Hdrnet")
    #     hdrnet_endpoint_url = f"{selected_container}/process-batch-interface"  # Adjust the endpoint accordingly
    #     hdrnet_payload = {
    #         'input[]': ('image.jpg', image),
    #         'checkpoint_dir': 'your_hdrnet_checkpoint_dir',  # DOesn't matter, hard coded for now, inisde container...
    #     }

    #     try:
    #         celery.current_task.update_state(state='PROGRESS', meta={'image_filename': image, 'status': 'Processing'})
    #         hdrnet_response = requests.post(hdrnet_endpoint_url, files=hdrnet_payload)
    #         if hdrnet_response.status_code == 200:
                
    #             print(f"Image {image} processed successfully by container {selected_container}")
    #             save_image(hdrnet_response.json()['output'], folder_id, model="hdrnet")
    #             result = AsyncResult(parent_task_id)
    #             result.backend.store_result(result.id, {"image_status": True})
    #             return True
    #         else:
    #             print(f"Error processing image {image} by container {selected_container}")
    #             return False
    #     except Exception as e:
    #         print(f"Exception while processing image {image} by container {selected_container}: {str(e)}")
    #         celery.current_task.update_state(state='FAILURE', meta={'image_filename': image, 'status': 'Error', 'error_message': str(e)})
    #         return False




@celery.task(name="create_task")
def create_task(folder_id, images: List[str], webhook_url, aws_bucket):
    print(f"Working on {folder_id}")

    parent_task_id = create_task.request.id

    signature_tasks = []
    
    for image in images:
        # Use signature for each process_image task
        task = process_image.s(folder_id, image, parent_task_id)
        signature_tasks.append(task)
        processing_delay = 15  # in seconds
        time.sleep(processing_delay)


    # Create a chord of tasks
    chord_task = chord(signature_tasks, body=images_processed.s(parent_task_id, webhook_url, aws_bucket, folder_id))

    # Apply the chord
    chord_task.apply_async()
   
    return parent_task_id


@celery.task(name="upload files")
def upload_files_completion(input_folder, aws_bucket):
    output_folder =  f"{input_folder}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
    try:
        upload_status = upload_images_to_s3(input_folder,output_folder,aws_bucket)
        if upload_status:
            return {"status":"success", "saved_to": output_folder, "bucket": aws_bucket, "s3_urls": upload_status}
    except Exception as e:
        return {"status":"failed", "msg":str(e)}


@celery.task(name="send_discord_message")
def send_discord_message(data):
    webhook_url = "https://discord.com/api/webhooks/1201505585301049345/UuT5TLTlR8TTVGM9Pd1IgDm5g76roSYKAjkhJJwiymJnDJIgmhQ80rjDiG9rxhYxdscx"

    # Extract relevant information from the response
    status_code = data.get('status_code', 'N/A')

    message = f"""Task {str(data['parent_task_id'])} completed:\n Status Code: 204 \n Successfully processed {str(data['successful_count'])} images.\n 
              Failed to process {str(data['failed_count'])} images.\n """

    payload = {
        "content": message
    }

    response = requests.post(webhook_url, json=payload)

    if response.status_code == 200:
        print("Discord message sent successfully.")
    else:
        print(f"Error sending Discord message. Status code: {response.status_code}")

    return {"webhook_status_code": response.status_code}


@celery.task(name="send_webhook_message")
def send_webhook_message(data, webhook_url):
    message = {
        "content": f"Task {str(data['parent_task_id'])} completed:",
        "embeds": [
            {
                "title": "Task Details",
                "fields": [
                    {"name": "Status Code", "value": "204", "inline": True},
                    {"name": "Successful Count", "value": str(data['successful_count']), "inline": True},
                    {"name": "Failed Count", "value": str(data['failed_count']), "inline": True}
                ]
            }
        ]
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(webhook_url, data=json.dumps(message), headers=headers)
    if response.status_code == 200:
        print("Webhook message sent successfully.")
    else:
        print(f"Error sending Webhook message. Status code: {response.status_code}")
    return {"webhook_status_code": response.status_code}
    




@celery.task(name="finalize_task")
def finalize_task(final_result, folder_id):
    # Check if all tasks were successful before removing the directory
    if final_result.get('status') == 'success':
        os.removedirs(folder_id)

    logging.info(f"Final Result Data: {str(final_result)}")

    return final_result

@celery.task(name="handle_final_result")
def handle_final_result(successful_results, parent_task_id, webhook_url, aws_bucket, folder_id):
    # Assuming successful_results is a list of successful results
    final_result = {
        "successful_count": len(successful_results),
        "failed_count": 0,  # Assuming no failures in this step
        "all_image_paths": [result.get("image_path") for result in successful_results],
        "parent_task_id": parent_task_id,
        "bucket": aws_bucket,
    }

    # Create a chord with the tasks: upload_files_completion -> update_final_result
    # -> send_discord_message -> send_webhook_message -> finalize_task
    cleanup_chain = chain(
        upload_files_completion.s(folder_id, aws_bucket),
        update_final_result.s(final_result),
        send_discord_message.s(),
        send_webhook_message.s(webhook_url),
        finalize_task.s(folder_id)
    )

    # Apply async to the entire cleanup_chord
    cleanup_chain.apply_async()

    return final_result


@celery.task(name="update_final_result")
def update_final_result(upload_result, final_result):
    final_result["saved_to"] = upload_result.get('saved_to')
    final_result["s3_urls"] = upload_result.get('s3_urls')
    return final_result


@celery.task(name="process_task_completed")
def images_processed(results, parent_task_id, webhook_url, aws_bucket, folder_id):
    successful_count = 0
    failed_count = 0
    all_image_paths = []

    # Extract successful and failed results
    successful_results = []
    failed_results = []

    for result in results:
        image_status = result.get("image_status")
        if image_status == "success":
            successful_count += 1
            image_path = result.get("image_path")
            if image_path:
                all_image_paths.append(image_path)
            successful_results.append(result)
        elif image_status == "error":
            failed_count += 1
            failed_results.append(result)

    logging.info(f"Successfully processed {successful_count} images.")
    logging.info(f"Failed to process {failed_count} images.")

    # Send the successful results to the next task
    async_result = handle_final_result.s(
        successful_results,
        parent_task_id,
        webhook_url,
        aws_bucket,
        folder_id
    ).delay()

    # Return a placeholder response if needed
    return {"status": "processing images completed,", "message": "Task is still in progress"}