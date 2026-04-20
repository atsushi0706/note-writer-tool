# note記事ライター

コンセプトを入力するだけで、ONE HACKモデルに従って2,000文字のnote記事を自動生成するツール。

## 特徴

- **Gemini 2.0 Flash** で完全無料動作
- **ONE HACKモデル**（H→A→C→K）で構成
- **海外エビデンス** を自動リサーチ
- **トーン設定**（優しい↔挑発的 / 柔らかく包む↔グサッと言い切る）
- **品質スコア** 自動チェック

## 使い方

1. [Google AI Studio](https://aistudio.google.com/apikey) で無料のGemini API Keyを取得
2. サイドバーにAPI Keyを貼り付け
3. コンセプトとペルソナを入力
4. リサーチ → 記事生成
5. コピーしてnoteに貼り付け

詳しい手順は [docs/GEMINI_API_KEY_GUIDE.md](docs/GEMINI_API_KEY_GUIDE.md) を参照。

## ローカルで動かす

```bash
pip install -r requirements.txt
streamlit run app.py
```

ブラウザで http://localhost:8501 が開きます。
