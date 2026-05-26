<<<<<<< HEAD
"""
면접 라우터 — /api/v1/interviews

엔드포인트:
  POST   /interviews                               — 면접 세션 생성 + 질문 자동 할당
  GET    /interviews                               — 내 면접 목록 조회 (최신순)
  GET    /interviews/{id}                          — 면접 단건 조회
  GET    /interviews/{id}/questions                — 질문 목록 조회
  POST   /interviews/{id}/questions/{qid}/answer   — 질문 답변 저장
  POST   /interviews/{id}/questions/{qid}/feedback — 질문 즉시 AI 피드백
  PATCH  /interviews/{id}/finish                   — 면접 종료 처리
  DELETE /interviews/{id}                          — 면접 삭제
  POST   /interviews/transcribe                    — 음성 STT 변환
"""
=======
>>>>>>> origin/feature/AI_model_error_v2
import json
import logging
import os
from datetime import datetime
import hashlib
from typing import List

<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sqla_delete
=======
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
>>>>>>> origin/feature/AI_model_error_v2
from pydantic import BaseModel

from core.database import get_db
from core.security import get_current_user_id
from models.interview import Interview, InterviewQuestion, InterviewStatus
<<<<<<< HEAD
from models.analysis import Analysis
from schemas.schemas import InterviewCreate, InterviewResponse, QuestionResponse, AnswerSubmit
from core.config import settings
=======
from schemas.schemas import InterviewCreate, InterviewResponse
>>>>>>> origin/feature/AI_model_error_v2
from services.llm.gemini_service import generate_questions_from_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interviews", tags=["면접"])

QUESTION_CACHE_FILE = "question_cache.json"
<<<<<<< HEAD


