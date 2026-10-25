"""
사용자가 넣은 글(입력 칸 · 답변 · 파일에서 읽은 글)을 저장 · 모델 입력 전에 정리한다 (10/26 보안 점검).

- 제어 문자: NUL(\\x00) 같은 보이지 않는 문자는 DB · 로그 · 화면에서 오류나 표시 위장을 일으킬 수 있어 지운다 (줄바꿈 · 탭은 남김)
- 글자 방향 문자(U+202A~202E, U+2066~2069): 'txt.exe'를 'exe.txt'처럼 보이게 하는 데 쓰여 지운다
- 언어 모델 대화 구분 기호(<|eot_id|>, <|start_header_id|> …): 답변에 섞이면 토크나이저가 진짜 구분 기호로 읽어
  '여기서부터 채점 결과'처럼 대화를 꾸며 점수를 조작할 수 있다 → 모델에 넣기 전에 지운다

SQL 문법(' OR 1=1 --)이나 HTML(<script>)은 지우지 않는다 — DB는 매개변수 방식(SQLAlchemy)이라 글로만 저장되고,
화면(React)은 글자를 그대로 글자로 보여 주므로 실행되지 않는다. 지우면 '<' 같은 정상 글자까지 망가진다.
"""
import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]")
_BIDI = re.compile("[‪-‮⁦-⁩]")
_MODEL_TOKEN = re.compile(r"<\|[^<>|\n]{1,64}\|>")


def strip_model_tokens(text: str) -> str:
    """언어 모델 대화 구분 기호(<|…|>)만 지운다 — 모델에 넣는 사용자 글에 쓴다."""
    return _MODEL_TOKEN.sub("", text or "")


def clean_user_text(text, keep_newlines: bool = True):
    """사용자 글 정리 — 줄바꿈 통일(\\r\\n → \\n), 제어 · 글자 방향 문자와 모델 구분 기호 제거, 유니코드 정규화(NFC).
    None은 그대로 둔다 (선택 입력 칸)."""
    if text is None:
        return None
    text = unicodedata.normalize("NFC", str(text)).replace("\r\n", "\n").replace("\r", "\n")
    text = _BIDI.sub("", _CONTROL.sub("", text))
    text = strip_model_tokens(text)
    if not keep_newlines:
        text = re.sub(r"[\n\t]+", " ", text)
    return text
