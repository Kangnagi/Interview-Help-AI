"""
채용공고 · 이력서 · 자기소개서 파일(또는 붙여넣은 글) → 글자 추출 → 자기소개서 작성 칸 채우기.

- 채용공고(kind="posting")   → 제목 · 기업명 · 지원 업무명 · 직무 수행 업무 · 인재상
- 이력서 · 자기소개서(kind="intro") → 자기소개서 내용만 (개인 정보 항목 · 문서 제목은 뺌)

지원 형식: PDF · HWP(한글 5.0) · HWPX · DOCX · TXT. 파일은 메모리에서만 읽고 저장하지 않는다.
형식은 확장자가 아니라 파일 앞부분(시그니처)으로 판단한다.

안전장치
- 압축 해제 · 페이지 수 · 글자 수에 상한을 둬서, 작게 만든 파일이 서버 메모리를 다 쓰게 하지 못하게 한다 (압축 폭탄).
- DOCX · HWPX의 XML은 파서 없이 글자 태그만 정규식으로 꺼낸다 (외부 엔터티 · 엔터티 폭탄 문제가 생기지 않음).
- 암호가 걸린 문서 · 배포용 한글 문서는 읽지 않고 안내한다.
- 칸을 채우기 전에 전화번호 · 이메일 · 주민등록번호는 지운다 (면접 질문 생성에 필요 없고, 저장할 이유가 없다).
"""
import html
import io
import logging
import re
import struct
import zipfile
import zlib
from pathlib import Path

from core.text_safety import clean_user_text

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 5 * 1024 * 1024        # 업로드 파일 최대 5MB
MAX_TEXT_CHARS = 60_000                 # 문서에서 읽는 글자 수 상한 (자기소개서는 길어야 수천 자)
MAX_UNZIPPED_BYTES = 30 * 1024 * 1024   # DOCX · HWPX · HWP 압축을 풀었을 때 상한
MAX_PDF_PAGES = 30

# 화면 칸 길이 (routers/resume.py의 스키마와 같음)
LIMITS = {"title": 200, "company_name": 200, "job_title": 200,
          "job_description": 5000, "ideal_candidate": 3000, "self_introduction": 3000}


class DocumentError(Exception):
    """사용자에게 그대로 보여줄 수 있는 안내 문구를 담는다."""


# ── 형식별 글자 추출 ──────────────────────────────────────────────────────────

def _cap(text: str) -> str:
    return text[:MAX_TEXT_CHARS]


def _read_zip_member(zf: zipfile.ZipFile, name: str, budget: list) -> bytes:
    """압축 폭탄 방지 — 선언된 크기를 믿지 않고 실제로 풀면서 남은 예산을 넘으면 멈춘다."""
    out = bytearray()
    with zf.open(name) as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            budget[0] -= len(chunk)
            if budget[0] < 0:
                raise DocumentError("파일 내용이 너무 큽니다. 자기소개서 부분만 따로 저장해서 올려 주세요.")
            out += chunk
    return bytes(out)


def _tag_bodies(xml: str, tag: str) -> list:
    """<tag …>…</tag> 안쪽들을 차례로 — 끝 태그로 잘라 각 조각의 마지막 시작 태그부터 쓴다 (한 번만 훑는 선형 시간).
    예전 정규식(<w:p .*?</w:p>)은 끝 태그 없는 시작 태그가 많은 조작된 파일에서 시작 태그마다 문서 끝까지 다시 훑어
    (제곱 시간) 서버 CPU를 오래 붙잡을 수 있었다 (10/26 보안 점검)."""
    start_tag = re.compile(rf"<{re.escape(tag)}(?:\s[^<>]*)?>")
    out = []
    for chunk in xml.split(f"</{tag}>")[:-1]:
        last = None
        for last in start_tag.finditer(chunk):
            pass
        if last is not None:
            out.append(chunk[last.end():])
    return out


