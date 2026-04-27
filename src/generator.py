"""
記事生成モジュール — Gemini 2.5 Flash + ONE HACKモデル

ジャンル別にトーンを切り替え、構造化出力でJSON parseエラーを防止。
"""

import json
from pathlib import Path

from google import genai
from google.genai import types

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


GENRE_TONE = {
    "psychology": """【ジャンルの方針: 心理学・ビジネス系】
- エビデンスや専門家の知見を起点に「なるほど」を作る
- ロジカルな構造を見せつつ、読者の感情にも寄り添う
- 「研究によると〜」「○○博士は〜と語った」など、知的好奇心を刺激""",

    "spiritual": """【ジャンルの方針: スピリチュアル・直感系】
- 純粋な論文・統計だけに頼らない。だが**完全に非論理的にもしない**
- 「未科学」「疑似科学」と呼ばれる領域を扱う：量子物理学と意識、ニューロセオロジー、ホロトロピック、HeartMath、ゲシュタルト療法、トランスパーソナル心理学、ノエティック・サイエンス（IONS）、近年の臨死体験研究など
- 海外の霊性指導者の非論理的な智恵（エックハルト・トール、ラム・ダス、バイロン・ケイティ、ルーミー、老子）と、それを論理的・科学的に再解釈した試み（ジョー・ディスペンザ、グレッグ・ブレイデン、ブルース・リプトン）の**両方を扱う**
- 詩的・瞑想的でありつつ、ロジカル読者も納得する「橋渡し」を意識する
- 「証明」ではなく「響き」と「整合性」で導く。比喩は自然・季節・宇宙・身体感覚から
- 「研究では〜」も使ってよいが、論理に閉じこめない。「古来の教え + 最新の科学が同じことを指している」という構造が理想""",

    "essay": """【ジャンルの方針: エッセイ・日常系】
- 個人の視点・日常の機微を大事にする
- 統計やエビデンスは不要。**情緒と気づきが主役**
- 詩人・作家・哲学者の言葉を1〜2個引用する程度
- 比喩は日常の風景（コーヒー、雨、電車、台所）から
- 結論を急がず、余韻を残す""",
}


def load_knowledge() -> dict[str, str]:
    knowledge = {}
    for f in KNOWLEDGE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").strip()
        if content:
            knowledge[f.stem] = content
    return knowledge


def _build_tone_instruction(tone_aggressive: int, tone_blunt: bool) -> str:
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

    return f"""【トーン指定】\n{aggr}\n{blunt}\n"""


_ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title", "body", "tags"],
}


def generate_article(
    concept: str,
    persona: str,
    research: dict,
    tone_aggressive: int = 30,
    tone_blunt: bool = False,
    word_count: int = 2000,
    writer_style: str = "",
    api_key: str = "",
    genre: str = "psychology",
    author_identity: str = "",
    author_pain: str = "",
) -> dict:
    """ONE HACK構成 + ジャンル別トーンで記事を生成。"""
    client = genai.Client(api_key=api_key)

    knowledge = load_knowledge()
    hack_model = knowledge.get("ONE_HACK_model", "")
    note_structure = knowledge.get("売れるnote構成", "")

    evidence_text = ""
    for i, ev in enumerate(research.get("evidence", []), 1):
        evidence_text += f"{i}. {ev.get('title', '')} — {ev.get('summary', '')} (出典: {ev.get('source', '不明')})\n"

    expert_text = ""
    for eq in research.get("expert_quotes", []):
        expert_text += f"- {eq.get('expert', '')}: 「{eq.get('quote', '')}」({eq.get('context', '')})\n"

    tone_instruction = _build_tone_instruction(tone_aggressive, tone_blunt)
    genre_tone = GENRE_TONE.get(genre, GENRE_TONE["psychology"])

    style_instruction = ""
    if writer_style:
        style_instruction = f"【ライティングスタイル参考】\n{writer_style}のような文体で書いてください。\n"

    author_instruction = ""
    if author_identity or author_pain:
        author_instruction = f"""【★著者のプロフィール — 記事に必ず反映する】
- 著者の発信内容: {author_identity or "（未入力）"}
- 著者の過去の悩み・痛み: {author_pain or "（未入力）"}

★この著者の視点から書くこと。
★著者が経験した痛みを、ペルソナの痛みと重ねて語る部分を必ず1箇所入れる。
★著者が発信していることと、記事のテーマを繋げる。著者の独自視点で再解釈する。
★ただし、自己アピールにならないように。「私の経験から言うと…」程度の自然な織り込み方で。
"""

    system_prompt = f"""あなたは超一流のコピーライターです。以下のナレッジに基づいて記事を書きます。

【構成モデル — ONE HACK】
{hack_model}

【note記事の構成】
{note_structure}

{genre_tone}

{tone_instruction}

{style_instruction}

{author_instruction}

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

【リサーチで見つかった素材】
{evidence_text}

【専門家・著名人の知見】
{expert_text}

【ONE HACK要素】
- ONE idea: {research.get('suggested_one_idea', concept)}
- ONE emotion: {research.get('suggested_one_emotion', '気づき')}
- ONE story: {research.get('suggested_one_story', '')}
- ONE action: {research.get('suggested_one_action', '記事の内容を1つ試してみる')}
- Key insight: {research.get('key_insight', '')}

【構成指示】
H（Hook）: 相反する概念の結合で謎を作る。2-3行。
A（Ask）: 客観的に提示→構造に目を向けさせる。決めつけない。
C（Core）: 素材を使ってアハ体験。比喩で直感的に。
K（Key）: 小さな一歩を提案して着地。

タイトル、本文、タグ5個を出力してください。
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=system_prompt + "\n\n" + user_prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=_ARTICLE_SCHEMA,
        ),
    )

    result = json.loads(response.text)
    result["one_hack"] = {
        "idea": research.get("suggested_one_idea", ""),
        "emotion": research.get("suggested_one_emotion", ""),
        "story": research.get("suggested_one_story", ""),
        "action": research.get("suggested_one_action", ""),
    }
    result["genre"] = genre

    return result
