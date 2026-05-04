"""
品質チェックモジュール — Gemini Flash

生成された記事を基準でチェックし、スコアと改善点を返す。
構造化出力(response_schema)で JSON エラーを防止。
"""

import json
from google import genai
from google.genai import types


_QUALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "issues": {"type": "string"},
        "suggestion": {"type": "string"},
    },
    "required": ["score", "issues", "suggestion"],
}


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

scoreは0-100の整数、issuesは問題点の文字列、suggestionは改善提案の文字列で返してください。
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=_QUALITY_SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("AIから空の応答が返りました。もう一度お試しください。")

    result = _parse_quality(text)
    result["passed"] = result.get("score", 0) >= 90
    return result


def _parse_quality(text: str) -> dict:
    """品質チェックのJSON応答を補修してパースする。

    完全に壊れていてもスコアだけは正規表現で抽出するフォールバックを持つ。
    """
    import re as _re

    # 1. 直接パース
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. strict=False
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    # 3. コードブロック抽出
    code_match = _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if code_match:
        try:
            return json.loads(code_match.group(1), strict=False)
        except Exception:
            pass

    # 4. 最終手段: スコア・issues・suggestionを正規表現で個別抽出
    score_match = _re.search(r'"score"\s*:\s*(\d+)', text)
    issues_match = _re.search(r'"issues"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)
    suggestion_match = _re.search(r'"suggestion"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)

    if score_match:
        return {
            "score": int(score_match.group(1)),
            "issues": (issues_match.group(1).replace("\\n", "\n").replace('\\"', '"')
                       if issues_match else "JSON応答が一部壊れていましたが、スコアは取得できました。"),
            "suggestion": (suggestion_match.group(1).replace("\\n", "\n").replace('\\"', '"')
                           if suggestion_match else ""),
        }

    raise ValueError("品質チェックの応答を解釈できませんでした。再度お試しください。")
