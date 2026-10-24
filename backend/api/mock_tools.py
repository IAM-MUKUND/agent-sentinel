from fastapi import APIRouter, HTTPException, status
from models.schemas import EmailPayload, CustomerPayload, RefundPayload, ServerConfigPayload, ApprovalPayload

router = APIRouter()

@router.post("/send_email")
async def send_email(payload: EmailPayload):
    # Mock sending email
    return {"status": "success", "message": f"Email queued for {payload.to}"}

@router.delete("/delete_customer/{customer_id}")
async def delete_customer(customer_id: str):
    # Mock deletion
    return {"status": "success", "message": f"Customer {customer_id} deleted"}

@router.post("/customer")
async def add_customer(payload: CustomerPayload):
    # Mock adding customer
    return {"status": "success", "customer_id": "cust_12345", "message": "Customer created"}

@router.get("/customer/{customer_id}")
async def get_customer(customer_id: str):
    # Mock retrieval
    return {"status": "success", "data": {"customer_id": customer_id, "name": "Alice Smith", "email": "alice@example.com"}}

@router.post("/upload_document")
async def upload_document(filename: str):
    # Mock upload (normally would use File/UploadFile, but keeping it simple for mock)
    return {"status": "success", "message": f"Document {filename} uploaded successfully"}

@router.get("/download_logs")
async def download_logs():
    # Mock log download
    return {"status": "success", "logs": ["[INFO] System start", "[WARN] High memory"]}

@router.post("/process_refund")
async def process_refund(payload: RefundPayload):
    return {"status": "success", "message": f"Refund of ${payload.amount} processed for customer {payload.customer_id}"}

@router.post("/update_server_config")
async def update_server_config(payload: ServerConfigPayload):
    return {"status": "success", "message": f"Config {payload.config_key} updated"}

@router.post("/request_approval")
async def request_approval(payload: ApprovalPayload):
    return {"status": "success", "approval_token": "token_abc123", "message": "Approval granted"}

@router.get("/export_database")
async def export_database():
    return {"status": "success", "message": "Database export initiated", "download_url": "https://mock.url/export.zip"}
