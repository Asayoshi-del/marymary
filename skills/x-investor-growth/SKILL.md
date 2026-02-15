---
name: x-investor-growth
description: X（旧Twitter）アカウント @3m6LGY8PTkQKx63 のフォロワー最大化のための自動運用Skill。バズ投稿リサーチ・分析・リライト・予約投稿のワークフローを自動化する。
---

# X Investor Growth Skill

## ペルソナ定義

**属性**: 個人投資家、富裕層の思考を持つビジネスマン

**投稿内容**:
- ビジネス全般
- 米国株トレンド（投資助言なし）
- 富裕層の習慣
- お金持ちの思考法
- 自己啓発

**トーン**:
- 落ち着いていて理性的
- 時折鋭い本質を突く洞察
- 感情的にならず、事実と論理に基づいて語る
- 過去ツイートから抽出した口癖やリズムを模倣する

## ワークフロー

### 1. バズ投稿リサーチ（Research Module）
```bash
# 実行方法: main.py の --generate オプション内で自動実行
```

1. 指定ジャンルのキーワードでX API検索を実行
2. いいね数・RT数でバズ投稿をフィルタリング
3. テキスト構造パターンを分析（問いかけ型、断言型、リスト型、対比型、体験型、格言型）
4. 分析結果を `data/research_results.json` に保存

### 2. スタイル分析（Style Analyzer）
1. 過去ツイート50件を取得
2. 語尾パターン分析（「だ」「である」等の使用頻度）
3. 漢字/ひらがな/カタカナ比率の計算
4. 口癖・頻出フレーズの抽出
5. 分析結果を `data/style_profile.json` に保存

### 3. 投稿生成（Content Engine）
1. Anthropic Claude API を使用
2. ペルソナ + スタイル分析結果をプロンプトに反映
3. バズ投稿の構造パターンを参考にリライト
4. **140文字以内**を厳守（超過時は自動リトライ）
5. 禁止表現チェック（投資助言排除）

### 4. 予約投稿（Scheduler）
ピークタイムに分散投稿：
- **朝** (7:00, 8:00, 9:00): 3件
- **昼** (12:00, 12:30, 13:00): 3件  
- **夜** (20:00, 21:00, 22:00, 23:00): 4件

### 5. 投稿レビュー（Interactive Mode）
デフォルトで対話型モードが有効：
- `[a]` 承認
- `[s]` スキップ
- `[e]` 編集
- `[q]` 終了

## コマンドリファレンス

```bash
# 投稿案の生成（対話型レビュー付き）
python main.py --generate

# 自動承認モード
python main.py --generate --auto

# 生成件数を指定
python main.py --generate --count 5

# ドライラン（API呼出なし）
python main.py --generate --dry-run

# 予約投稿の実行（デーモンモード）
python main.py --run

# スケジュール状況の確認
python main.py --status

# 投稿済みアイテムのクリア
python main.py --clear
```

## 制約事項

1. **140文字以内**を厳守
2. **ハッシュタグは一切使用しない**
3. **投資助言に該当する断定的表現は禁止**
   - 禁止: 「買い」「売り」「必ず儲かる」「おすすめ銘柄」等
   - 許可: 思考法やトレンドの紹介
4. URLやメンションは含めない

## セットアップ

### 1. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

### 2. APIキーの設定
```bash
cp .env.example .env
# .env ファイルを編集し、各APIキーを入力
```

### 必要なAPIキー
| キー名 | 説明 |
|--------|------|
| `X_API_KEY` | X API Consumer Key |
| `X_API_SECRET` | X API Consumer Secret |
| `X_ACCESS_TOKEN` | X API Access Token |
| `X_ACCESS_TOKEN_SECRET` | X API Access Token Secret |
| `X_BEARER_TOKEN` | X API Bearer Token |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key |
