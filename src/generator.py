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


def _parse_article_json(text: str) -> dict:
    """記事生成のJSONレスポンスを補修してパースする。

    Geminiの構造化出力でも稀にJSONが壊れることがあるため、
    複数段階で補修を試みる。
    """
    import re as _re

    # 1. そのままパース
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. strict=Falseで再試行（制御文字を許容）
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    # 3. ```json ブロックの中身だけ抽出
    code_match = _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if code_match:
        inner = code_match.group(1)
        try:
            return json.loads(inner, strict=False)
        except json.JSONDecodeError:
            pass

    # 4. title/body/tagsを正規表現で個別に抽出（最終手段）
    title_match = _re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)
    body_match = _re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', text, _re.DOTALL)
    tags_match = _re.search(r'"tags"\s*:\s*\[(.*?)\]', text, _re.DOTALL)

    if title_match and body_match:
        try:
            title = json.loads(f'"{title_match.group(1)}"')
            body = json.loads(f'"{body_match.group(1)}"')
        except Exception:
            title = title_match.group(1).replace("\\n", "\n").replace('\\"', '"')
            body = body_match.group(1).replace("\\n", "\n").replace('\\"', '"')

        tags = []
        if tags_match:
            for m in _re.findall(r'"((?:[^"\\]|\\.)*)"', tags_match.group(1)):
                tags.append(m.replace("\\n", "\n").replace('\\"', '"'))

        return {"title": title, "body": body, "tags": tags}

    raise ValueError(
        "AIの応答からJSONを取り出せませんでした。"
        "もう一度お試しください。続く場合は文字数を減らしてみてください。"
    )


def _format_plan_instruction(plan: dict | None) -> str:
    """進め方プランを記事生成への指示文に整形する。"""
    if not plan:
        return ""

    evidence_list = "\n".join(f"  - {e}" for e in plan.get("evidence_to_use", []))

    return f"""【★承認済み進め方プラン — 必ずこの方針で書く】
- 核心メッセージ: {plan.get("main_message", "")}
- 冒頭フックの方向性: {plan.get("hook_direction", "")}
- 中核論理・展開: {plan.get("core_argument", "")}
- 使う素材:
{evidence_list}
- 比喩・ストーリー: {plan.get("key_metaphor", "")}
- 締めくくり: {plan.get("closing_action", "")}
- 著者プロフィールの活かし方: {plan.get("author_angle", "")}
- 読後の余韻: {plan.get("expected_impact", "")}

★このプランはユーザーが承認済み。プランの方向性から外れないこと。
"""


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
    ctas: list = None,
    article_plan: dict = None,
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

    cta_instruction = ""
    if ctas:
        cta_blocks = []
        for cta in ctas:
            cta_blocks.append(
                f"- 【{cta['position']}に配置】 誘導文: {cta['label']}"
            )
        cta_instruction = f"""【★CTA・誘導文の挿入 — 必ず指定位置に挿入】
以下の誘導文を記事の指定位置に**必ず**挿入してください。

{chr(10).join(cta_blocks)}

【挿入のルール】
- 「冒頭」: 自己紹介の直後、本論に入る前
- 「中盤」: 問題提起から解決策に移る境目（A→Cの間）
- 「末尾」: 記事の締めの直前
- 誘導文は前後の文脈に**自然に繋げる**こと（押し売り感を出さない）
- URLは入れない。ユーザーが後でnote上で手動でリンクを貼るため、誘導文のみを入れる
- 流れを切らないよう、CTA前後で文章を繋ぐ一文を入れる
- 形式の例（自然な流れの中に組み込む）:

  本文の流れの中で…
  「もしこの記事が役に立ったら、{{誘導文}}。きっと役に立つはずです。」
  本文が続く…
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

{cta_instruction}

{_format_plan_instruction(article_plan)}

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
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        finish_reason = ""
        if response.candidates:
            finish_reason = str(response.candidates[0].finish_reason)
        raise ValueError(
            f"AIから空の応答が返りました（finish_reason={finish_reason}）。"
            "もう一度お試しください。続く場合は文字数を減らすか、コンセプトを短くしてください。"
        )

    result = _parse_article_json(text)
    result["one_hack"] = {
        "idea": research.get("suggested_one_idea", ""),
        "emotion": research.get("suggested_one_emotion", ""),
        "story": research.get("suggested_one_story", ""),
        "action": research.get("suggested_one_action", ""),
    }
    result["genre"] = genre

    return result
