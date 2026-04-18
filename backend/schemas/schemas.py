from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models.interview import InterviewStatus, InterviewCategory


# ─── User ───────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Interview ──────────────────────────────────────
class InterviewCreate(BaseModel):
    title: str
    category: InterviewCategory = InterviewCategory.GENERAL

class InterviewResponse(BaseModel):
    id: int
    title: str
    category: InterviewCategory
    status: InterviewStatus
    total_questions: int
    duration_seconds: Optional[int]
    created_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True

class QuestionResponse(BaseModel):
    id: int
    order: int
    question_text: str
    answer_text: Optional[str]
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True

class AnswerSubmit(BaseModel):
    answer_text: str


# ─── Analysis ───────────────────────────────────────
class AnalysisResponse(BaseModel):
    id: int
    interview_id: int
    total_score: Optional[float]
    content_score: Optional[float]
    relevance_score: Optional[float]
    clarity_score: Optional[float]
    speech_score: Optional[float]
    posture_score: Optional[float]
    eye_contact_score: Optional[float]
    feedback_summary: Optional[str]
    strengths: Optional[List[str]]
    improvements: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── WebSocket ──────────────────────────────────────
class WSMessage(BaseModel):
    type: str           # "start" | "stop" | "answer" | "status"
    payload: Optional[dict] = None
