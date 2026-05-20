from fastapi import FastAPI, Request
from google.cloud import tasks_v2
from google.cloud import storage
from google import genai
from google.genai import types
import os
import json
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment Variables
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project-id")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "your-gcs-bucket-name")
QUEUE = os.environ.get("QUEUE_NAME", "your-queue-name")
LOCATION = os.environ.get("LOCATION", "us-central1")

def save_result_to_gcs(bucket_name: str, request_id: str, content: str):
    """Simply saves the final LLM response to GCS."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"results/{request_id}/answer.json")
    blob.upload_from_string(content, content_type="application/json")


@app.post("/ask")
# async def trigger_analysis(request_id: str, question: str):
async def trigger_analysis(request: Request, request_id: str, question: str):
    """
    Frontend endpoint. 
    Immediately delegates the workload to Cloud Tasks to control the rate limit.
    """
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(PROJECT_ID, LOCATION, QUEUE)
    service_url = str(request.base_url).rstrip("/")
    if service_url.startswith("http://"):
        service_url = service_url.replace("http://", "https://")

    task_payload = {
        "request_id": request_id,
        "question": question
    }

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{service_url}/process-worker",
            "headers": {"Content-type": "application/json"},
            "body": json.dumps(task_payload).encode(),
        }
    }
    
    # Send to the background queue (GCP enforces the max-concurrent-dispatches here)
    client.create_task(request={"parent": parent, "task": task})

    return {
        "status": "queued",
        "request_id": request_id,
        "message": "Request queued successfully."
    }


@app.post("/process-worker")
async def process_worker(request: Request):
    """
    Background worker endpoint called by Google Cloud Tasks.
    Executes the Gemini API call and saves the result.
    """
    data = await request.json()
    request_id = data["request_id"]
    question = data["question"]
    
    try:
        logger.info(f"Worker started for {request_id}")
        
        # 1. Initialize Gemini Client 
        client = genai.Client(
            
            vertexai=True,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    initial_delay=1.0,
                    attempts=5,
                    http_status_codes=[429],
                ),
                timeout=120 * 1000,
            ),
        
        )
        
        # 2. Call Gemini Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Or whichever flash version you use
            contents=question
        )
        
        # 3. Save result to GCS
        result_data = json.dumps({
            "request_id": request_id,
            "question": question,
            "answer": response.text
        })
        
        save_result_to_gcs(BUCKET_NAME, request_id, result_data)
        logger.info(f"Worker finished successfully for {request_id}")

    except Exception as e:
        logger.error(f"Error processing request {request_id}: {e}")
        # Raising the error allows Cloud Tasks to automatically retry the failed request 
        # based on your queue's max-attempts configuration
        raise e 
        
    return {"status": "success"}