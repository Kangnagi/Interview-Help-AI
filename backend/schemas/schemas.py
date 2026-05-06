"""
Pydantic 스키마 — API 요청/응답 데이터 형식 정의

역할:
  - 클라이언트가 보낸 JSON을 Python 객체로 변환 (입력 검증)
  - DB 모델(SQLAlchemy)을 JSON 응답으로 직렬화 (출력 변환)
  - from_attributes = True → ORM 객체를 스키마로 자동 변환 가능 (Pydantic v2)
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models.interview import InterviewStatus, InterviewCategory


# ─── User (사용자) ────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """POST /auth/register 요청 바디 — 회원가입 입력값"""
    email: EmailStr   # 이메일 형식 자동 검증 (예: user@example.com)
    username: str
    password: str     # 평문 수신 후 security.py에서 argon2 해싱 처리


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


# ─── Interview (면접) ─────────────────────────────────────────────────────────

class InterviewCreate(BaseModel):
    """POST /interviews 요청 바디 — 면접 생성 입력값"""
    title: str
    # 카테고리를 지정하지 않으면 일반 면접(GENERAL)으로 생성
    category: InterviewCategory = InterviewCategory.GENERAL
<<<<<<< Updated upstream

=======
    interview_type: str = "practice"
    resume_ref_id: Optional[str] = None
>>>>>>> Stashed changes

class InterviewResponse(BaseModel):
    """면접 단건 조회·목록 응답"""
    id: int
    title: str
    category: InterviewCategory   # general / technical / behavioral / self_intro
    status: InterviewStatus       # pending / in_progress / completed / cancelled
    total_questions: int
<<<<<<< Updated upstream
    duration_seconds: Optional[int]   # 면접 총 소요 시간 (종료 후 산출)
=======
    duration_seconds: Optional[int]
    interview_type: Optional[str] = None
    resume_ref_id: Optional[str] = None
>>>>>>> Stashed changes
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

    class Config:
        from_attributes = True


class AnswerSubmit(BaseModel):
    """POST /interviews/{id}/questions/{qid}/answer 요청 바디 — 답변 저장"""
    answer_text: str   # Whisper STT 변환 텍스트 또는 프론트에서 직접 입력한 텍스트


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

    created_at: datetime

    class Config:
        from_attributes = True


# ─── WebSocket 제어 메시지 ────────────────────────────────────────────────────

class WSMessage(BaseModel):
<<<<<<< Updated upstream
    """
    WebSocket으로 주고받는 JSON 제어 메시지 형식.
    바이너리(영상 프레임)는 별도로 bytes로 전송하고 이 스키마는 사용하지 않음.
    """
    type: str                       # "start" | "stop" | "ping" | "status" | "frame_analysis"
    payload: Optional[dict] = None  # type별 추가 데이터 (없으면 None)
=======
    type: str
    payload: Optional[dict] = None
>>>>>>> Stashed changes
