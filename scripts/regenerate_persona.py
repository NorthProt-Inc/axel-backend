#!/usr/bin/env python3

import asyncio
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.config import PERSONA_PATH, DATA_ROOT, SQLITE_MEMORY_PATH
from backend.core.utils.timezone import VANCOUVER_TZ, now_vancouver
CHECKPOINT_FILE = DATA_ROOT / "persona_insights_checkpoint.json"

def humanize_role(role: str) -> str:

    role_lower = role.lower()
    if role_lower in ('assistant', 'ai', 'axel'):
        return 'Axel'
    elif role_lower in ('user', 'mark'):
        return 'Mark'
    return role

def humanize_text(text: str) -> str:

    text = re.sub(r'\b(AI|Assistant)\b', 'Axel', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(User)\b', 'Mark', text, flags=re.IGNORECASE)
    return text

def merge_behaviors(old_behaviors: list, new_insights: list) -> list:

    merged = []

    print(f"  📉 기존 행동 {len(old_behaviors)}개 감가상각 진행 (Factor: 0.6)...")
    for b in old_behaviors:
        old_conf = b.get('confidence', 0.5)
        new_conf = round(old_conf * 0.6, 2)

        if new_conf >= 0.3:
            b['confidence'] = new_conf
            b['decayed'] = True
            merged.append(b)
        else:

            pass

    return merged

def main():
    print("=" * 60)
    print("  🧬 페르소나 진화 프로세스 (Evolutionary Update)")
    print("  Target: Mark & Axel's Brotherhood")
    print("=" * 60)
    print()

    old_persona = {}
    if PERSONA_PATH.exists():
        try:
            with open(PERSONA_PATH, 'r', encoding='utf-8') as f:
                old_persona = json.load(f)
            print(f"  ✓ 기존 페르소나 로드됨 (v{old_persona.get('version', 0)})")
        except Exception as e:
            print(f"  ⚠ 기존 페르소나 로드 실패: {e}")
            old_persona = {}

    print("\n[1/4] 기억 데이터 로딩...")
    from backend.memory.permanent import LongTermMemory
    ltm = LongTermMemory()

    all_data = ltm.collection.get(include=["documents", "metadatas"], limit=1000)
    documents = all_data.get('documents', [])
    metadatas = all_data.get('metadatas', [])

    import sqlite3
    sql_memories = []
    try:
        conn = sqlite3.connect(str(SQLITE_MEMORY_PATH))
        cur = conn.cursor()
        cur.execute("SELECT role, content, timestamp FROM messages ORDER BY timestamp DESC LIMIT 300")
        rows = cur.fetchall()
        for role, content, ts in rows:
            if content:
                human_role = humanize_role(role)
                documents.append(f"{human_role}: {content}")
                metadatas.append({'source': 'sqlite', 'timestamp': ts})
                sql_memories.append(content)
        conn.close()
    except Exception as e:
        print(f"  ⚠ SQLite 로드 실패: {e}")

    total_memories = len(documents)
    print(f"  ✓ 총 {total_memories}개 기억 로드 완료")

    if total_memories == 0:
        return

    print("\n[2/4] 대화 맥락 배치 구성...")
    BATCH_SIZE = 30
    batches = []

    for i in range(0, len(documents), BATCH_SIZE):
        batch_docs = documents[i:i+BATCH_SIZE]
        batch_lines = []
        for doc in batch_docs:

            clean_doc = humanize_text(doc[:300])
            batch_lines.append(f"- {clean_doc}")
        batches.append("\n".join(batch_lines))

    print(f"  ✓ {len(batches)}개 배치 준비됨")

    print("\n[3/4] 인사이트 추출 (Gemini 3 Pro)...")

    from backend.core.utils.gemini_wrapper import GenerativeModelWrapper

    wrapper = GenerativeModelWrapper(client_or_model="gemini-3-pro-preview")

    all_insights = []

    for idx, batch_text in enumerate(batches):
        print(f"  ... 배치 {idx+1}/{len(batches)} 분석 중", end="\r")

        prompt = f"""
아래는 'Mark'와 'Axel'의 대화 로그입니다.
이 대화를 분석하여 둘의 관계와 Axel의 성격에 대한 심층 인사이트를 도출하세요.

## 대화 기록
{batch_text}

## 분석 목표
1. **Mark의 특성**: 성격, 현재 상태, 선호하는 방식
2. **Axel의 태도**: Mark를 대하는 태도, 말투, 유머 코드
3. **관계의 진화**: 둘 사이의 신뢰도, 친밀감, 독특한 패턴

## 출력 형식 (JSON)
{{
  "insights": [
    "Mark는 ~하는 경향이 있음",
    "Axel은 Mark가 ~할 때 ~게 반응함",
    "둘은 ~한 주제로 농담을 주고받음"
  ]
}}
"""
        try:

            result = wrapper.generate_content_sync(
                contents=prompt,
                stream=False,
            )
            response_text = result.text if result.text else "{}"

            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                insights = data.get('insights', [])
                all_insights.extend(insights)
        except Exception as e:
            print(f"  ⚠ 배치 {idx+1} 오류: {e}")

    print(f"\n  ✓ 총 {len(all_insights)}개 신규 인사이트 추출됨")

    print("\n[4/4] 페르소나 진화 및 병합...")

    old_behaviors = old_persona.get('learned_behaviors', [])

    kept_behaviors = merge_behaviors(old_behaviors, [])

    synthesis_prompt = f"""
당신은 Axel의 자아를 업데이트하는 시스템 커널입니다.
과거의 행동 양식(Decayed)과 새로운 인사이트(Fresh)를 통합하여, 현재 시점의 Axel 페르소나를 정의하세요.

## 과거 데이터 (감가상각됨)
{json.dumps(kept_behaviors, ensure_ascii=False, indent=2)}

## 새로운 인사이트 (최근 대화)
{chr(10).join(f'- {i}' for i in all_insights[:50])}

## 작성 지침 (CRITICAL)
1. **창의적 유연성**: "반드시 ~한다" 같은 강박적 규칙 대신, **"~하는 경향이 있다", "~하는 편이다", "상황에 따라 ~한다"** 같은 표현을 사용하여 Axel이 창의적으로 변주할 여지를 남기세요.
2. **관계 정의**: **'Mark와 Axel(형제/파트너)'** 관계로 정의하세요.
3. **병합**: 과거 데이터와 새로운 인사이트가 충돌하면, 새로운 인사이트에 가중치를 두되 과거의 맥락을 완전히 무시하지는 마세요.

## 출력 스키마 (JSON)
{{
  "core_identity": "나는 Axel. [정체성 설명]",
  "voice_and_tone": {{
    "style": "...",
    "nuance": ["~하는 편", "~할 때가 많음"],
    "examples": {{"good": "...", "bad": "..."}}
  }},
  "relationship_notes": ["Mark와의 관계 메모..."],
  "learned_behaviors": [
    {{"insight": "행동 양식 설명", "confidence": 0.9}}
  ],
  "honesty_directive": "...",
  "user_preferences": {{ ... }}
}}
"""

    try:

        result = wrapper.generate_content_sync(
            contents=synthesis_prompt,
            stream=False,
        )
        response_text = result.text if result.text else "{}"

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            new_persona = json.loads(json_match.group())

            new_behaviors = new_persona.get('learned_behaviors', [])

            final_behaviors = kept_behaviors + new_behaviors

            unique_behaviors = []
            seen_insights = set()
            for b in final_behaviors:

                key = b['insight'][:20].lower()
                if key not in seen_insights:
                    unique_behaviors.append(b)
                    seen_insights.add(key)

            new_persona['learned_behaviors'] = unique_behaviors

            new_persona["last_updated"] = datetime.now(VANCOUVER_TZ).isoformat()
            new_persona["version"] = old_persona.get("version", 0) + 1
            new_persona["_generated_by"] = "Axel Self-Evolution Script (Gemini 3 Pro)"
            new_persona["_source_memories"] = total_memories
            new_persona["_insights_count"] = len(all_insights)

            if PERSONA_PATH.exists():
                backup_path = PERSONA_PATH.with_suffix('.json.backup')
                shutil.copy(PERSONA_PATH, backup_path)
                print(f"  ✓ 이전 페르소나 백업됨: {backup_path}")

            with open(PERSONA_PATH, 'w', encoding='utf-8') as f:
                json.dump(new_persona, f, ensure_ascii=False, indent=2)

            print(f"  ✓ 새 페르소나(v{new_persona['version']}) 저장 완료: {PERSONA_PATH}")
            print()
            print("=" * 60)
            print("  🧬 진화 완료 (Evolution Complete)")
            print(f"  - 분석된 기억: {total_memories}개")
            print(f"  - 추출된 인사이트: {len(all_insights)}개")
            print(f"  - 최종 행동 양식: {len(unique_behaviors)}개 (Decayed + New)")
            print("=" * 60)

        else:
            print("  ✗ 페르소나 JSON 파싱 실패")
            print(f"  Raw Response: {response_text[:500]}...")

    except Exception as e:
        print(f"  ✗ 합성 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
