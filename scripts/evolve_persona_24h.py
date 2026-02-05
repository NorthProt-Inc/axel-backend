#!/usr/bin/env python3

import json
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from backend.config import PERSONA_PATH, DATA_ROOT, SQLITE_MEMORY_PATH
from backend.core.utils.timezone import VANCOUVER_TZ
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
    print("  🧬 페르소나 24시간 진화 (Incremental Evolution)")
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

    print("\n[1/4] 최근 24시간 기억 로딩 (sqlite_memory.db)...")
    import sqlite3

    cutoff_time = datetime.now(VANCOUVER_TZ) - timedelta(hours=24)
    cutoff_iso = cutoff_time.strftime('%Y-%m-%dT%H:%M:%S')

    conn = sqlite3.connect(str(SQLITE_MEMORY_PATH))
    cur = conn.cursor()

    cur.execute('''
        SELECT m.role, m.content, m.timestamp, s.summary
        FROM messages m
        LEFT JOIN sessions s ON m.session_id = s.session_id
        WHERE m.timestamp >= ?
        ORDER BY m.timestamp DESC
        LIMIT 500
    ''', (cutoff_iso,))

    rows = cur.fetchall()
    conn.close()

    documents = []
    for role, content, timestamp, summary in rows:
        if content:
            human_role = humanize_role(role)
            documents.append(f"{human_role}: {content}")

    total_memories = len(documents)
    print(f"  ✓ 총 {total_memories}개 기억 로드 완료 (24시간)")

    if total_memories == 0:
        print("  ! 최근 24시간 내 기억이 없습니다. 종료.")
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
    {{"insight": "Mark는 ~하는 경향이 있음", "confidence": 0.9}},
    {{"insight": "Axel은 Mark가 ~할 때 ~게 반응함", "confidence": 0.85}},
    {{"insight": "둘은 ~한 주제로 농담을 주고받음", "confidence": 0.8}}
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

    new_behaviors = []
    for insight_obj in all_insights:
        if isinstance(insight_obj, dict):
            insight_text = insight_obj.get("insight", "")
            confidence = insight_obj.get("confidence", 0.9)
        else:
            insight_text = str(insight_obj)
            confidence = 0.9

        if insight_text:
            new_behaviors.append({
                "insight": insight_text,
                "confidence": confidence,
                "learned_at": datetime.now(VANCOUVER_TZ).isoformat()
            })

    final_behaviors = kept_behaviors + new_behaviors

    unique_behaviors = []
    seen_insights = set()
    for b in final_behaviors:

        key = b['insight'][:20].lower()
        if key not in seen_insights:
            unique_behaviors.append(b)
            seen_insights.add(key)

    old_persona['learned_behaviors'] = unique_behaviors
    old_persona["last_updated"] = datetime.now(VANCOUVER_TZ).isoformat()
    old_persona["version"] = old_persona.get("version", 0) + 1
    old_persona["_last_evolution"] = "24h incremental"
    old_persona["_source_memories"] = total_memories
    old_persona["_insights_count"] = len(all_insights)

    if PERSONA_PATH.exists():
        backup_path = PERSONA_PATH.with_suffix('.json.backup')
        shutil.copy(PERSONA_PATH, backup_path)
        print(f"  ✓ 이전 페르소나 백업됨: {backup_path}")

    with open(PERSONA_PATH, 'w', encoding='utf-8') as f:
        json.dump(old_persona, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 새 페르소나(v{old_persona['version']}) 저장 완료: {PERSONA_PATH}")
    print()
    print("=" * 60)
    print("  🧬 진화 완료 (Evolution Complete)")
    print(f"  - 분석된 기억: {total_memories}개 (24시간)")
    print(f"  - 추출된 인사이트: {len(all_insights)}개")
    print(f"  - 최종 행동 양식: {len(unique_behaviors)}개 (Decayed + New)")
    print("=" * 60)

if __name__ == "__main__":
    main()
