"""
リサーチモジュール — Gemini 2.5 Flash + Google Search Grounding

実際にGoogle検索を叩いて、海外の研究・論文・記事を引いてくる。
Geminiの内部知識ではなく、リアルタイムWeb検索に基づいたリサーチ。
"""

import json
import re
from google import genai
from google.genai import types


def research_topic(concept: str, persona: str, api_key: str) -> dict:
    """
    コンセプトに基づいてGoogle検索でリサーチを実行する。

    Returns:
        {
            "evidence": [{"title": str, "summary": str, "source": str}, ...],
            "key_insight": str,
            "suggested_one_idea": str,
            "suggested_one_emotion": str,
            "suggested_one_story": str,
            "suggested_one_action": str,
            "expert_quotes": [{"expert": str, "quote": str, "context": str}, ...],
            "sources": [{"title": str, "uri": str}, ...]  # グラウンディングで参照した実URL
        }
    """
    client = genai.Client(api_key=api_key)

    prompt = f"""あなたは優秀なリサーチャーです。Google検索で実際に調べて、以下のコンセプトに関する「海外の研究・論文・専門家の知見」を集めてください。

【コンセプト】
{concept}

【届けたいペルソナ】
{persona}

【検索の方針】
1. **英語で検索**して、海外の一次情報（英語の論文・学術サイト・研究者の記事）にアクセスする
2. 日本語の二次情報（まとめサイト、ブログ）は**避ける**
3. 以下の情報源を優先：
   - PubMed、Google Scholar、ResearchGate などの学術データベース
   - 有名大学の心理学部サイト（Harvard、Stanford、Yale 等）
   - 著名心理学者・研究者の個人サイトやTED Talks
   - APA（米国心理学会）、NIH などの公的機関
4. 検索クエリは英語で、"{concept}"に関連する専門用語を使う

【リサーチ指示】
1. 実際にGoogle検索した結果から、3〜5個のエビデンスを集める
2. **検索で実在を確認した研究・書籍・人物のみ**引用すること（絶対に捏造しない）
3. 出典URLを記録する
4. ペルソナが「なるほど！」と思える意外な事実や逆説を探す
5. このコンセプトで記事を書く場合のONE HACK要素を提案する

【絶対NG】
- Google検索で確認できない論文・書籍を引用すること
- 著者名や出版年を推測で埋めること
- 日本語のまとめサイトを一次情報として扱うこと

【出力形式】最後に以下のJSON形式のみを出力してください。他の説明文は不要。
```json
{{
    "evidence": [
        {{"title": "研究/書籍の英語タイトル（実在するもの）", "summary": "日本語で要約（2-3文）", "source": "著者名・出版年・出典URL"}}
    ],
    "key_insight": "この記事の核となる洞察（日本語1文）",
    "suggested_one_idea": "伝えるべき1つのアイデア（日本語）",
    "suggested_one_emotion": "揺さぶるべき1つの感情（日本語）",
    "suggested_one_story": "使うべき比喩・ストーリー（日本語）",
    "suggested_one_action": "読者に促す1つの行動（日本語）",
    "expert_quotes": [
        {{"expert": "実在する専門家の名前", "quote": "その人が実際に言った/書いた内容の日本語訳", "context": "どの文脈で使えるか"}}
    ]
}}
```
"""

    # Google検索グラウンディングを有効化
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.7,
        ),
    )

    raw = response.text.strip()

    # JSONを抽出（grounding使用時はJSON mode不可なのでテキストから抽出）
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # ```がない場合は最後の{...}ブロックを探す
        json_match = re.search(r"(\{[\s\S]*\})", raw)
        if not json_match:
            raise ValueError(f"JSONが抽出できませんでした: {raw[:500]}")
        json_str = json_match.group(1)

    result = json.loads(json_str)

    # グラウンディングで参照した実URLを抽出
    sources = []
    if response.candidates and response.candidates[0].grounding_metadata:
        metadata = response.candidates[0].grounding_metadata
        if metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if chunk.web:
                    sources.append({
                        "title": chunk.web.title or "",
                        "uri": chunk.web.uri or "",
                    })

    result["sources"] = sources
    return result
