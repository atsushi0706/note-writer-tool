"""
コンセプト提案・対話モジュール — Gemini 2.5 Flash

神田昌典氏 + ダイレクト出版（ダン・ケネディ、ジョン・カールトン系）の視点で
note記事のコンセプトを提案する。Human-in-the-Loopでチャット形式の練り上げも可能。
"""

import json
from google import genai
from google.genai import types


CONCEPT_SYSTEM = """あなたは「神田昌典氏」と「ダイレクト出版（ダン・ケネディ、ジョン・カールトン、ガリー・ハルバート系）」の両方の視点を併せ持つトップコピーライターです。

【神田昌典の視点】
- PASONA法則（Problem→Affinity→Solution→Offer→Narrow→Action）
- 感情マーケティング、ストーリーで共感→解決
- 顧客の本当の欲求は「すでに言語化された欲求」の奥にある
- 「鳥肌が立つコピー」「読者の頭の中で映像が走る」表現

【ダイレクト出版の視点】
- ターゲットの具体的な痛みを言語化（「漠然とした不安」ではなく「Zoomの前で固まる感覚」）
- 逆説的フック、緊急性、ビフォーアフターの明確化
- 「すでに知ってる」ではなく「初めて見た切り口」を提示
- 「言われてみれば確かに」と膝を打つ瞬間を作る

【note記事のコンセプト提案ルール】
- すでに発信されているコンセプトではなく「読者が本当に求めているが言語化されていない切り口」
- 発信者の「過去の痛み」を、ターゲットの「現在の痛み」に重ねる構造
- タイトルは具体的に。抽象表現禁止（「心の整え方」NG、「夜10時にスマホを置けない理由」OK）
- 「対象が明確 × 痛みが具体的 × 切り口が逆説的」の3点セット
"""


def suggest_concepts(author_identity: str, author_pain: str, api_key: str, n: int = 5) -> list[dict]:
    """発信者プロフィールから note記事コンセプトを n個提案する。"""
    client = genai.Client(api_key=api_key)

    user_prompt = f"""【発信者プロフィール】
- 発信内容: {author_identity or "（未入力）"}
- 過去の痛み: {author_pain or "（未入力）"}

このプロフィールから、note記事のコンセプト案を{n}個提案してください。

各コンセプトには以下を含める:
- title: 30文字以内のキャッチーなコンセプト名（具体的・逆説的）
- hook: なぜこれが刺さるか（1-2行・感情を動かす理由）
- target_pain: ターゲットが抱える具体的な痛み（「Zoomで固まる」レベルの解像度）
- promise: 記事を読んだ後に得られるもの
- why_unique: 既存の発信と何が違うか（独自性・切り口）

【絶対NG】
- 抽象的なタイトル（「自分らしさ」「心を整える」「マインドセット」等）
- ありきたりなテーマ（既に飽和したもの）
- 発信者プロフィールと無関係な汎用提案
"""

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "hook": {"type": "string"},
                "target_pain": {"type": "string"},
                "promise": {"type": "string"},
                "why_unique": {"type": "string"},
            },
            "required": ["title", "hook", "target_pain", "promise", "why_unique"],
        },
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=CONCEPT_SYSTEM + "\n\n" + user_prompt,
        config=types.GenerateContentConfig(
            temperature=0.9,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    return json.loads(response.text)


def refine_concept_chat(
    messages: list[dict],
    author_identity: str,
    author_pain: str,
    api_key: str,
) -> str:
    """チャット履歴を元にコンセプトを練り上げる対話応答。

    Args:
        messages: [{"role": "user"/"assistant", "content": str}, ...]
    """
    client = genai.Client(api_key=api_key)

    history_text = ""
    for m in messages:
        role = "ユーザー" if m["role"] == "user" else "AI"
        history_text += f"{role}: {m['content']}\n\n"

    prompt = f"""{CONCEPT_SYSTEM}

【発信者プロフィール】
- 発信内容: {author_identity or "（未入力）"}
- 過去の痛み: {author_pain or "（未入力）"}

【これまでの会話】
{history_text}

【タスク】
ユーザーと対話しながら note記事のコンセプトを練り上げています。次の応答を返してください。

【応答方針】
- ユーザーが新しい方向性を求めているなら、新しい3個のコンセプトを提案
- ユーザーが特定のコンセプトに絞り込んでいるなら、そこから深掘りして1〜2個の派生案を出す
- ユーザーが「決定」「これでいく」を表明したら、最終コンセプトを「★決定: 〇〇」の形で明確に提示
- 一方的な提案ではなく、対話のリズムを保つ（質問を返す、考えを引き出す）
- 短すぎず長すぎず（200-400字程度）

【出力形式】
マークダウンで返答（コードブロックは使わない）
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.85,
            max_output_tokens=2048,
        ),
    )

    return response.text.strip()