def load_question_cache():
    if os.path.exists(QUESTION_CACHE_FILE):
        try:
            with open(QUESTION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_question_cache(cache_data):
    try:
        with open(QUESTION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
    except Exception:
        pass


_question_cache = load_question_cache()


class AnswerCreate(BaseModel):
    answer_text: str
=======
>>>>>>> origin/feature/AI_model_error_v2

def load_question_cache():
    if os.path.exists(QUESTION_CACHE_FILE):
        try:
            with open(QUESTION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_question_cache(cache_data):
    try:
        with open(QUESTION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
    except Exception:
        pass

_question_cache = load_question_cache()

@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(
    body: InterviewCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
<<<<<<< HEAD
    """
    면접 세션 생성.

    1) Interview 레코드 생성
    2) 자기소개서 기반 Gemini 질문 생성 (없으면 폴백 질문)
    3) total_questions 업데이트 후 반환
    """
=======
    # 1. 면접 엔티티 생성
>>>>>>> origin/feature/AI_model_error_v2
    interview = Interview(
        user_id=user_id,
        title=body.title,
        category=body.category,
        interview_type=body.interview_type,
        resume_ref_id=body.resume_ref_id,
    )
    db.add(interview)
<<<<<<< HEAD
    await db.flush()  # interview.id 확보 (질문의 interview_id FK에 필요)

    questions_list = []
    try:
        resume_hash = ""
        if body.resume_text:
            resume_hash = hashlib.sha256(body.resume_text.encode('utf-8')).hexdigest()

        cache_entry = None
        if resume_hash and resume_hash in _question_cache:
            cache_entry = _question_cache[resume_hash]
            # 구버전 캐시(리스트 형태) 호환성 처리
            if isinstance(cache_entry, list):
                cache_entry = {
                    "ai_questions": cache_entry[2:] if len(cache_entry) > 2 else cache_entry,
                    "index": 0
                }
            logger.info(f"Interview {interview.id}: 캐시된 질문 풀에서 가져옵니다. (API 절약)")
        elif settings.GEMINI_API_KEY and body.resume_text and len(body.resume_text.strip()) > 10:
            logger.info(f"Interview {interview.id}: Gemini API로 질문 풀 생성을 시도합니다.")
            category_val = body.category.value if hasattr(body.category, "value") else str(body.category)
            raw_questions = await generate_questions_from_resume(
                resume_text=body.resume_text,
                category=category_val,
                num_questions=8
            )
            if raw_questions and len(raw_questions) > 2:
                cache_entry = {
                    "ai_questions": raw_questions[2:],
                    "index": 0
                }
                if resume_hash:
                    _question_cache[resume_hash] = cache_entry
                    save_question_cache(_question_cache)
            else:
                logger.warning(f"Interview {interview.id}: Gemini가 질문을 반환하지 않았습니다. 폴백 로직을 사용합니다.")
        else:
            logger.info(f"Interview {interview.id}: Gemini API 키가 없거나 자기소개서 내용이 부족하여 폴백 로직을 사용합니다.")

        if cache_entry and "ai_questions" in cache_entry:
            ai_pool = cache_entry["ai_questions"]
            idx = cache_entry.get("index", 0)

            selected_ai = []
            count_to_pick = min(3, len(ai_pool))
            for _ in range(count_to_pick):
                selected_ai.append(ai_pool[idx])
                idx = (idx + 1) % len(ai_pool)

            # 다음 면접을 위해 회전된 인덱스 저장
            cache_entry["index"] = idx
            if resume_hash:
                _question_cache[resume_hash] = cache_entry
                save_question_cache(_question_cache)

            questions_list = [
                "간단한 자기소개 부탁드립니다.",
                "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?"
            ] + selected_ai

    except Exception as e:
        logger.error(f"Interview {interview.id}: 질문 생성 중 예외 발생, 폴백 로직 실행: {e}")

    # AI 질문 생성에 실패한 경우 기본 폴백 질문 사용
    if not questions_list or len(questions_list) <= 2:
        FALLBACK_QUESTIONS = [
            "간단한 자기소개 부탁드립니다.",
            "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?",
            "자기소개서에 작성하신 경험에 대해 더 자세히 설명해 주세요.",
            "지원하신 직무와 관련하여 본인만의 강점은 무엇인가요?",
            "가장 힘들었던 경험과 이를 어떻게 극복했는지 말씀해 주세요.",
        ]
        questions_list = FALLBACK_QUESTIONS[:5]

=======
    await db.flush()  # ID 생성을 위해 flush

    questions_list = []
    try:
        resume_hash = ""
        if body.resume_text:
            resume_hash = hashlib.sha256(body.resume_text.encode('utf-8')).hexdigest()
            
        if resume_hash and resume_hash in _question_cache:
            cache_entry = _question_cache[resume_hash]
            # 구버전 캐시(리스트 형태) 호환성 처리
            if isinstance(cache_entry, list):
                cache_entry = {
                    "ai_questions": cache_entry[2:] if len(cache_entry) > 2 else cache_entry,
                    "index": 0
                }
            logger.info(f"Interview {interview.id}: 캐시된 질문 풀에서 3개를 가져옵니다. (API 절약)")
        elif os.getenv("GEMINI_API_KEY") and body.resume_text and len(body.resume_text.strip()) > 10:
            logger.info(f"Interview {interview.id}: Gemini API로 질문 풀 생성을 시도합니다.")
            category_val = body.category.value if hasattr(body.category, "value") else str(body.category)
            raw_questions = await generate_questions_from_resume(
                resume_text=body.resume_text,
                category=category_val,
                num_questions=8  # 타임아웃 방지: 고정 2개 + AI 질문 6개로 축소
            )
            if raw_questions and len(raw_questions) > 2:
                cache_entry = {
                    "ai_questions": raw_questions[2:],
                    "index": 0
                }
            else:
                cache_entry = None
                logger.warning(f"Interview {interview.id}: Gemini가 질문을 반환하지 않았습니다. 폴백 로직을 사용합니다.")
        else:
            cache_entry = None
            logger.info(f"Interview {interview.id}: Gemini API 키가 없거나 자기소개서 내용이 부족하여 폴백 로직을 사용합니다.")

        if cache_entry and "ai_questions" in cache_entry:
            ai_pool = cache_entry["ai_questions"]
            idx = cache_entry.get("index", 0)
            
            selected_ai = []
            count_to_pick = min(3, len(ai_pool))
            for _ in range(count_to_pick):
                selected_ai.append(ai_pool[idx])
                idx = (idx + 1) % len(ai_pool)
                
            # 다음 면접을 위해 회전된 인덱스 저장
            cache_entry["index"] = idx
            _question_cache[resume_hash] = cache_entry
            save_question_cache(_question_cache)
            
            questions_list = [
                "간단한 자기소개 부탁드립니다.",
                "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?"
            ] + selected_ai

    except Exception as e:
        logger.error(f"Interview {interview.id}: Gemini 질문 생성 중 예외 발생, 폴백 로직 실행: {e}")

    # 3. AI 질문 생성에 실패한 경우, 기본 폴백 질문 사용
    if not questions_list or len(questions_list) <= 2:
        DEFAULT_QUESTIONS = [
            "간단한 자기소개 부탁드립니다.",
            "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?",
            "자기소개서에 작성하신 경험에 대해 더 자세히 설명해 주세요.",
            "지원하신 직무와 관련하여 본인만의 강점은 무엇인가요?",
            "가장 힘들었던 경험과 이를 어떻게 극복했는지 말씀해 주세요.",
        ]
        questions_list = DEFAULT_QUESTIONS[:5]

    # 4. 생성된 질문을 DB에 저장
>>>>>>> origin/feature/AI_model_error_v2
    for i, q_text in enumerate(questions_list):
        new_q = InterviewQuestion(
            interview_id=interview.id,
            order=i + 1,
            question_text=q_text,
        )
        db.add(new_q)

    interview.total_questions = len(questions_list)

<<<<<<< HEAD
    await db.commit()
=======
    # 5. 최종 커밋 및 데이터 반환
    await db.commit() 
>>>>>>> origin/feature/AI_model_error_v2
    await db.refresh(interview)
    return interview


@router.get("")
async def list_interviews(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자의 모든 면접 이력과 종합 점수를 조회합니다."""
<<<<<<< HEAD
=======
    from models.analysis import Analysis
>>>>>>> origin/feature/AI_model_error_v2
    result = await db.execute(
        select(Interview, Analysis.total_score)
        .outerjoin(Analysis, Interview.id == Analysis.interview_id)
        .where(Interview.user_id == user_id)
        .order_by(Interview.created_at.desc())
    )
<<<<<<< HEAD

=======
    
>>>>>>> origin/feature/AI_model_error_v2
    data = []
    for iv, score in result.all():
        data.append({
            "id": iv.id,
            "title": iv.title,
            "category": iv.category.value if hasattr(iv.category, 'value') else iv.category,
            "status": iv.status.value if hasattr(iv.status, 'value') else iv.status,
            "total_questions": iv.total_questions,
            "created_at": iv.created_at.isoformat() if iv.created_at else None,
            "total_score": round(score, 1) if score else None
        })
    return data


<<<<<<< HEAD
@router.get("/{interview_id}")
async def get_interview(
=======
# ----------------------------------------------------
# 프론트엔드 연동을 위한 추가 API 라우터
# ----------------------------------------------------

class AnswerCreate(BaseModel):
    answer_text: str

@router.get("/{interview_id}/questions")
async def get_interview_questions(
>>>>>>> origin/feature/AI_model_error_v2
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
<<<<<<< HEAD
    """면접 단건 조회 — 본인 소유 면접만 접근 가능."""
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")
    return interview


@router.get("/{interview_id}/questions", response_model=List[QuestionResponse])
async def get_interview_questions(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """질문 목록 조회 — 소유권 확인 후 order 기준 오름차순 반환."""
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    q_result = await db.execute(
=======
    """특정 면접의 질문 목록을 가져옵니다."""
    result = await db.execute(
>>>>>>> origin/feature/AI_model_error_v2
        select(InterviewQuestion)
        .where(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order)
    )
    return result.scalars().all()

@router.post("/{interview_id}/questions/{question_id}/answer")
async def submit_answer(
    interview_id: int,
    question_id: int,
<<<<<<< HEAD
    body: AnswerCreate,
=======
    answer_text: str = Form(...),
    is_practice: bool = Form(False),
    audio_file: UploadFile = File(None),
>>>>>>> origin/feature/AI_model_error_v2
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
<<<<<<< HEAD
    """면접 질문에 대한 사용자의 답변(텍스트)을 서버에 저장합니다."""
=======
    """면접 질문에 대한 사용자의 답변(텍스트 및 오디오 파일)을 서버에 저장합니다."""
>>>>>>> origin/feature/AI_model_error_v2
    result = await db.execute(
        select(InterviewQuestion).where(InterviewQuestion.id == question_id, InterviewQuestion.interview_id == interview_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")
    
    question.answer_text = answer_text
    
    # 🔊 전송받은 음성 파일이 있다면 분석을 위해 로컬에 저장
    image_bytes = None
    if audio_file:
        from core.config import settings
        file_path = f"{settings.UPLOAD_DIR}/iv_{interview_id}_q_{question_id}.webm"
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())
            
        if is_practice:
            try:
                from services.voice.librosa_service import generate_audio_spectrogram
                image_bytes = await generate_audio_spectrogram(file_path)
            except Exception as e:
                logger.warning(f"오디오 이미지 변환 실패: {e}")

<<<<<<< HEAD
    question.answer_text = body.answer_text
    db.add(question)
    await db.commit()
    return {"message": "답변이 저장되었습니다"}
=======
    feedback = None
    if is_practice:
        from services.llm.gemini_service import analyze_answer_with_gemini_short
        feedback = await analyze_answer_with_gemini_short(question.question_text, answer_text, image_bytes)
>>>>>>> origin/feature/AI_model_error_v2

    await db.commit()
    return {"message": "답변이 저장되었습니다", "feedback": feedback}

@router.post("/{interview_id}/questions/{question_id}/feedback")
async def get_question_feedback(
    interview_id: int,
    question_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """답변 저장 직후 즉시 AI 피드백을 반환합니다 (연습·실전 면접 공통)."""
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.id == question_id,
            InterviewQuestion.interview_id == interview_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

    if not question.answer_text or not question.answer_text.strip():
        return {"score": 0, "feedback": "답변이 없습니다. 답변을 먼저 입력해 주세요.", "tip": ""}

    from services.llm.gemini_service import analyze_answer_with_gemini_short
    feedback = await analyze_answer_with_gemini_short(
        question=question.question_text,
        answer=question.answer_text,
    )
    return feedback


@router.patch("/{interview_id}/finish")
async def finish_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """면접 상태를 완료(COMPLETED)로 변경합니다."""
<<<<<<< HEAD
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
=======
    result = await db.execute(select(Interview).where(Interview.id == interview_id))
>>>>>>> origin/feature/AI_model_error_v2
    interview = result.scalar_one_or_none()
    if interview:
        try:
            interview.status = InterviewStatus.COMPLETED
        except AttributeError:
            interview.status = "completed"
        await db.commit()
        
    return {"message": "면접이 완료되었습니다"}

<<<<<<< HEAD
    try:
        interview.status = InterviewStatus.COMPLETED
    except AttributeError:
        interview.status = "completed"

    interview.ended_at = datetime.utcnow()
    await db.commit()
    return {"message": "면접이 완료되었습니다"}


@router.delete("/{interview_id}", status_code=204)
async def delete_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """면접 기록 삭제 — 소유자만 가능, 연관 질문·분석 결과도 함께 삭제됩니다."""
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    await db.execute(sqla_delete(Analysis).where(Analysis.interview_id == interview_id))
    await db.execute(sqla_delete(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id))
    await db.delete(interview)
    await db.commit()
    return Response(status_code=204)

=======
>>>>>>> origin/feature/AI_model_error_v2

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
<<<<<<< HEAD
    user_id: int = Depends(get_current_user_id),
=======
    user_id: int = Depends(get_current_user_id)
>>>>>>> origin/feature/AI_model_error_v2
):
    """음성 파일을 업로드받아 텍스트로 변환(STT)합니다."""
    audio_bytes = await file.read()
    try:
        from services.voice.whisper_service import whisper_service
<<<<<<< HEAD
        if hasattr(whisper_service, "transcribe_bytes"):
            result = await whisper_service.transcribe_bytes(audio_bytes)
            logger.info(f"[STT 분석 결과] {result}")
=======
        # whisper_service에 transcribe_bytes 메서드가 구현되어 있다고 가정
        if hasattr(whisper_service, "transcribe_bytes"):
            result = await whisper_service.transcribe_bytes(audio_bytes)
            logger.info(f"🎤 [STT 분석 결과] {result}")
>>>>>>> origin/feature/AI_model_error_v2
            text = result.get("text", "") if isinstance(result, dict) else str(result)
        else:
            text = "음성 인식을 완료했습니다. (현재 Whisper 모델 연동 대기 중)"
        return {"text": text}
    except Exception as e:
        logger.error(f"STT 변환 중 오류: {e}")
<<<<<<< HEAD
        return {"text": f"음성 변환 실패: {str(e)}"}
=======
        return {"text": f"음성 변환 실패: {str(e)}"}
>>>>>>> origin/feature/AI_model_error_v2
