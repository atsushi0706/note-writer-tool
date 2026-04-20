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
from src.quality_checker import check_quality

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


# --- セッション初期化 ---
if "step" not in st.session_state:
    st.session_state.step = 1  # 1: 入力, 2: リサーチ結果, 3: 記事プレビュー
if "research" not in st.session_state:
    st.session_state.research = None
if "article" not in st.session_state:
    st.session_state.article = None
if "quality" not in st.session_state:
    st.session_state.quality = None


# --- ヘッダー ---
st.markdown('<div class="big-title">✍️ note記事ライター</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">コンセプトを入力 → リサーチ → 記事生成</div>', unsafe_allow_html=True)

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
    st.caption("Gemini 2.0 Flash（無料枠）で動作")
    st.caption("ONE HACKモデルで構成")

    # API Keyをセッションに保存
    if api_key:
        st.session_state["_api_key"] = api_key

    # リセットボタン
    if st.button("最初からやり直す", use_container_width=True):
        st.session_state.step = 1
        st.session_state.research = None
        st.session_state.article = None
        st.session_state.quality = None
        st.rerun()


# ========================================
# STEP 1: 入力
# ========================================
if st.session_state.step == 1:
    st.header("① コンセプトとペルソナを入力")

    concept = st.text_area(
        "今日書きたいコンセプト",
        placeholder="例: 完璧主義の人ほど先延ばしをしてしまう理由",
        height=100,
    )

    persona = st.text_area(
        "届けたいペルソナ（誰に向けて書くか）",
        placeholder="例: 30代女性、フリーランスのWebデザイナー。仕事は順調だが、なぜか自己肯定感が低い。",
        height=100,
    )

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
            with st.spinner("海外のエビデンスをリサーチ中..."):
                try:
                    research = research_topic(concept, persona, api_key)
                    st.session_state.research = research
                    st.session_state.concept = concept
                    st.session_state.persona = persona
                    st.session_state.tone_aggressive = tone_aggressive
                    st.session_state.tone_blunt = tone_blunt == "グサッと言い切る"
                    st.session_state.writer_style = writer_style
                    st.session_state.word_count = word_count
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"リサーチに失敗しました: {e}")


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

    st.subheader("ONE HACK要素（編集可能）")
    col1, col2 = st.columns(2)
    with col1:
        one_idea = st.text_input("ONE idea", value=research.get("suggested_one_idea", ""))
        one_emotion = st.text_input("ONE emotion", value=research.get("suggested_one_emotion", ""))
    with col2:
        one_story = st.text_input("ONE story", value=research.get("suggested_one_story", ""))
        one_action = st.text_input("ONE action", value=research.get("suggested_one_action", ""))

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← 入力に戻る", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

    with col_next:
        if st.button("📝 記事を生成する", type="primary", use_container_width=True):
            st.session_state.research["suggested_one_idea"] = one_idea
            st.session_state.research["suggested_one_emotion"] = one_emotion
            st.session_state.research["suggested_one_story"] = one_story
            st.session_state.research["suggested_one_action"] = one_action

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
                    )
                    st.session_state.article = article

                    quality = check_quality(
                        title=article.get("title", ""),
                        body=article.get("body", ""),
                        concept=st.session_state.concept,
                        api_key=st.session_state.get("_api_key", ""),
                    )
                    st.session_state.quality = quality
                    st.session_state.step = 3
                    st.rerun()
                except Exception as e:
                    st.error(f"記事生成に失敗しました: {e}")


# ========================================
# STEP 3: 記事完成
# ========================================
elif st.session_state.step == 3:
    st.header("③ 記事完成")
    article = st.session_state.article
    quality = st.session_state.quality

    # 品質スコア
    score = quality.get("score", 0) if quality else 0
    col_score, col_info = st.columns([1, 3])
    with col_score:
        if score >= 90:
            st.markdown(f'<div class="score-high">{score}点</div>', unsafe_allow_html=True)
        elif score >= 70:
            st.markdown(f'<div class="score-mid">{score}点</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="score-low">{score}点</div>', unsafe_allow_html=True)
        st.caption("品質スコア")

    with col_info:
        if quality:
            if quality.get("passed"):
                st.success("品質チェック通過！")
            else:
                st.warning(f"改善の余地あり: {quality.get('issues', '')}")
                st.caption(f"提案: {quality.get('suggestion', '')}")

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
            "quality_score": score,
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
                    )
                    st.session_state.article = article
                    quality = check_quality(
                        title=article.get("title", ""),
                        body=article.get("body", ""),
                        concept=st.session_state.concept,
                        api_key=st.session_state.get("_api_key", ""),
                    )
                    st.session_state.quality = quality
                    st.rerun()
                except Exception as e:
                    st.error(f"再生成に失敗しました: {e}")
