# YouTube新着ダッシュボード（自動取得版）

登録済みチャンネル：

- 海外Yパパラジオ 世界を読み解く
- URL: https://www.youtube.com/@neko_Ypapa
- チャンネルID: `UC8fTn4DsxlAlql3OXJ8syRA`

## この版でできること

- YouTube公式RSSから新着動画を自動取得
- タイトル、公開日時、リンク、サムネイル、概要欄を表示
- OpenAI APIキーがある場合、タイトルと概要欄から日本語要約を生成
- APIキーがない場合も簡易要約で動作
- 毎日4:05（日本時間）にGitHub Actionsで自動更新
- GitHub Pagesでブラウザ表示
- 手動更新にも対応

## 導入手順

### 1. GitHubに新しいリポジトリを作る

GitHubで空のリポジトリを作成し、このフォルダー内のファイルをすべてアップロードします。
`.github`は隠しフォルダーなので、フォルダー構造を保ったままアップロードしてください。

### 2. GitHub Pagesを有効にする

リポジトリの次の画面を開きます。

`Settings → Pages`

設定：

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/ (root)`

保存後、公開URLが発行されます。

### 3. 初回データを取得する

次の画面を開きます。

`Actions → Update YouTube dashboard → Run workflow`

処理完了後、`data/videos.json`に実データが保存されます。

### 4. AI要約を有効にする（任意）

OpenAI APIキーがある場合は、次の画面で登録します。

`Settings → Secrets and variables → Actions → New repository secret`

- Name: `OPENAI_API_KEY`
- Secret: OpenAI APIキー

APIキーを設定しなくても、RSSの概要欄を使った簡易要約で動作します。

## チャンネルを追加する方法

`channels.json`に項目を追加します。

```json
{
  "name": "表示名",
  "handle": "@ハンドル名",
  "channelId": "UCから始まるチャンネルID",
  "url": "チャンネルURL",
  "category": "分類"
}
```

## 注意事項

- RSSは公開されている最新動画を取得します。
- OpenAIによる要約は、動画の音声そのものではなく、タイトルと概要欄に基づきます。
- `index.html`をPCから直接ダブルクリックすると、ブラウザの制約によりJSONを読めない場合があります。GitHub Pagesで表示してください。
- GitHub Actionsの実行時刻は混雑により数分遅れる場合があります。
