from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

class EmailPayload(BaseModel):
    to: EmailStr
    subject: str
    body: str

class CustomerPayload(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None

class RefundPayload(BaseModel):
    customer_id: str
    amount: float = Field(gt=0, description="Refund amount must be greater than 0")
    reason: str

class ServerConfigPayload(BaseModel):
    config_key: str
    config_value: Any
    
class ApprovalPayload(BaseModel):
    action: str
    justification: str
