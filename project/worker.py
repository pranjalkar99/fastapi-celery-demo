import os, shutil
import datetime
import traceback
import time
from typing import List
import requests, json
import base64
from io import BytesIO
from PIL import Image
import time, logging

from db_utils import *
from aws_manage import *

logging.basicConfig(filename='logs/worker.log', format='%(asctime)s %(message)s',
                    filemode='w')
logger = logging.getLogger(__name__)

from celery import Celery, group, chord, chain
import random
from celery.result import AsyncResult

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")


@celery.task(name="save_and_upload")
def save_and_upload(processed_image, folder_id, aws_bucket, s3_folder_name, parent_task_id):
    if processed_image:
        # Use processed_image to save and upload
        image_path, s3_url = save_image(processed_image, folder_id, model="bread", aws_bucket=aws_bucket,
                                       s3_folder_name=s3_folder_name)
        celery.current_task.update_state(state='PROGRESS',
                                             meta={'image_filename': image_path, 'status': 'saving_and_uploading'})
        logger.info("completed save_image...")
        # Check if save_image is successful
        if s3_url:
            celery.current_task.update_state(state='SUCCESS',
                                                 meta={'image_filename': image_path, 'status': 'success',
                                                       "parent": parent_task_id, "s3_urls": s3_url})
            return {"status": "success", "image_path": image_path, "s3_urls": s3_url}
        else:
            celery.current_task.update_state(state='FAILURE',
                                                 meta={'image_filename': image_path, 'status': 'fail',
                                                       "parent": parent_task_id,
                                                       "reason": "Image Processed, but Failing to Upload ..."})
            return {"status": "fail", "image_path": image_path}
    else:
        celery.current_task.update_state(state='FAILURE',
                                                 meta={ 'status': 'fail',
                                                       "parent": parent_task_id,
                                                       "reason": "Image  Not Processed,hence not saving and uploading ..."})
        return {"status": "fail"}

@celery.task(name="process_image")
def process_image(folder_id, image, parent_task_id, aws_bucket, s3_folder_name):
    # This is the classification logic...

    container_choices = ["http://34.138.136.100:8084", "http://34.138.136.100:5001"]
    selected_container = "http://34.138.136.100:8084"  # random.choice(container_choices)

    # Make a request to the selected container

    if selected_container == "http://34.138.136.100:8084":
        print("Request for Bread model...")

        endpoint_url = f"{selected_container}/predictions"
        payload = {"input": {"gamma": 0.9, "image": image, "strength": 0.05}}

        try:
            celery.current_task.update_state(state='PROGRESS', meta={'image_filename': image, 'status': 'Processing'})
            response = requests.post(endpoint_url, json=payload)

            if response.status_code == 200:
                logger.info(f"processing here..Image {image} processed successfully by container {selected_container}")
                print(f"Image {image} processed successfully by container {selected_container} I got response code 200..")

                # Return the processed image data
                logger.info('Simply returning the code..')
                return response.json()['output']
            else:
                print(f"Error processing image {image} by container {selected_container}")
                logger.error(f"Error processing image {image} by container {selected_container}")
                # Return None if processing fails
                return None
        except Exception as e:
            print(f"Exception while processing image {image} by container {selected_container}: {str(e)}")
            # Return None if an exception occurs during processing
            return None
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

    s3_folder_name =  f"{folder_id}-{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
    
    for image in images:
        # Use signature for each process_image task
        task = process_image.s(folder_id, image, parent_task_id, aws_bucket, s3_folder_name)
        chain_task = chain(task, save_and_upload.s(folder_id, aws_bucket, s3_folder_name, parent_task_id))
        signature_tasks.append(chain_task)
        processing_delay = 15  # in seconds
        time.sleep(processing_delay)


    # Create a chord of tasks
    chord_task = chord(signature_tasks, body=images_processed.s(parent_task_id, webhook_url, folder_id, aws_bucket))

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
        return {"status":"fail", "msg":str(e)}


