"""
品質チェックモジュール — Gemini Flash

生成された記事をONE HACKの基準でチェックし、
スコアと改善点を返す。
"""

import json
from google import genai
from google.genai import types


def check_quality(title: str, body: str, concept: str, api_key: str) -> dict:
    """
    記事の品質をチェックする。

    Returns:
        {"score": int, "passed": bool, "issues": str, "suggestion": str}
    """
    client = genai.Client(api_key=api_key)

    prompt = f"""以下のnote記事を品質チェックしてください。

【記事】
タイトル: {title}
本文: {body[:3000]}

【コンセプト】
{concept}

【チェック基準 — 全て満たして90点以上】
1. 悪いハテナがゼロか（文章の意味が通じない、論理が飛躍しているものがないか）
2. 良いハテナが1つあるか（「え、どういうこと？もっと知りたい」と前のめりになるもの）
3. 読者のネガティブ感情に寄り添っているか（頭ごなしに否定していないか）
4. 比喩が日常テーマで直感的か
5. 専門用語に平易な補足があるか
6. 読者の前提を決めつけず一般論として提示しているか
7. 煽り・押しつけがないか
8. コンセプトからブレてないか
9. H→A→C→Kの流れが自然か
10. 「安心してください」等の一方的声かけをしていないか
11. 「あなたの〇〇が悪いわけではありません」等の決めつけをしていないか
12. 「むしろ」を使っていないか
13. フック単体で「何を？」という悪いハテナが出ていないか
14. 目的語の欠落がないか（初出時は必ず目的語を明示）

【高評価パターン】
A. 一般論を起点に逆説・矛盾を突く
B. 専門家の概念を紹介してから独自解釈に転換
C. 日常的な比喩で専門用語を翻訳
D. 読者の前のめり感を引き出すフック

【出力形式】JSONのみ。
{{"score": 0-100, "passed": true/false, "issues": "問題点", "suggestion": "改善提案"}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=1000,
        ),
    )

    raw = response.text.strip()
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()

    result = json.loads(raw)
    result["passed"] = result.get("score", 0) >= 90

    return result
