"""텍스트 정제 유틸리티"""
import re


def sanitize_memory_text(text: str) -> str:
    """메모리 저장 전 텍스트 정제

    - 마크다운 문법 제거 (**bold**, `code`)
    - 이모지 제거
    - 허용: 영어, 한국어, 숫자, 기본 문장부호
    """
    if not text:
        return text

    # 마크다운 제거
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 이모지 제거
    text = re.sub(r'[\U0001F000-\U0001FFFF]', '', text)
    text = re.sub(r'[\u2600-\u27BF]', '', text)

    # 허용: 영어, 한국어, 숫자, 기본 문장부호, 공백, 줄바꿈
    text = re.sub(r"[^a-zA-Z0-9가-힣\s.,!?:;\-()\"'\[\]\n/]", '', text)

    # 연속 공백 정리
    text = re.sub(r' +', ' ', text)

    return text.strip()
