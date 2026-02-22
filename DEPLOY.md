# Streamlit Cloud デプロイ手順（Google Sheets 連携）

本番用シークレットを誤ってコミットしないための作業手順をまとめます。

## 1. シークレットの準備（ローカルで開かない）
- `gen-lang-client-0360673218-9b47aa22b42f.json` は **コミットしない**（`.gitignore` 済み）。
- JSON を開く必要がある場合はローカルで確認し、`private_key` の改行を `\n` に置換しておく。

## 2. Streamlit Cloud の Secrets 設定
1. Streamlit Cloud のデプロイページで **Secrets** を開く。
2. 以下を貼り付け、`project_id`・`client_email`・`private_key` を JSON から転記する（改行は `\n`）。
   ```toml
   [connections.gsheets]
   type = "service_account"
   project_id = "gen-lang-client-0360673218"
   private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
   client_email = "streamlit-sheets-sa@gen-lang-client-0360673218.iam.gserviceaccount.com"
   spreadsheet = "https://docs.google.com/spreadsheets/d/1WnlZ2BACdf3uCha0JOscdk2wPselC_VVm_Ua6VlhC-I"
   ```
3. 保存後にアプリを再デプロイする。

## 3. 動作確認（手順）
1. デプロイされたアプリを開き、任意のユーザー名でクイズを完了。
2. 「スコアを保存」を押す。
3. 数秒後に Google Sheets の `Scores` シートを開き、レコードが追加されているか確認。
4. アプリのランキング表示に反映されることを確認（`load_scores` はキャッシュ無効化なので即時反映）。

## 4. ローカルの鍵ファイルの扱い
- 作業後は鍵ファイルを安全な場所に移動するか削除する。
- 追加で鍵を扱う場合は、`.gitignore` にあることを確認し、誤ってステージングしないよう注意する。

## 5. 依存関係
- `requirements.txt` に `streamlit`, `pandas`, `streamlit-gsheets` を記載済み。Cloud で自動インストールされる。

## 6. トラブルシュートのヒント
- 認証エラー: Secrets の `private_key` の改行が `\n` に置換されているか確認。
- 書き込みエラー: Sheets 側でサービスアカウントが「編集者」権限になっているか確認。
- 反映遅延: ネットワーク遅延の場合があるため数秒待つ。キャッシュは `ttl=0` なので基本即時反映。
