"""
note記事ライターツール — Streamlit UI

コンセプト入力 → リサーチ → 記事生成 → コピーしてnoteに貼り付け
全てGemini Flash（無料枠）で動作。
"""

import json
import streamlit as st
from pathlib import Path

from src.researcher import research_topic
from src.generator import generate_article
from src.concept_suggester import suggest_concepts, refine_concept_chat, generate_article_plan, refine_plan_chat

# --- ページ設定 ---
st.set_page_config(
    page_title="note記事ライター",
    page_icon="✍️",
    layout="wide",
)

# --- カスタムCSS ---
st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .big-title { font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }
    .sub-title { font-size: 1rem; color: #666; margin-bottom: 2rem; }
    .score-high { color: #22c55e; font-size: 2rem; font-weight: bold; }
    .score-mid { color: #f59e0b; font-size: 2rem; font-weight: bold; }
    .score-low { color: #ef4444; font-size: 2rem; font-weight: bold; }
    .evidence-card {
        background: #f8f9fa; border-radius: 8px; padding: 1rem;
        margin-bottom: 0.5rem; border-left: 4px solid #6366f1;
    }
    .step-indicator {
        display: flex; gap: 1rem; margin-bottom: 2rem;
    }
    .step {
        flex: 1; text-align: center; padding: 0.5rem;
        border-radius: 8px; background: #f0f0f0; color: #999;
    }
    .step-active { background: #6366f1; color: white; }
    .step-done { background: #22c55e; color: white; }
</style>
""", unsafe_allow_html=True)


# --- エラーハンドリング ---
def show_friendly_error(e: Exception, context: str = "処理"):
    """Gemini APIのエラーをユーザーに分かりやすく表示する。"""
    err_str = str(e)
    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower():
        st.error(
            f"⚠️ **Geminiの1日の無料枠を使い切りました**\n\n"
            f"無料プランの1日あたりリクエスト数の上限に達しています。\n\n"
            f"**解決策（どれか1つ）:**\n"
            f"1. **24時間待つ** → 翌日に自動でリセットされます\n"
            f"2. **別のGoogleアカウントで新しいAPI Keyを作る** → "
            f"[Google AI Studio](https://aistudio.google.com/apikey) で別アカウントから取得\n"
            f"3. **記事生成前のステップ（コンセプト相談・プラン）を減らす** → 一発で記事生成に進む"
        )
    elif "API key" in err_str or "API_KEY" in err_str:
        st.error(
            f"⚠️ **APIキーが正しくありません**\n\n"
            f"左サイドバーのGemini API Keyを確認してください。"
            f"[取得マニュアル](https://github.com/atsushi0706/note-writer-tool/blob/master/docs/GEMINI_API_KEY_GUIDE.md)"
        )
    else:
        st.error(f"{context}に失敗しました: {e}")


# --- セッション初期化 ---
if "step" not in st.session_state:
    st.session_state.step = 1  # 1: 入力, 2: リサーチ結果, 3: 記事プレビュー
if "research" not in st.session_state:
    st.session_state.research = None
if "article" not in st.session_state:
    st.session_state.article = None
if "concept_messages" not in st.session_state:
    st.session_state.concept_messages = []
if "concept_suggestions" not in st.session_state:
    st.session_state.concept_suggestions = None
if "article_plan" not in st.session_state:
    st.session_state.article_plan = None
if "plan_messages" not in st.session_state:
    st.session_state.plan_messages = []


# --- ヘッダー ---
st.markdown('<div class="big-title">✍️ note記事ライター</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">コンセプトを入力 → リサーチ → 記事生成</div>', unsafe_allow_html=True)

# --- 使い方説明 ---
with st.expander("📖 はじめての方へ｜このツールの使い方", expanded=True):
    st.markdown("""
### 🎯 このツールでできること

あなたのプロフィールと書きたいテーマから、**読まれるnote記事**を自動で書き上げるツールです。

- ✅ 海外のエビデンス・専門家の知見を**実際にWeb検索**して引いてくる
- ✅ AIと相談しながら「何を書くか」を一緒に練り上げる
- ✅ 書く前に「進め方プラン」を確認できるので、思ってた記事と違うが起きない
- ✅ あなたのプロフィール・過去の痛みを記事に自然に織り込む
- ✅ Instagram・LP等への誘導文も自然に挿入できる

---

### 📐 noteで読まれる記事の3つのポイント

このツールは、これらを自動で組み込んで書きます。

1. **冒頭3行で読者の心を掴む（フック）**
   → 「えっ、どういうこと？」と前のめりにさせる一言から始める

2. **読者の悩みに共感する（共感パート）**
   → 「分かる、それ私もそうだった」と感じてもらう

3. **たった1つの気づき・行動を残す（核心パート）**
   → 詰め込まない。1記事1メッセージ

---

### 📝 全体の流れ（3ステップ・最短2クリック）

| Step | やること | API回数 |
|---|---|---|
| **① 入力** | プロフィール → コンセプト（自分で書くor AI相談） → ペルソナ → 設定 | コンセプトAI相談時のみ +1〜N回 |
| **② リサーチ → 記事生成** | 「📝 すぐに記事を書く」で1クリック完結 | **2回**（リサーチ+記事生成）|
| **③ 記事完成** | 完成 → コピーしてnoteに貼り付け | 0回 |

> 💡 **最小コース: 2回のAPI呼び出しで記事完成**
> プラン確認・コンセプト相談は任意（API追加消費）。Geminiの無料枠を節約したい場合は、これらをスキップしてください。

---

### ⚙️ どこを変えると、どう変わるか

下表を見ながら、自分が変えたい部分を調整してください。

| 設定する場所 | 変えるとどうなる |
|---|---|
| **プロフィール** | 記事に著者の体験談・視点が入る。空だと一般論寄りに |
| **過去の痛み** | ペルソナの痛みに重ねて語る部分ができる。空だと共感が浅め |
| **コンセプト** | 記事の主題が変わる。AI相談で迷いを解消できる |
| **ペルソナ** | 言葉選び・例え・距離感が変わる |
| **記事ジャンル**（心理学/スピリチュアル/エッセイ） | 集める素材が変わる（論文 / 物語 / 名言）。文体も変わる |
| **トーン**（優しい〜強め） | 記事の温度感が変わる |
| **伝え方**（柔らかく包む / グサッと言い切る） | 核心の伝え方が変わる |
| **ライタースタイル**（参考著者名） | その著者っぽい文体に近づく |
| **目標文字数**（1500〜3000） | 記事の長さ |
| **CTA・誘導文** | 記事内に自然な誘導が挿入される（リンクは後で手動で貼る） |

---

### 🔑 はじめる前の準備

1. **左サイドバー** に **Gemini API Key** を貼り付けてください（無料・クレカ不要）
2. APIキーをまだ持っていない方は、[**APIキー取得マニュアル**](https://github.com/atsushi0706/note-writer-tool/blob/master/docs/GEMINI_API_KEY_GUIDE.md)を参照

---

### 💡 上手く使うコツ

- **プロフィールは具体的に書く**（職業・読者層・経験を入れると記事の独自性が上がる）
- 例: ❌「キャリアコーチ」 → ✅「元銀行員のキャリアコーチ。30代女性向けに副業から起業を支援」
- **過去の痛みを書く**と、ペルソナの痛みに重ねて深い記事になる
- コンセプトに迷ったら **AI相談モード** で「もっと女性向けに」のように追い込める
- **進め方プランの段階**で違和感があれば、チャットで修正してから記事生成へ

---

### ⚠️ noteへの貼り付けについて

完成した記事は **コピー → note新規作成画面に貼り付け** してください。
（自動下書き保存は、セキュリティ上の理由で実装していません）

「🚀 noteで新規作成」ボタンで、note の新規作成ページがすぐ開けます。
""")
    st.caption("このパネルは ▼ をクリックして閉じられます。慣れたら閉じてOKです。")

# --- ステップインジケーター ---
steps = ["① 入力", "② リサーチ", "③ 記事完成"]
cols = st.columns(3)
for i, (col, label) in enumerate(zip(cols, steps), 1):
    if i < st.session_state.step:
        col.markdown(f'<div class="step step-done">{label} ✓</div>', unsafe_allow_html=True)
    elif i == st.session_state.step:
        col.markdown(f'<div class="step step-active">{label}</div>', unsafe_allow_html=True)
    else:
        col.markdown(f'<div class="step">{label}</div>', unsafe_allow_html=True)

st.divider()

# --- サイドバー: API KEY ---
with st.sidebar:
    st.header("設定")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="Google AI Studio (aistudio.google.com) で無料取得できます",
    )
    if not api_key:
        st.info("Gemini API Keyを入力してください。\n\n[Google AI Studio](https://aistudio.google.com/apikey) で無料取得できます。")

    st.divider()
    st.markdown("📖 **使い方マニュアル**")
    st.markdown("- [APIキー取得・設定マニュアル](https://github.com/atsushi0706/note-writer-tool/blob/master/docs/GEMINI_API_KEY_GUIDE.md)")
    st.markdown("- [README（概要・使い方）](https://github.com/atsushi0706/note-writer-tool/blob/master/README.md)")
    st.divider()
    st.caption("Gemini 2.5 Flash（無料枠）+ Google検索で動作")
    st.caption("ONE HACKモデルで構成")

    # API Keyをセッションに保存
    if api_key:
        st.session_state["_api_key"] = api_key

    # リセットボタン
    if st.button("最初からやり直す", use_container_width=True):
        st.session_state.step = 1
        st.session_state.research = None
        st.session_state.article = None
        st.session_state.article_plan = None
        st.session_state.plan_messages = []
        st.session_state.concept_messages = []
        st.session_state.concept_suggestions = None
        st.rerun()


# ========================================
# STEP 1: 入力
# ========================================
if st.session_state.step == 1:

    # ========== ① プロフィール（最上部・推奨） ==========
    st.header("① あなたのプロフィール")
    st.caption("入力するとAIがコンセプト案を提案します。記事にも反映されます。")

    author_identity = st.text_area(
        "あなたは何者で、どういったことを発信しているか",
        placeholder="例: 元銀行員のキャリアコーチ。30代女性向けに、お金と仕事の両立を発信している。",
        height=80,
        key="author_identity",
    )
    author_pain = st.text_area(
        "過去にどんな悩み・痛みを経験したか",
        placeholder="例: 銀行時代に過労で体を壊し、人生を見直した。お金のために自分を殺していた経験がある。",
        height=80,
        key="author_pain",
    )

    st.divider()

    # ========== ② コンセプト（AI提案 or 自分で入力） ==========
    st.header("② 今日書きたいコンセプト")

    concept_mode = st.radio(
        "コンセプトの決め方",
        ["💡 AIに相談しながら決める（プロのコピーライティング視点）", "✍️ 自分で入力する"],
        index=0,
        horizontal=False,
    )

    concept = ""

    if concept_mode == "✍️ 自分で入力する":
        concept = st.text_area(
            "今日書きたいコンセプト",
            placeholder="例: 完璧主義の人ほど先延ばしをしてしまう理由",
            height=100,
        )
    else:
        # AI相談モード
        st.caption("👆 上のプロフィール（発信内容＋過去の痛み）を元にコンセプトが提案されます。")
        if not author_identity:
            st.warning("⚠️ プロフィールの「発信内容」を入力してから提案ボタンを押してください。プロフィールが空だと一般的な提案になります。")

        # 初回提案ボタン
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button(
                "🎯 コンセプト案を出してもらう",
                use_container_width=True,
                disabled=not (api_key and author_identity),
            ):
                with st.spinner("プロのコピーライター視点でコンセプトを練っています..."):
                    try:
                        suggestions = suggest_concepts(author_identity, author_pain, api_key)
                        st.session_state.concept_suggestions = suggestions
                        # チャットの最初のメッセージとして整形して保存
                        intro = f"プロフィールから {len(suggestions)} 個のコンセプト案を出しました。気になる案があれば「案2でいきたい」のように伝えてください。別の角度から考えたい場合は遠慮なく言ってください。\n\n"
                        for i, s in enumerate(suggestions, 1):
                            intro += f"\n**案{i}: {s['title']}**\n"
                            intro += f"- フック: {s['hook']}\n"
                            intro += f"- 痛み: {s['target_pain']}\n"
                            intro += f"- 約束: {s['promise']}\n"
                            intro += f"- 独自性: {s['why_unique']}\n"
                        st.session_state.concept_messages = [
                            {"role": "assistant", "content": intro}
                        ]
                        st.rerun()
                    except Exception as e:
                        show_friendly_error(e, "提案")
        with col_btn2:
            if st.button("🔄 チャットをリセット", use_container_width=True):
                st.session_state.concept_messages = []
                st.session_state.concept_suggestions = None
                st.rerun()

        # チャット表示
        if st.session_state.concept_messages:
            with st.container(border=True):
                st.markdown("**💬 AIとの相談ログ**")
                for msg in st.session_state.concept_messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            # 修正リクエスト（折りたたみ式）
            with st.expander("🔧 もっと深掘りしたい・別の角度を試したい"):
                refine_input = st.text_area(
                    "AIへのリクエスト",
                    placeholder="例: 「案3を女性向けにアレンジして」「もう少しスピリチュアル寄りに」",
                    height=70,
                    key="concept_refine_input",
                )
                if st.button("📨 AIに送る", use_container_width=True, disabled=not refine_input):
                    st.session_state.concept_messages.append({"role": "user", "content": refine_input})
                    with st.spinner("考え中..."):
                        try:
                            response = refine_concept_chat(
                                st.session_state.concept_messages,
                                author_identity,
                                author_pain,
                                api_key,
                            )
                            st.session_state.concept_messages.append({"role": "assistant", "content": response})
                            st.rerun()
                        except Exception as e:
                            show_friendly_error(e, "応答取得")

            # 確定したコンセプトを入力
            st.markdown("---")
            st.markdown("### ✅ 決定したコンセプトを記入")
            st.caption("上のAI提案から気に入ったものを **コピー＆ペーストするか自分の言葉で書き直して** ください。これがリサーチと記事生成のベースになります。")
            concept = st.text_area(
                "今日書きたいコンセプト（確定版）",
                placeholder="例: 受け取れない人が抱えている「与え続ける症候群」の正体",
                height=80,
                key="finalized_concept",
            )

    st.divider()

    # ========== ③ ペルソナ ==========
    st.header("③ 届けたいペルソナ")
    persona = st.text_area(
        "誰に向けて書くか",
        placeholder="例: 30代女性、フリーランスのWebデザイナー。仕事は順調だが、なぜか自己肯定感が低い。",
        height=100,
    )

    st.divider()

    # ========== ④ オプション設定 ==========
    st.header("④ オプション設定")

    with st.expander("📌 CTA・誘導文（任意）— Instagram、LP、リードマグネット等への誘導"):
        st.caption("最大3つまで登録できます。AIが記事の指定位置に**誘導文だけ**を自然に織り込みます。リンクは各自noteで手動で貼ってください。")
        ctas = []
        for i in range(1, 4):
            st.markdown(f"**CTA {i}**")
            c1, c2 = st.columns([2, 1])
            with c1:
                label = st.text_input(
                    f"誘導文（記事に挿入されるフレーズ）",
                    placeholder="例: 公式LINEで電子書籍プレゼント中／詳しくはInstagramで／プロフィールのリンクから",
                    key=f"cta_label_{i}",
                )
            with c2:
                position = st.selectbox(
                    f"配置位置",
                    options=["使わない", "冒頭", "中盤", "末尾"],
                    index=0,
                    key=f"cta_pos_{i}",
                )
            if label and position != "使わない":
                ctas.append({
                    "label": label,
                    "position": position,
                })
            st.divider()

    st.subheader("記事ジャンル")
    genre_label = st.radio(
        "ジャンル（リサーチ方針が変わります）",
        options=[
            "心理学・ビジネス系（エビデンス重視）",
            "スピリチュアル・直感系（物語・未科学を扱う）",
            "エッセイ・日常系（個人視点・情緒重視）",
        ],
        index=0,
        help="ジャンルによってリサーチ対象と文体が変わります",
    )
    genre = {
        "心理学・ビジネス系（エビデンス重視）": "psychology",
        "スピリチュアル・直感系（物語・未科学を扱う）": "spiritual",
        "エッセイ・日常系（個人視点・情緒重視）": "essay",
    }[genre_label]

    st.subheader("トーン設定")
    col1, col2 = st.columns(2)

    with col1:
        tone_aggressive = st.slider(
            "トーン",
            min_value=0,
            max_value=100,
            value=30,
            help="0: とても優しい ← → 100: 挑発的",
        )
        if tone_aggressive <= 25:
            st.caption("🕊️ とても優しく包み込むトーン")
        elif tone_aggressive <= 50:
            st.caption("😊 基本優しく、核心では少し踏み込む")
        elif tone_aggressive <= 75:
            st.caption("💪 愛のある厳しさ")
        else:
            st.caption("🔥 常識を揺さぶる挑発的フック")

    with col2:
        tone_blunt = st.radio(
            "伝え方",
            options=["柔らかく包む", "グサッと言い切る"],
            index=0,
            help="核心の伝え方を選択",
        )

    writer_style = st.text_input(
        "参考にしたいライタースタイル（任意）",
        placeholder="例: ジョセフ・シュガーマン、神田昌典、メンタリストDaiGo",
        help="有名なセールスライター・著者の名前を入力すると、その文体を参考にします",
    )

    word_count = st.select_slider(
        "目標文字数",
        options=[1500, 2000, 2500, 3000],
        value=2000,
    )

    if st.button("🔍 リサーチ開始", type="primary", use_container_width=True, disabled=not api_key):
        if not concept:
            st.error("コンセプトを入力してください。")
        elif not persona:
            st.error("ペルソナを入力してください。")
        else:
            with st.spinner("リサーチ中..."):
                try:
                    research = research_topic(concept, persona, api_key, genre=genre)
                    st.session_state.research = research
                    st.session_state.concept = concept
                    st.session_state.persona = persona
                    st.session_state.genre = genre
                    st.session_state.ctas = ctas
                    st.session_state.tone_aggressive = tone_aggressive
                    st.session_state.tone_blunt = tone_blunt == "グサッと言い切る"
                    st.session_state.writer_style = writer_style
                    st.session_state.word_count = word_count
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    show_friendly_error(e, "リサーチ")


# ========================================
# STEP 2: リサーチ結果
# ========================================
elif st.session_state.step == 2:
    st.header("② リサーチ結果")
    research = st.session_state.research

    st.subheader("見つかったエビデンス")
    for ev in research.get("evidence", []):
        st.markdown(f"""<div class="evidence-card">
            <strong>{ev.get('title', '')}</strong><br>
            {ev.get('summary', '')}<br>
            <small>出典: {ev.get('source', '不明')}</small>
        </div>""", unsafe_allow_html=True)

    if research.get("expert_quotes"):
        st.subheader("専門家の知見")
        for eq in research.get("expert_quotes", []):
            st.markdown(f"**{eq.get('expert', '')}**: 「{eq.get('quote', '')}」")
            st.caption(eq.get("context", ""))

    st.subheader("核となる洞察")
    st.info(research.get("key_insight", ""))

    # Google検索で実際に参照したURL
    if research.get("sources"):
        with st.expander(f"🔗 検索で参照した情報源（{len(research['sources'])}件）"):
            for src in research["sources"]:
                title = src.get("title", "")
                uri = src.get("uri", "")
                if uri:
                    st.markdown(f"- [{title or uri}]({uri})")

    st.subheader("🎯 記事の4つの軸（編集可能）")
    st.caption("**1記事に「1つだけ」を貫く設計です。** 下の4つを書き換えると記事の方向性が変わります。AIが提案した値が入っていますが、自由に編集できます。")

    col1, col2 = st.columns(2)
    with col1:
        one_idea = st.text_input(
            "💡 1つのアイデア（記事で伝える唯一のメッセージ）",
            value=research.get("suggested_one_idea", ""),
            help="変えると記事の主題そのものが変わります。例: 「自己投資の本質はお金ではなく時間」",
        )
        st.caption("→ ここを変えると **記事の核心メッセージ** が変わる")

        one_emotion = st.text_input(
            "💗 1つの感情（読者に呼び起こす感情）",
            value=research.get("suggested_one_emotion", ""),
            help="変えると記事の温度感が変わる。例: 安心 / 焦り / 共感 / 怒り / 希望",
        )
        st.caption("→ ここを変えると **読者が記事を読んで感じる感情** が変わる")

    with col2:
        one_story = st.text_input(
            "📖 1つのストーリー（使う比喩・物語）",
            value=research.get("suggested_one_story", ""),
            help="変えると記事の例え・例示が変わる。例: 「料理の味付け」「マラソンの走り方」",
        )
        st.caption("→ ここを変えると **記事の中で使われる比喩** が変わる")

        one_action = st.text_input(
            "🎯 1つの行動（読者に促す行動）",
            value=research.get("suggested_one_action", ""),
            help="変えると記事の締めくくりが変わる。例: 「今日の出来事を1つ書き出す」",
        )
        st.caption("→ ここを変えると **記事の最後に読者に促す行動** が変わる")

    st.divider()

    # ========== 🚀 すぐに記事を生成（推奨） ==========
    st.subheader("🚀 記事を生成する")
    st.caption("**推奨：API節約モード** プランをスキップして1クリックで記事を生成します（API呼び出し1回）。")

    quick_clicked = False
    if st.button("📝 すぐに記事を書く（プランをスキップ）", type="primary", use_container_width=True, key="quick_generate"):
        st.session_state.research["suggested_one_idea"] = one_idea
        st.session_state.research["suggested_one_emotion"] = one_emotion
        st.session_state.research["suggested_one_story"] = one_story
        st.session_state.research["suggested_one_action"] = one_action
        st.session_state.article_plan = None
        quick_clicked = True

    st.divider()

    # ========== 📋 進め方プラン（任意・API追加消費） ==========
    approve_clicked = False
    with st.expander("📋 進め方プランを確認してから書きたい場合（API追加消費）"):
        st.caption("記事を書く前に「この方向性で進めますね」をAIが提案します。プラン作成で+1回、修正チャットで+N回のAPIを使います。")

        if st.session_state.article_plan is None:
            if st.button("🎯 進め方プランを作る", use_container_width=True):
                st.session_state.research["suggested_one_idea"] = one_idea
                st.session_state.research["suggested_one_emotion"] = one_emotion
                st.session_state.research["suggested_one_story"] = one_story
                st.session_state.research["suggested_one_action"] = one_action

                with st.spinner("進め方プランを作成中..."):
                    try:
                        plan = generate_article_plan(
                            concept=st.session_state.concept,
                            persona=st.session_state.persona,
                            research=st.session_state.research,
                            author_identity=st.session_state.get("author_identity", ""),
                            author_pain=st.session_state.get("author_pain", ""),
                            genre=st.session_state.get("genre", "psychology"),
                            tone_aggressive=st.session_state.tone_aggressive,
                            tone_blunt=st.session_state.tone_blunt,
                            api_key=st.session_state.get("_api_key", ""),
                        )
                        st.session_state.article_plan = plan
                        st.rerun()
                    except Exception as e:
                        show_friendly_error(e, "プラン作成")
        else:
            plan = st.session_state.article_plan

            with st.container(border=True):
                st.markdown(f"### 🎯 核心メッセージ\n{plan.get('main_message', '')}")
                st.markdown(f"### 🪝 冒頭フック\n{plan.get('hook_direction', '')}")
                st.markdown(f"### 🔑 中核論理・展開\n{plan.get('core_argument', '')}")

                evidence_list = plan.get("evidence_to_use", [])
                if evidence_list:
                    st.markdown("### 📚 使う素材")
                    for ev in evidence_list:
                        st.markdown(f"- {ev}")

                st.markdown(f"### 🎨 比喩・ストーリー\n{plan.get('key_metaphor', '')}")
                st.markdown(f"### 🚪 締めくくり（読者の行動）\n{plan.get('closing_action', '')}")

                if plan.get("author_angle"):
                    st.markdown(f"### 👤 著者プロフィールの活かし方\n{plan.get('author_angle', '')}")

                st.markdown(f"### 💫 読後の余韻\n{plan.get('expected_impact', '')}")

            # ボタン
            col_regen, col_approve = st.columns(2)
            with col_regen:
                if st.button("🔄 プランを再生成する", use_container_width=True):
                    st.session_state.article_plan = None
                    st.session_state.plan_messages = []
                    st.rerun()
            with col_approve:
                approve_clicked = st.button("✅ このプランで記事を書く", type="primary", use_container_width=True)

    st.divider()

    col_back = st.columns(1)[0]
    with col_back:
        if st.button("← 入力に戻る", use_container_width=True):
            st.session_state.step = 1
            st.session_state.article_plan = None
            st.session_state.plan_messages = []
            st.rerun()

    # 記事生成（クイック or プラン承認時に実行）
    if quick_clicked or approve_clicked:
        with st.spinner("ONE HACK構成で記事を生成中..."):
            try:
                article = generate_article(
                    concept=st.session_state.concept,
                    persona=st.session_state.persona,
                    research=st.session_state.research,
                    tone_aggressive=st.session_state.tone_aggressive,
                    tone_blunt=st.session_state.tone_blunt,
                    word_count=st.session_state.word_count,
                    writer_style=st.session_state.writer_style,
                    api_key=st.session_state.get("_api_key", ""),
                    genre=st.session_state.get("genre", "psychology"),
                    author_identity=st.session_state.get("author_identity", ""),
                    author_pain=st.session_state.get("author_pain", ""),
                    ctas=st.session_state.get("ctas", []),
                    article_plan=st.session_state.article_plan,
                )
                st.session_state.article = article
                st.session_state.step = 3
                st.rerun()
            except Exception as e:
                show_friendly_error(e, "記事生成")


# ========================================
# STEP 3: 記事完成
# ========================================
elif st.session_state.step == 3:
    st.header("③ 記事完成")
    article = st.session_state.article

    st.divider()

    # タイトル（編集可能）
    edited_title = st.text_input("タイトル", value=article.get("title", ""))

    # タグ
    tags = article.get("tags", [])
    st.caption(f"タグ: {', '.join(tags)}")

    # 本文（編集可能）
    edited_body = st.text_area(
        "本文",
        value=article.get("body", ""),
        height=500,
    )

    char_count = len(edited_body)
    st.caption(f"文字数: {char_count:,}")

    st.divider()

    # コピー & ダウンロード
    st.subheader("📋 記事を使う")
    st.caption("以下のボタンから記事をコピーして、noteに貼り付けてください。")

    col_copy_title, col_copy_body = st.columns(2)

    with col_copy_title:
        st.text_area(
            "タイトル（コピー用）",
            value=edited_title,
            height=70,
            help="右上のコピーボタンでコピーできます",
            key="copy_title",
        )

    with col_copy_body:
        st.text_area(
            "本文（コピー用）",
            value=edited_body,
            height=200,
            help="右上のコピーボタンでコピーできます",
            key="copy_body",
        )

    # noteを開くリンク
    col1, col2, col3 = st.columns(3)

    with col1:
        st.link_button(
            "🚀 noteで新規作成",
            url="https://note.com/notes/new",
            use_container_width=True,
        )

    with col2:
        # JSONダウンロード
        json_data = json.dumps({
            "title": edited_title,
            "body": edited_body,
            "tags": tags,
        }, ensure_ascii=False, indent=2)
        st.download_button(
            "💾 JSONでダウンロード",
            data=json_data,
            file_name=f"note_draft_{edited_title[:20]}.json",
            mime="application/json",
            use_container_width=True,
        )

    with col3:
        # テキストダウンロード
        text_data = f"{edited_title}\n\n{edited_body}"
        st.download_button(
            "📄 テキストでダウンロード",
            data=text_data,
            file_name=f"note_draft_{edited_title[:20]}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    st.divider()

    # ナビゲーションボタン
    col_back, col_regen = st.columns(2)

    with col_back:
        if st.button("← リサーチに戻る", use_container_width=True):
            st.session_state.step = 2
            st.rerun()

    with col_regen:
        if st.button("🔄 再生成する", use_container_width=True):
            with st.spinner("再生成中..."):
                try:
                    article = generate_article(
                        concept=st.session_state.concept,
                        persona=st.session_state.persona,
                        research=st.session_state.research,
                        tone_aggressive=st.session_state.tone_aggressive,
                        tone_blunt=st.session_state.tone_blunt,
                        word_count=st.session_state.word_count,
                        writer_style=st.session_state.writer_style,
                        api_key=st.session_state.get("_api_key", ""),
                        genre=st.session_state.get("genre", "psychology"),
                        author_identity=st.session_state.get("author_identity", ""),
                        author_pain=st.session_state.get("author_pain", ""),
                        ctas=st.session_state.get("ctas", []),
                        article_plan=st.session_state.article_plan,
                    )
                    st.session_state.article = article
                    st.rerun()
                except Exception as e:
                    show_friendly_error(e, "再生成")