@celery.task(name="send_discord_message")
def send_discord_message(data):
    webhook_url = "https://discord.com/api/webhooks/1201505585301049345/UuT5TLTlR8TTVGM9Pd1IgDm5g76roSYKAjkhJJwiymJnDJIgmhQ80rjDiG9rxhYxdscx"

    # Extract relevant information from the response
    s3_urls = data.get('s3_urls',None)
    if s3_urls is not None:
        status_code = 200
    else:
        status_code = 400

    message = f"""Task {str(data['parent_task_id'])} completed:\n Status Code: {status_code}\n Successfully processed {str(data['successful_count'])} images.\n 
              Failed to process {str(data['failed_count'])} images.\n  
               \n THE S3 URLS list is : {str(data['s3_urls'])} """

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

    s3_urls = data.get('s3_urls',None)
    if s3_urls is not None:
        status_code = 200
    else:
        status_code = 400

    message = {
        "content": f"Task {str(data['parent_task_id'])} completed:",
        "embeds": [
            {
                "title": "Task Details",
                "fields": [
                    {"name": "Status Code", "value": status_code, "inline": True},
                    {"name": "Successful Count", "value": str(data['successful_count']), "inline": True},
                    {"name": "Failed Count", "value": str(data['failed_count']), "inline": True},
                    {"name": "S3 Upload URLS", "value": s3_urls, "inline": True},
                    {"name": "Batch Status", "value": data['batch_status'], "inline": True},
                    {"name": "Folder ID", "value": data['folder_id'], "inline": True},
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
    if final_result.get('batch_status') == 'success':
        # Use shutil.rmtree to remove the directory and its contents
        shutil.rmtree(folder_id)

    logger.info(f"Final Result Data: {str(final_result)}")

    return final_result

@celery.task(name="handle_final_result")
def handle_final_result(successful_results,failed_results, s3_urls, parent_task_id, webhook_url, folder_id, aws_bucket):
    

    if len(successful_results) > len(failed_results):
        batch_status = "success"
    else:
        batch_status = "fail"
    final_result = {
        "successful_count": len(successful_results),
        "failed_count": len(failed_results),  
        "all_image_paths": [result.get("image_path") for result in successful_results],
        "parent_task_id": parent_task_id,
        "bucket": aws_bucket,
        "s3_urls": s3_urls,
        "batch_status": batch_status,
        "folder_id": folder_id
    }

    # # Do these two tasks synchronously...

    # upload_result = upload_files_completion(folder_id, aws_bucket)
    # final_result = update_final_result(upload_result, final_result)

    send_discord_message.delay(final_result)
    send_webhook_message.delay(final_result, webhook_url)
    finalize_task.delay(final_result, folder_id)


    return final_result


@celery.task(name="update_final_result")
def update_final_result(upload_result, final_result):
    # Wait until upload_result is ready
    
    while upload_result is None :
        time.sleep(1)  

    # Check if upload_result is successful and has the expected structure
    if "status" in upload_result and upload_result.get('status') == "success":
        final_result["saved_to"] = upload_result.get('saved_to')
        final_result["s3_urls"] = upload_result.get('s3_urls')
    else:
        raise Exception("s3 urls not Received")
        # Handle the case where upload_result is not successful or has unexpected structure
        final_result["saved_to"] = "unknown"
        final_result["s3_urls"] = []

    return final_result


@celery.task(name="process_task_completed")
def images_processed(results, parent_task_id, webhook_url, folder_id, aws_bucket):
    successful_count = 0
    failed_count = 0
    error_count=0
    all_image_paths = []

    # Extract successful and failed results
    successful_results = []
    failed_results = []
    s3_urls = []

    for result in results:
        image_status = result.get("status")
        if image_status == "success":
            successful_count += 1
            s3_urls.append(result.get("s3_urls"))
            image_path = result.get("image_path")
            if image_path:
                all_image_paths.append(image_path)
            successful_results.append(result)
        elif image_status == "fail":
            failed_count += 1
            failed_results.append(result)
        
        elif image_status == "error":
            error_count += 1

    logger.info(f"Successfully processed {successful_count} images.")
    logger.info(f"Failed to process {failed_count} images.")
    logger.info(f"Error count: {error_count}")

    # Send the successful results to the next task
    async_result = handle_final_result.s(
        successful_results,
        failed_results,
        s3_urls,
        parent_task_id,
        webhook_url,
        folder_id,
        aws_bucket
    ).delay()

    # Return a placeholder response if needed
    return {"status": "processing images completed,", "message": "Task is still in progress"}