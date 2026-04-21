"""
記事生成モジュール — Gemini Flash + ONE HACKモデル

チェーンプロンプト方式:
  1. リサーチ結果（エビデンス）
  2. ONE HACKモデル（構成）
  3. トーン設定（ユーザー指定）
→ Gemini Flashで記事を生成
"""

import json
from pathlib import Path

from google import genai
from google.genai import types

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def load_knowledge() -> dict[str, str]:
    """ナレッジファイルを読み込む"""
    knowledge = {}
    for f in KNOWLEDGE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").strip()
        if content:
            knowledge[f.stem] = content
    return knowledge


def _build_tone_instruction(tone_aggressive: int, tone_blunt: bool) -> str:
    """トーン設定から指示文を生成する"""
    if tone_aggressive <= 25:
        aggr = "とても優しく包み込むようなトーンで書いてください。読者を責めず、寄り添い、温かく語りかけます。"
    elif tone_aggressive <= 50:
        aggr = "基本的に優しいトーンですが、核心部分では少し踏み込んだ表現を使います。"
    elif tone_aggressive <= 75:
        aggr = "読者の心に刺さる強めの表現を適度に使います。ただし攻撃的にはならず、愛のある厳しさです。"
    else:
        aggr = "読者の常識を揺さぶる挑発的なフックを使います。ただし人格攻撃は絶対にしません。構造や常識への挑戦です。"

    if tone_blunt:
        blunt = "伝えたいことはグサッとストレートに言い切ります。遠回しにせず、核心を突く一文を必ず入れてください。"
    else:
        blunt = "伝えたいことは比喩やストーリーで柔らかく包んで伝えます。直接的な表現は避け、読者が自分で気づくように導きます。"

    return f"""【トーン指定】
{aggr}
{blunt}
"""


def generate_article(
    concept: str,
    persona: str,
    research: dict,
    tone_aggressive: int = 30,
    tone_blunt: bool = False,
    word_count: int = 2000,
    writer_style: str = "",
    api_key: str = "",
) -> dict:
    """
    リサーチ結果に基づいてONE HACK構成の記事を生成する。

    Returns:
        {"title": str, "body": str, "tags": list[str], "one_hack": dict}
    """
    client = genai.Client(api_key=api_key)

    knowledge = load_knowledge()
    hack_model = knowledge.get("ONE_HACK_model", "")
    note_structure = knowledge.get("売れるnote構成", "")

    # リサーチ結果を整形
    evidence_text = ""
    for i, ev in enumerate(research.get("evidence", []), 1):
        evidence_text += f"{i}. {ev.get('title', '')} — {ev.get('summary', '')} (出典: {ev.get('source', '不明')})\n"

    expert_text = ""
    for eq in research.get("expert_quotes", []):
        expert_text += f"- {eq.get('expert', '')}: 「{eq.get('quote', '')}」({eq.get('context', '')})\n"

    tone_instruction = _build_tone_instruction(tone_aggressive, tone_blunt)

    style_instruction = ""
    if writer_style:
        style_instruction = f"""【ライティングスタイル参考】
{writer_style}のような文体で書いてください。そのライターの特徴的な語り口、リズム、読者との距離感を参考にしてください。
"""

    system_prompt = f"""あなたは超一流のコピーライターです。以下のナレッジに基づいて記事を書きます。

【構成モデル — ONE HACK】
{hack_model}

【note記事の構成】
{note_structure}

{tone_instruction}

{style_instruction}

【★H→A→C→Kの流れを厳密に守ること。ラベルは出さない★】
【★文体の禁止事項】
- 「むしろ」禁止
- 「考えてみてください」→「想像してみてください」
- 「いやいや」禁止
- 読者の状況を憶測で決めつけない
"""

    user_prompt = f"""以下の素材でnote記事を書いてください。
★文字数は{word_count}文字以上を厳守。各セクション（H/A/C/K）をしっかり展開すること。

【コンセプト】
{concept}

【届けたいペルソナ】
{persona}

【リサーチで見つかったエビデンス】
{evidence_text}

【専門家の知見】
{expert_text}

【ONE HACK要素】
- ONE idea: {research.get('suggested_one_idea', concept)}
- ONE emotion: {research.get('suggested_one_emotion', '気づき')}
- ONE story: {research.get('suggested_one_story', '')}
- ONE action: {research.get('suggested_one_action', '記事の内容を1つ試してみる')}
- Key insight: {research.get('key_insight', '')}

【構成指示】
H（Hook）: 相反する概念の結合で謎を作る。2-3行。
A（Ask）: 客観的に一般論を提示→構造に目を向けさせる。決めつけない。
C（Core）: エビデンスを使ってアハ体験。比喩で直感的に。
K（Key）: 小さな一歩を提案して着地。

【出力形式】JSONのみ。
{{"title": "記事タイトル", "body": "記事本文", "tags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"]}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=system_prompt + "\n\n" + user_prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=4096,
        ),
    )

    raw = response.text.strip()
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0].strip()
        if not raw:
            raw = response.text.strip().split("```")[1].strip()

    result = json.loads(raw)
    result["one_hack"] = {
        "idea": research.get("suggested_one_idea", ""),
        "emotion": research.get("suggested_one_emotion", ""),
        "story": research.get("suggested_one_story", ""),
        "action": research.get("suggested_one_action", ""),
    }

    return result