def _xml_text(xml: str, para_tag: str, text_tag: str) -> str:
    """<{para_tag}> 문단마다 줄을 나누고 <{text_tag}> 안의 글자만 모은다 (표 칸도 문단이라 한 줄씩 나온다)."""
    lines = []
    for body in _tag_bodies(xml, para_tag):
        # 줄바꿈 · 탭 태그는 공백으로
        body = re.sub(r"<(w:br|w:tab|hp:lineBreak|hp:tab)\b[^>]*/>", " ", body)
        parts = _tag_bodies(body, text_tag)
        line = html.unescape(re.sub(r"<[^>]+>", "", "".join(parts)))
        lines.append(line)
    return "\n".join(lines)


def _docx_text(zf: zipfile.ZipFile) -> str:
    budget = [MAX_UNZIPPED_BYTES]
    xml = _read_zip_member(zf, "word/document.xml", budget).decode("utf-8", "ignore")
    return _xml_text(xml, "w:p", "w:t")


def _hwpx_text(zf: zipfile.ZipFile) -> str:
    budget = [MAX_UNZIPPED_BYTES]
    sections = sorted((n for n in zf.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)),
                      key=lambda n: int(re.search(r"\d+", n).group()))
    out = []
    for name in sections:
        xml = _read_zip_member(zf, name, budget).decode("utf-8", "ignore")
        out.append(_xml_text(xml, "hp:p", "hp:t"))
        if sum(map(len, out)) > MAX_TEXT_CHARS:
            break
    return "\n".join(out)


# HWP 5.0 문단 글자(HWPTAG_PARA_TEXT) 안의 제어 문자: 이 코드들은 글자 8칸(16바이트)을 차지하는 개체 표시라 건너뛴다
_HWP_WIDE_CONTROLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
_HWPTAG_PARA_TEXT = 67


def _hwp_para_text(data: bytes) -> str:
    chars = []
    i, n = 0, len(data) // 2
    while i < n:
        code = struct.unpack_from("<H", data, i * 2)[0]
        if code in _HWP_WIDE_CONTROLS:
            i += 8
            continue
        if code in (10, 13):
            chars.append("\n")
        elif code == 9:
            chars.append(" ")
        elif code >= 32:
            chars.append(chr(code))
        i += 1
    return "".join(chars).rstrip("\n")       # 문단 끝 표시(13) — 문단끼리는 줄바꿈 하나로 잇는다


def _inflate(raw: bytes) -> bytes:
    d = zlib.decompressobj(-15)
    out = d.decompress(raw, MAX_UNZIPPED_BYTES)
    if d.unconsumed_tail:
        raise DocumentError("파일 내용이 너무 큽니다. 자기소개서 부분만 따로 저장해서 올려 주세요.")
    return out


def _hwp_text(data: bytes) -> str:
    import olefile
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception:
        raise DocumentError("한글 파일을 열 수 없습니다. 파일이 손상되지 않았는지 확인해 주세요.")
    try:
        if not ole.exists("FileHeader"):
            raise DocumentError("지원하지 않는 형식입니다. (예전 Word .doc 파일이면 .docx로 저장해서 올려 주세요)")
        header = ole.openstream("FileHeader").read()
        if not header.startswith(b"HWP Document File"):
            raise DocumentError("지원하지 않는 형식입니다. (예전 Word .doc 파일이면 .docx로 저장해서 올려 주세요)")
        props = struct.unpack_from("<I", header, 36)[0]
        compressed, encrypted, distribution = props & 1, props & 2, props & 4
        if encrypted:
            raise DocumentError("암호가 걸린 한글 파일은 읽을 수 없습니다. 암호를 풀고 다시 저장해서 올려 주세요.")
        if distribution:
            raise DocumentError("배포용 한글 문서는 읽을 수 없습니다. 일반 문서(.hwp/.hwpx)나 PDF로 저장해서 올려 주세요.")
        sections = sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
                          key=lambda e: int(re.sub(r"\D", "", e[1]) or 0))
        out, total = [], 0
        for entry in sections:
            raw = ole.openstream(entry).read()
            body = _inflate(raw) if compressed else raw
            total += len(body)
            if total > MAX_UNZIPPED_BYTES:
                raise DocumentError("파일 내용이 너무 큽니다. 자기소개서 부분만 따로 저장해서 올려 주세요.")
            pos = 0
            while pos + 4 <= len(body):
                h = struct.unpack_from("<I", body, pos)[0]
                tag, size = h & 0x3FF, (h >> 20) & 0xFFF
                pos += 4
                if size == 0xFFF:
                    if pos + 4 > len(body):
                        break
                    size = struct.unpack_from("<I", body, pos)[0]
                    pos += 4
                if tag == _HWPTAG_PARA_TEXT:
                    out.append(_hwp_para_text(body[pos:pos + size]))
                pos += size
            if sum(map(len, out)) > MAX_TEXT_CHARS:
                break
        return "\n".join(out)
    finally:
        ole.close()


