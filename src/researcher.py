"""
リサーチモジュール — Gemini Flash + Google Search Grounding

コンセプトに基づいて海外のエビデンス・研究・事例をリサーチし、
記事に使える素材を構造化して返す。
"""

import json
from google import genai
from google.genai import types


def research_topic(concept: str, persona: str, api_key: str) -> dict:
    """
    コンセプトに基づいてリサーチを実行する。

    Returns:
        {
            "evidence": [{"title": str, "summary": str, "source": str}, ...],
            "key_insight": str,
            "suggested_one_idea": str,
            "suggested_one_emotion": str,
            "suggested_one_story": str,
            "suggested_one_action": str,
            "expert_quotes": [{"expert": str, "quote": str, "context": str}, ...],
        }
    """
    client = genai.Client(api_key=api_key)

    prompt = f"""あなたは優秀なリサーチャーです。以下のコンセプトについて、海外の研究・エビデンス・専門家の知見をリサーチしてください。

【コンセプト】
{concept}

【届けたいペルソナ】
{persona}

【リサーチ指示】
1. このコンセプトに関連する海外の研究・論文・書籍から、3〜5個のエビデンスを見つけてください
2. 有名な心理学者・研究者・セールスライターの知見があれば引用してください
3. ペルソナが「なるほど！」と思えるような意外な事実や逆説を探してください
4. このコンセプトで記事を書く場合のONE HACK要素を提案してください

【重要】
- 実在する研究・書籍・人物のみ引用すること（捏造禁止）
- 出典が不明確なものは「一般的に〜と言われている」と明記
- 日本語で回答

【出力形式】以下のJSON形式で出力してください。JSONのみ。
{{
    "evidence": [
        {{"title": "研究/書籍名", "summary": "要約（2-3文）", "source": "著者・出典"}}
    ],
    "key_insight": "この記事の核となる洞察（1文）",
    "suggested_one_idea": "伝えるべき1つのアイデア",
    "suggested_one_emotion": "揺さぶるべき1つの感情",
    "suggested_one_story": "使うべき比喩・ストーリー",
    "suggested_one_action": "読者に促す1つの行動",
    "expert_quotes": [
        {{"expert": "専門家名", "quote": "引用・知見", "context": "どの文脈で使えるか"}}
    ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )

    raw = response.text.strip()

    # JSONを抽出
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()
        if not raw:
            raw = response.text.strip().split("```")[1].strip()

    return json.loads(raw)
