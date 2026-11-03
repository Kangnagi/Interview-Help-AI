"""
Pydantic 스키마 — API 요청/응답 데이터 형식 정의

역할:
  - 클라이언트가 보낸 JSON을 Python 객체로 변환 (입력 검증)
  - DB 모델(SQLAlchemy)을 JSON 응답으로 직렬화 (출력 변환)
  - from_attributes = True → ORM 객체를 스키마로 자동 변환 가능 (Pydantic v2)
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from core.text_safety import clean_user_text
from typing import Optional, List
from datetime import datetime
from models.interview import InterviewStatus, InterviewCategory


# ─── User (사용자) ────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """POST /auth/register 요청 바디 — 회원가입 입력값"""
    email: EmailStr   # 이메일 형식 자동 검증 (예: user@example.com)
    username: str = Field(min_length=1, max_length=30)
    # 평문 수신 후 security.py에서 argon2 해싱 처리. 8자 이상 (비밀번호 재설정과 같은 기준 — 예전엔 가입만 1글자도 됐다),
    # 128자 이하 (아주 긴 값으로 해싱에 시간을 끄는 것 방지)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def _clean_name(cls, v):
        v = clean_user_text(v, keep_newlines=False).strip() if isinstance(v, str) else v
        if isinstance(v, str) and not v:
            raise ValueError("이름을 입력해주세요")
        return v


class UserLogin(BaseModel):
    """POST /auth/login 요청 바디 — 로그인 입력값"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """사용자 정보 응답 — 비밀번호는 절대 포함하지 않음"""
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True   # User ORM 객체 → UserResponse 자동 변환


class TokenResponse(BaseModel):
    """POST /auth/login 응답 — JWT 토큰 + 사용자 정보 함께 반환"""
    access_token: str
    token_type: str = "bearer"  # OAuth2 표준 Bearer 방식
    user: UserResponse          # 로그인 직후 사용자 프로필도 함께 전달해 프론트 왕복 절약


class PasswordResetRequest(BaseModel):
    """POST /auth/password-reset/request — 재설정 이메일 요청"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """POST /auth/password-reset/confirm — 새 비밀번호 설정"""
    token: str = Field(max_length=200)
    new_password: str = Field(max_length=128)


# ─── Interview (면접) ─────────────────────────────────────────────────────────

class InterviewCreate(BaseModel):
    """POST /interviews 요청 바디 — 면접 생성 입력값"""
    title: str = Field(max_length=200)
    category: InterviewCategory = InterviewCategory.GENERAL
    interview_type: str = Field(default="practice", max_length=20)          # 'practice' | 'real'
    resume_ref_id: Optional[str] = Field(default=None, max_length=40)
    resume_text: Optional[str] = Field(default=None, max_length=15000)     # 자기소개서 칸들을 합친 글 (각 칸 상한의 합보다 조금 크게)

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, v):   # 보이지 않는 제어 문자 · 글자 방향 문자 · 모델 구분 기호 제거 (core/text_safety.py)
        return clean_user_text(v) if isinstance(v, str) else v

class InterviewResponse(BaseModel):
    """면접 단건 조회·목록 응답"""
    id: int
    title: str
    category: InterviewCategory   # general / technical / behavioral / self_intro
    status: InterviewStatus       # pending / in_progress / completed / cancelled
    total_questions: int
    duration_seconds: Optional[int]
    interview_type: Optional[str] = None
    resume_ref_id: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime]      # 면접 종료 시각 (진행 중이면 None)

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    """질문 목록 응답 — 답변 포함"""
    id: int
    order: int            # 질문 순서 (1부터 시작)
    question_text: str
    answer_text: Optional[str]        # 아직 답변 안 했으면 None
    duration_seconds: Optional[int]   # 해당 질문 답변 소요 시간
    ai_score: Optional[float] = None  # 분석 후 채워지는 AI 점수
    ai_feedback: Optional[str] = None # 분석 후 채워지는 AI 피드백

    class Config:
        from_attributes = True


class AnswerSubmit(BaseModel):
    """POST /interviews/{id}/questions/{qid}/answer 요청 바디 — 답변 저장"""
    answer_text: str = Field(max_length=5000)   # Whisper STT 변환 텍스트 또는 프론트에서 직접 입력한 텍스트

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, v):   # 보이지 않는 제어 문자 · 글자 방향 문자 · 모델 구분 기호 제거 (core/text_safety.py)
        return clean_user_text(v) if isinstance(v, str) else v


class QuestionFeedbackResponse(BaseModel):
    """POST /interviews/{id}/questions/{qid}/feedback 응답 — 즉시 AI 피드백"""
    score: int
    feedback: str
    tip: str


class QuestionWithFeedback(BaseModel):
    """분석 결과 내 질문별 상세 피드백"""
    id: int
    order: int
    question_text: str
    answer_text: Optional[str] = None
    ai_score: Optional[float] = None
    ai_feedback: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Analysis (분석 결과) ─────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    """GET /analysis/{id} 응답 — AI 분석 결과 전체"""
    id: int
    interview_id: int

    # 종합 점수 (0~100) — 하위 점수들의 평균
    total_score: Optional[float]

    # KoBERT 분석 점수 (답변 내용 기반)
    content_score: Optional[float]    # 내용 적절성
    relevance_score: Optional[float]  # 질문 관련성
    clarity_score: Optional[float]    # 명확성

    # Whisper + Librosa 분석 점수 (음성 기반)
    speech_score: Optional[float]     # 발화 종합 점수

    # MediaPipe 분석 점수 (영상 기반)
    posture_score: Optional[float]    # 자세 점수
    eye_contact_score: Optional[float]  # 눈맞춤 점수

    # 텍스트 피드백
    feedback_summary: Optional[str]        # AI 종합 피드백 요약
    strengths: Optional[List[str]]         # 잘한 점 목록
    improvements: Optional[List[str]]      # 개선할 점 목록

    # 질문별 상세 피드백 (분석 파이프라인 완료 후 채워짐)
    question_feedbacks: Optional[List[QuestionWithFeedback]] = None

    created_at: datetime

    class Config:
        from_attributes = True


# ─── WebSocket 제어 메시지 ────────────────────────────────────────────────────

class WSMessage(BaseModel):
    """
    WebSocket으로 주고받는 JSON 제어 메시지 형식.
    바이너리(영상 프레임)는 별도로 bytes로 전송하고 이 스키마는 사용하지 않음.
    """
    type: str                       # "start" | "stop" | "ping" | "status" | "frame_analysis"
    payload: Optional[dict] = None  # type별 추가 데이터 (없으면 None)