def _unwrap_lines(text: str) -> str:
    """PDF는 쪽 너비에서 문장을 강제로 줄바꿈해 둔다 — 문장 중간에서 끊긴 줄을 다시 잇는다
    (앞 줄이 충분히 길고 문장 끝 · 항목 이름으로 끝나지 않으며, 다음 줄이 새 항목 제목이 아닐 때)."""
    lines = text.split("\n")
    out = []
    for line in lines:
        prev = out[-1] if out else ""
        if (len(prev.strip()) >= 25 and line.strip() and not re.search(r"[.?!:：。]\s*$", prev)
                and not re.match(r"\s*(?:\d+[.)]|[■□▶●◆○\-*•]|\[|【|Q\d|문항)", line)
                and not re.match(r"\s*\S{1,10}(?:\s\S{1,10})?\s*[:：]", line)      # 다음 줄이 '주요 업무: …' 같은 항목
                and not _section_of(line.strip())):                                # 다음 줄이 '근무조건' 같은 채용공고 구역 제목
            out[-1] = prev.rstrip() + " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        raise DocumentError("PDF 파일을 열 수 없습니다. 파일이 손상되지 않았는지 확인해 주세요.")
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):          # 열기 암호 없이 권한만 걸린 PDF는 빈 암호로 열린다
                raise DocumentError("암호가 걸린 PDF는 읽을 수 없습니다. 암호를 풀고 다시 저장해서 올려 주세요.")
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("암호가 걸린 PDF는 읽을 수 없습니다. 암호를 풀고 다시 저장해서 올려 주세요.")
    out = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            out.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(map(len, out)) > MAX_TEXT_CHARS:
            break
    text = _unwrap_lines("\n".join(out))
    if len(re.sub(r"\s", "", text)) < 20:
        raise DocumentError("PDF에서 글자를 찾지 못했습니다. 스캔한 이미지 PDF는 읽을 수 없어요. 한글 · 워드 파일로 올려 주세요.")
    return text


