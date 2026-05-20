# llm-traffic-smoother
A serverless queuing architecture using FastAPI and Google Cloud Tasks to smooth spiky traffic and maximize LLM Provisioned Throughput.

# LLM Traffic Smoother

A serverless queuing architecture built with FastAPI, Google Cloud Run, and Cloud Tasks. 

This application acts as a "shock absorber" for bursty LLM traffic. It instantly queues heavy, asynchronous user requests (like complex agentic workflows or document analysis) and drip-feeds them to the Gemini API at a strictly controlled rate. This prevents `429 Too Many Requests` errors and maximizes your Provisioned Throughput (PT) utilization.

## 🚀 Deployment

This application uses a self-resolving "loopback" pattern, making it entirely CI/CD friendly. You can deploy it in just a few steps.

### 1. Create the Rate-Limiting Queue
Create the Cloud Tasks queue and set your strict Requests-Per-Second (RPS) limit to match your PT quota:
```bash
gcloud tasks queues create gemini-request-queue \
  --location=us-central1 \
  --max-dispatches-per-second=15 \
  --max-attempts=3
```

### 2. Deploy to Cloud Run:
Deploy the FastAPI application. Because the code dynamically grabs its own URL at runtime, you only need to run this once:
```bash
gcloud run deploy gemini-queue-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="PROJECT_ID=your_project_id,BUCKET_NAME=your_gcs_bucket,QUEUE_NAME=gemini-request-queue"
```
### 3. Grant IAM Permissions
Cloud Run uses the default compute service account. You must give it permission to add jobs to Cloud Tasks:
```bash
# Replace with your actual Google Cloud Project Number
gcloud projects add-iam-policy-binding your_project_id \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"
```
### 4. Grant IAM Permissions
Usage (Calling the API)
Once deployed, you can trigger a background job by calling the /ask endpoint. The API will immediately return a 202 Queued receipt, while the background worker processes the LLM prompt and saves the result to Google Cloud Storage.

Note: Ensure your query parameters are URL-encoded (e.g., %20 for spaces).
```bash
curl -X POST "https://YOUR_CLOUD_RUN_URL/ask?request_id=test-001&question=What%20is%20the%20capital%20of%20France%3F" \
     -H "accept: application/json"
```

Expected Response (Instant):
```bash
{
  "status": "queued",
  "request_id": "test-001",
  "message": "Request queued successfully."
}
```
The final LLM answer will be saved asynchronously to your specified GCS bucket at:
```bash gs://your_gcs_bucket/results/test-001/answer.json ```


     
