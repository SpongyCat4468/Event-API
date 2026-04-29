from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class TodoBase(BaseModel):
    title: str
    description: Optional[str] = None
    isCompleted: bool = False
    notificationTimes: List[int] = []  

class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    isCompleted: Optional[bool] = None
    notificationTimes: Optional[List[int]] = None  

class TodoResponse(TodoBase):
    id: int
    user_email: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True