def _plain_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "ignore")
    for enc in ("utf-8-sig", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


def extract_text(filename: str, data: bytes) -> str:
    """파일 내용(바이트) → 글자. 읽을 수 없으면 DocumentError(안내 문구)."""
    if not data:
        raise DocumentError("빈 파일입니다.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError(f"파일이 너무 큽니다 (최대 {MAX_FILE_BYTES // 1024 // 1024}MB).")
    ext = Path(filename or "").suffix.lower()

    if data.startswith(b"%PDF"):
        text = _pdf_text(data)
    elif data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):        # OLE — 한글 5.0 (또는 예전 .doc)
        text = _hwp_text(data)
    elif data.startswith(b"PK\x03\x04"):                             # ZIP — DOCX · HWPX
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise DocumentError("파일을 열 수 없습니다. 파일이 손상되지 않았는지 확인해 주세요.")
        with zf:
            names = set(zf.namelist())
            if "word/document.xml" in names:
                text = _docx_text(zf)
            elif any(re.fullmatch(r"Contents/section\d+\.xml", n) for n in names):
                text = _hwpx_text(zf)
            else:
                raise DocumentError("지원하지 않는 형식입니다. PDF · HWP · HWPX · DOCX · TXT 파일을 올려 주세요.")
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")) or (ext in (".txt", ".md", "") and b"\x00" not in data[:4096]):
        text = _plain_text(data)
    else:
        raise DocumentError("지원하지 않는 형식입니다. PDF · HWP · HWPX · DOCX · TXT 파일을 올려 주세요.")
    # 파일 속 보이지 않는 제어 문자 · 글자 방향 문자 · 모델 구분 기호 제거 (core/text_safety.py) — 글자로만 쓰고 실행하지 않는다
    return _cap(clean_user_text(text))


# ── 정리 · 개인정보 제거 ──────────────────────────────────────────────────────

_PERSONAL = [
    re.compile(r"\b\d{6}\s*-\s*[1-8]\d{6}\b"),                                   # 주민등록번호
    # 이메일 — 길이를 정해 둔다 (예전 [\w.+-]+@… 는 @ 없는 긴 글자 · 숫자 줄에서 시작 위치마다 끝까지 다시 훑어
    # 6만 자 파일에 10초 넘게 걸릴 수 있었다, 10/26). 주소 앞부분 64자 · 도메인 마디 63자는 이메일 규격 상한
    re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}"),
    re.compile(r"(\+82[\s-]?|0)1[016789][\s.-]?\d{3,4}[\s.-]?\d{4}\b"),           # 휴대전화
    re.compile(r"\b0(2|[3-6][1-5])[\s.)-]?\d{3,4}[\s.-]?\d{4}\b"),                 # 지역 전화번호
]


def remove_personal_info(text: str) -> tuple:
    """전화번호 · 이메일 · 주민등록번호를 지운다 → (글, 지운 개수)."""
    count = 0
    for pat in _PERSONAL:
        text, n = pat.subn("", text)
        count += n
    return text, count


def _normalize(text: str) -> str:
    """줄바꿈 · 특수 공백만 정리 (탭 · 여러 칸 띄어쓰기는 '항목 이름 · 값' 구분에 쓰여 남긴다)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub("[\u200b-\u200f\ufeff]", "", text)
    return "\n".join(ln.rstrip() for ln in text.split("\n"))


def clean_text(text: str) -> str:
    text = _normalize(text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = "\n".join(ln.strip() for ln in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ── 칸 채우기 ────────────────────────────────────────────────────────────────

# 항목 이름 — 값은 같은 줄의 ':' · '|' · 탭 · 두 칸 이상 띄어쓰기 뒤, 또는 (표 칸처럼) 이름만 있는 줄의 다음 줄
_COMPANY_NAMES = r"지원\s*(?:회사|기업|처)|회사\s*명|기업\s*명"
_JOB_NAMES = r"지원\s*(?:직무|분야|부문|업무|포지션|직종)|희망\s*(?:직무|분야|직종)|모집\s*(?:분야|부문|직무)|직무"
_DUTY_LABEL = re.compile(r"^[ \t]*(?:담당\s*업무|주요\s*업무|직무\s*(?:내용|설명|소개)|수행\s*업무|하는\s*일)[ \t]*(?:[:：|][ \t]*([^\n]*)|()$)", re.M)
_IDEAL_LABEL = re.compile(r"^[ \t]*(?:인재상|원하는\s*인재|우대\s*사항)[ \t]*(?:[:：|][ \t]*([^\n]*)|()$)", re.M)
# 다음 항목 제목처럼 보이는 줄 (문단을 어디서 끊을지)
_HEADING = re.compile(r"^\s*(?:\d+[.)]|[■□▶●◆○\-*]|\[|【|Q\d|문항)|^.{1,20}\s*[:：]\s*$")


# 개인 정보 항목 — 칸에 넣지 않고 이름 · 값 줄을 통째로 뺀다 (주소 · 생년월일 등은 번호 지우기로 안 걸린다)
_PERSONAL_NAMES = (r"성\s*명|이\s*름|성\s*별|생년월일|나\s*이|연락처|휴대\s*(?:폰|전화)(?:\s*번호)?|전화\s*(?:번호)?"
                   r"|이메일|e-?mail|주\s*소|현\s*주소|거주지|사진|병역|국적")
_DOC_TITLE = re.compile(r"^[ \t]*(?:입사\s*지원서|자기\s*소개서|이력서|지원서)[ \t]*$", re.M)


def _labeled(names: str, text: str) -> tuple:
    """'지원 직무: 서버 개발' · '지원분야 | 서버 개발' · '지원 분야 서버 개발'(짧은 줄) · (표) '지원분야' 다음 줄 '서버 개발'
    에서 값을 꺼낸다 → (값, 이름~값 줄 위치). 못 찾으면 ("", None)."""
    pats = [
        rf"^[ \t]*(?:{names})[ \t]*(?:[:：|]|\t|[ ]{{2,}})[ \t]*(\S[^\n]{{0,39}})$",       # 같은 줄, 구분 기호
        rf"^[ \t]*(?:{names})[ \t]*[:：]?[ \t]*\n+[ \t]*(\S[^\n]{{0,39}})$",               # 이름만 있는 줄 + 다음 줄
        rf"^[ \t]*(?:{names})[ ](\S[^\n]{{0,23}})$",                                        # 같은 줄, 한 칸 띄움 (짧은 줄만)
    ]
    for pat in pats:
        for m in re.finditer(pat, text, re.M | re.I):
            # 표에서 읽으면 다음 칸 제목이 같은 줄에 붙는 경우가 있어 '|' · 탭 · 두 칸 이상 띄어쓴 뒤는 버린다
            v = re.split(r"\s{2,}|\t|\|", m.group(1))[0].strip().strip("·-:：[]()").strip()
            # 값 자리에 다른 항목 이름 · 문장이 오면 다음 후보로
            if v and not re.search(r"[:：]$|습니다|입니다|했다|이다$|[.?!]$", v):
                return v, (m.start(), m.end())
    return "", None


def _personal_spans(text: str) -> list:
    """개인 정보 항목(성명 · 연락처 · 주소 …)의 이름 줄과 값 줄 위치."""
    spans = []
    for m in re.finditer(rf"^[ \t]*(?:{_PERSONAL_NAMES})[ \t]*(?:[:：|\t]|[ ]{{1,}}|$)[^\n]*$", text, re.M | re.I):
        line = m.group()
        if len(line.strip()) > 60:          # 긴 문장 속 '이름' 같은 단어는 항목이 아님
            continue
        end = m.end()
        rest = re.sub(rf"^[ \t]*(?:{_PERSONAL_NAMES})[ \t:：|]*", "", line, flags=re.I).strip()
        if not rest:                         # 이름만 있는 줄(표 칸) → 다음 짧은 줄이 값
            nxt = re.match(r"\n+([^\n]{0,60})(?=\n|$)", text[end:])
            if nxt and not re.search(r"습니다|입니다", nxt.group(1)):
                end += nxt.end()
        spans.append((m.start(), end))
    return spans


def _cut(text: str, spans: list) -> str:
    """겹칠 수 있는 위치들을 뒤에서부터 지운다."""
    for a, b in sorted(merged_spans(spans), reverse=True):
        text = text[:a] + text[b:]
    return text


def merged_spans(spans: list) -> list:
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _block_after(pat: re.Pattern, text: str, limit: int) -> tuple:
    """'주요 업무: …'처럼 제목 뒤 문단(다음 제목 · 빈 줄 전까지)을 가져온다 → (내용, 제목줄 시작~끝 위치)."""
    m = pat.search(text)
    if not m:
        return "", None
    same_line = (m.group(1) or "").strip()        # '주요 업무: …' 같은 줄 내용 (제목만 있는 줄이면 없음)
    parts = [same_line] if same_line else []
    end = m.end()
    for line_m in re.finditer(r"[^\n]*(\n|$)", text[m.end():]):
        line = line_m.group().strip()
        if not line_m.group():
            break
        if not line:
            if parts:
                break
            end = m.end() + line_m.end()
            continue
        if parts and _HEADING.search(line):
            break
        parts.append(line)
        end = m.end() + line_m.end()
        if sum(map(len, parts)) >= limit:
            break
    return "\n".join(p for p in parts if p)[:limit], (m.start(), end)


def _fit(value: str, field: str) -> str:
    return (value or "").strip()[:LIMITS[field]]


def heuristic_fields(text: str) -> dict:
    """제목이 붙은 항목(지원 회사 · 지원 직무 · 주요 업무 · 인재상)을 찾는다.
    자기소개서 칸에는 이 항목들 · 개인 정보 항목 · 문서 제목('입사지원서')을 뺀 나머지."""
    company, company_span = _labeled(_COMPANY_NAMES, text)
    job, job_span = _labeled(_JOB_NAMES, text)
    duty, duty_span = _block_after(_DUTY_LABEL, text, LIMITS["job_description"])
    ideal, ideal_span = _block_after(_IDEAL_LABEL, text, LIMITS["ideal_candidate"])
    spans = [sp for sp in (company_span, job_span, duty_span, ideal_span) if sp]
    spans += _personal_spans(text)
    spans += [(m.start(), m.end()) for m in _DOC_TITLE.finditer(text)]
    return {"company_name": company, "job_title": job, "job_description": duty,
            "ideal_candidate": ideal, "self_introduction": clean_text(_cut(text, spans))}


def prepare(text: str) -> tuple:
    """추출한 글 → (줄 정리 + 개인정보를 지운 글, 지운 개수). 칸 찾기 · 모델에 보내기 전에 꼭 거친다."""
    return remove_personal_info(_normalize(text))


# ── 채용공고 ────────────────────────────────────────────────────────────────
# 채용공고는 '모집부문 / 담당업무 / 자격요건 / 우대사항 / 근무조건 …' 같은 구역으로 나뉜다.
# 구역 제목 줄을 찾아 다음 구역 제목 전까지를 그 구역 내용으로 본다 (목록 기호 '-' '•' 줄도 내용).
_POSTING_SECTIONS = [
    ("company", r"회사\s*명|기업\s*명|채용\s*기업|회사\s*이름"),
    ("job", r"모집\s*(?:부문|분야|직무|직종|포지션)|채용\s*(?:직무|분야|부문|포지션|직군)|포지션|직무\s*명|직\s*무|직\s*군|채용\s*직종"),
    ("duty", r"담당\s*업무|주요\s*업무|업무\s*(?:내용|소개)|수행\s*업무|하는\s*일|직무\s*(?:내용|소개|설명)|이런\s*일을\s*(?:해요|합니다)|합류하면\s*함께\s*할\s*업무"),
    ("qual", r"자격\s*(?:요건|사항|조건)|지원\s*자격|필수\s*(?:요건|자격|역량|사항)|이런\s*분을\s*찾(?:아요|습니다)|요구\s*(?:역량|사항)"),
    ("pref", r"우대\s*(?:사항|조건|요건)|이런\s*분이면\s*더\s*좋아요|플러스\s*요인"),
    ("ideal", r"인재상|원하는\s*인재|이런\s*분과\s*함께|핵심\s*가치"),
    # 아래는 칸에 넣지 않는 구역 — 앞 구역이 어디서 끝나는지 알기 위해서만 찾는다
    ("other", r"근무\s*(?:조건|형태|지역|장소|시간|지|요일)|고용\s*형태|급여|연봉|복리\s*후생|혜택|전형\s*(?:절차|과정|방법)|채용\s*(?:절차|과정)"
              r"|접수\s*(?:기간|방법)|지원\s*(?:방법|기간)|제출\s*서류|모집\s*(?:인원|기간)|기타\s*(?:사항|안내)?|유의\s*사항|문의|회사\s*소개|기업\s*소개"
              r"|마감일|근무\s*부서|경력\s*(?:사항|여부)|학력|채용\s*인원"),
]
_BULLET = r"[\s■□▶▷●○◆◇◎※•·\-*#>]*"
_SECTION_LINE = [(kind, re.compile(
    rf"^{_BULLET}(?:\d+[.)]\s*)?[\[【<(]?\s*(?:{names})\s*[\]】>)]?\s*(?:[:：|]\s*(.*)|\t+(.*)|[ ]{{2,}}(.*)|$)" if kind != "other"
    # 칸에 안 넣는 구역은 '혜택 및 복지' · '근무 조건 안내'처럼 뒤에 몇 글자 더 붙어도 제목으로 본다
    else rf"^{_BULLET}(?:\d+[.)]\s*)?[\[【<(]?\s*(?:{names})[^:：\n]{{0,8}}?\s*[\]】>)]?\s*(?:[:：|]\s*(.*)|$)"))
    for kind, names in _POSTING_SECTIONS]


def _section_of(line: str):
    """구역 제목 줄이면 (구역 종류, 같은 줄 내용), 아니면 None. 긴 문장 속 단어('담당 업무를 맡아…')는 제목이 아님."""
    for kind, pat in _SECTION_LINE:
        m = pat.match(line)
        if m:
            rest = next((g for g in m.groups() if g), "").strip()
            head = line[:len(line) - len(rest)] if rest else line
            if len(head.strip()) <= 25:
                return kind, rest
    return None


def posting_sections(text: str) -> dict:
    """채용공고 → {구역 종류: [내용 줄, …]} (같은 종류가 여러 번 나오면 이어 붙임). 구역 밖 앞부분은 'head'."""
    out = {"head": []}
    cur = "head"
    for raw in text.split("\n"):
        line = raw.strip()
        sec = _section_of(line) if line else None
        if sec:
            cur, rest = sec
            out.setdefault(cur, [])
            if rest:
                out[cur].append(rest)
            continue
        if line:
            out.setdefault(cur, []).append(line)
    return out


def _guess_company(head: list) -> str:
    """구역 제목이 없을 때 공고 첫머리에서 회사 이름 찾기 — '[네오테크] 백엔드 개발자 채용', '(주)네오테크 …', '주식회사 네오테크 …'."""
    for line in head[:8]:
        m = re.match(r"^\s*[\[【]\s*([^\]】]{2,30}?)\s*[\]】]", line)
        if m and not re.search(r"채용|모집|공고|신입|경력|정규직|인턴", m.group(1)):
            return m.group(1).strip()
        m = re.search(r"(?:\(주\)|㈜|주식회사)\s*([가-힣A-Za-z0-9&]{2,20})", line)
        if m:
            return m.group(1)
    return ""


_JOB_WORD = re.compile(r"개발자|엔지니어|디자이너|기획자?|매니저|분석가|마케터|담당자?|연구원|운영|PM|PO|컨설턴트|사무|회계|영업|상담|강사|간호사|기자|에디터|데이터|서버|백엔드|프런트엔드|프론트엔드|인턴")
_POSTING_NOISE = re.compile(r"\d{4}\s*년?|상반기|하반기|신입|경력|정규직|계약직|채용|모집|공고|공개|수시|[(（]\s*\d+\s*명\s*[)）]|및|/")


def _guess_job(head: list, company: str) -> str:
    """구역 제목이 없을 때 공고 첫머리(제목 줄)에서 직무 찾기 — '[그린페이] 2026 하반기 백엔드 개발자 채용' → '백엔드 개발자'."""
    for line in head[:6]:
        v = re.sub(r"^\s*[\[【][^\]】]*[\]】]\s*", "", line)          # 앞의 [회사명]
        v = re.sub(r"(?:\(주\)|㈜|주식회사)\s*\S+", "", v)
        if company:
            v = v.replace(company, "")
        v = re.sub(r"\s+", " ", _POSTING_NOISE.sub(" ", v)).strip(" -·:|")
        if 2 <= len(v) <= 30 and _JOB_WORD.search(v) and not re.search(r"습니다|입니다|[.?!]$", v):
            return v
    return ""


def _short(lines: list) -> str:
    """구역 내용 중 첫 값 하나 (모집부문처럼 짧은 값) — 목록 기호 · 괄호 안 인원수 등은 정리."""
    for line in lines:
        v = re.sub(rf"^{_BULLET}", "", line).strip()
        v = re.split(r"\s{2,}|\t|\|", v)[0].strip()
        v = re.sub(r"\s*[(（]\s*\d+\s*명\s*[)）]\s*$", "", v)        # '백엔드 개발자 (0명)' → '백엔드 개발자'
        if 1 < len(v) <= 40 and not re.search(r"습니다|입니다|[.?!]$", v):
            return v
    return ""


def _block(lines: list, limit: int) -> str:
    return "\n".join(lines)[:limit].strip()


def posting_fields(text: str) -> dict:
    sec = posting_sections(text)
    company = _short(sec.get("company", [])) or _guess_company(sec.get("head", []))
    job = _short(sec.get("job", [])) or _guess_job(sec.get("head", []), company)
    duty_parts = []
    if sec.get("duty"):
        duty_parts.append(_block(sec["duty"], 3000))
    if sec.get("qual"):
        duty_parts.append("[자격 요건]\n" + _block(sec["qual"], 1500))
    ideal_parts = []
    if sec.get("ideal"):
        ideal_parts.append(_block(sec["ideal"], 2000))
    if sec.get("pref"):
        ideal_parts.append("[우대 사항]\n" + _block(sec["pref"], 1500))
    # 구역 제목이 하나도 없는 짧은 공고 — 앞부분 전체를 직무 수행 업무로
    if not duty_parts and not ideal_parts and not job and sec.get("head"):
        duty_parts.append(_block(sec["head"], LIMITS["job_description"]))
    return {"company_name": company, "job_title": job,
            "job_description": "\n\n".join(duty_parts), "ideal_candidate": "\n\n".join(ideal_parts)}


def build_fields(filename: str, text: str, model_guess: dict = None, kind: str = "intro") -> dict:
    """글자 → 화면 칸.
    kind="posting": 채용공고 → 제목 · 기업명 · 지원 업무명 · 직무 수행 업무 · 인재상 (자기소개서 칸은 비움)
    kind="intro"  : 이력서 · 자기소개서 → 자기소개서 내용만 (나머지 칸은 비움)
    model_guess는 구역 제목이 없어 못 찾은 회사 · 직무를 모델이 찾은 값 (원문에 그대로 있는 것만 들어옴)."""
    text, removed = prepare(text)
    if len(re.sub(r"\s", "", text)) < 10:
        raise DocumentError("읽을 수 있는 글자가 거의 없습니다. 내용이 글자로 저장된 파일인지 확인해 주세요.")
    empty = {k: "" for k in LIMITS}
    if kind == "posting":
        f = {**empty, **posting_fields(text)}
        for k in ("company_name", "job_title"):
            if not f[k] and model_guess and model_guess.get(k):
                f[k] = model_guess[k]
        title = " ".join(x for x in (f["company_name"], f["job_title"]) if x)
        f["title"] = f"{title} 지원" if title else ""
        truncated = False
    else:
        f = {**empty, "self_introduction": heuristic_fields(text)["self_introduction"]}
        truncated = len(f["self_introduction"]) > LIMITS["self_introduction"]
    out = {k: _fit(v, k) for k, v in f.items()}
    out["truncated"] = truncated
    out["removed_personal"] = removed
    return out
