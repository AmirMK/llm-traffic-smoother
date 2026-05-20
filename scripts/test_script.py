import requests
import urllib.parse

url_base = "https://YOUR_CLOUD_RUN_URL/ask"

with open("questions.txt", "r") as file:
    for line in file:
        # Skip empty lines
        if not line.strip():
            continue
            
        req_id, question = line.strip().split("|")
        
        # Safely encode the question
        encoded_q = urllib.parse.quote(question)
        url = f"{url_base}?request_id={req_id}&question={encoded_q}"
        
        # Send the POST request
        response = requests.post(url, headers={"accept": "application/json"})
        
        print(f"Sent {req_id}: {response.text}"