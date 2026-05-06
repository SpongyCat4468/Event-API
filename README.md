# 活動交易所 API

FastAPI + SQLite + Discord Bot 的三隊虛擬貨幣交易系統。

## 啟動後端與前端

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

前端即時看板：

```text
http://127.0.0.1:8000/
```

API 文件：

```text
http://127.0.0.1:8000/docs
```

## Discord Bot

```bash
export DISCORD_BOT_TOKEN="你的 Discord Bot Token"
export API_BASE_URL="http://127.0.0.1:8000"
export ADMIN_TOKEN="jmec-staff"
export DISCORD_GUILD_ID="你的 Discord 伺服器 ID"
python discord_bot.py
```

如果 FastAPI 已部署到線上，請把 `API_BASE_URL` 改成你的後端網址，例如：

```bash
export API_BASE_URL="https://jmec-event-api.onrender.com"
```

網址最後不用加 `/`。

## Render / Railway 部署

建議啟動指令：

```bash
gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

這個專案也已包含 `Procfile`：

```text
web: gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

環境變數建議：

| 變數 | 用途 | 範例 |
|---|---|---|
| `ADMIN_TOKEN` | 上帝模式 API token | `jmec-staff-secret` |
| `ALLOWED_ORIGINS` | 允許前端或 Bot 呼叫 API 的來源，預設 `*` | `*` 或 `https://你的前端網址` |
| `SQLITE_PATH` | SQLite 檔案位置，建議設到 persistent disk | `/var/data/crypto_sim.db` |
| `DATABASE_URL` | 進階 DB URL；有設定時會覆蓋 `SQLITE_PATH` | `sqlite:////var/data/crypto_sim.db` |

Render 若使用 persistent disk，可以把 disk 掛在 `/var/data`，並設定：

```text
SQLITE_PATH=/var/data/crypto_sim.db
```

Railway 若使用 Volume，程式會自動讀取 `RAILWAY_VOLUME_MOUNT_PATH`，也可以明確設定：

```text
SQLITE_PATH=/data/crypto_sim.db
```

沒有 persistent disk 時，SQLite 仍然可以讀寫，但雲端服務重啟或重新部署後資料可能消失。

Windows PowerShell：

```powershell
$env:DISCORD_BOT_TOKEN="你的 Discord Bot Token"
$env:API_BASE_URL="http://127.0.0.1:8000"
$env:ADMIN_TOKEN="jmec-staff"
$env:DISCORD_GUILD_ID="你的 Discord 伺服器 ID"
python discord_bot.py
```

## 預設資料

隊伍：

- Zeroth
- First
- Second

虛擬貨幣：

- INFOR（建中資訊社）
- CMIOC（景美電資社）
- IZCC（四社聯合）

## Discord Slash Commands

| 指令 | 說明 |
|---|---|
| `/price` | 查看即時幣價與最新新聞 |
| `/buy` | 小隊買入虛擬貨幣 |
| `/sell` | 小隊賣出虛擬貨幣 |
| `/balance` | 查看小隊資產 |
| `/leaderboard` | 查看排行榜 |
| `/news` | 查看新聞 |
| `/start_game` | 設定零小、一小、二小本金並重置遊戲 |
| `/end_game` | 結束遊戲並進入結算 |
| `/team_balance` | 對小隊現金執行 set/multiply/add/remove |
| `/team_holding` | 對小隊持幣執行 set/multiply/add/remove |
| `/pump` | 工作人員觸發利多暴漲 |
| `/crash` | 工作人員觸發市場崩盤 |

管理指令需要 Discord Administrator 或 Manage Server 權限，且 Bot 端 `ADMIN_TOKEN` 必須與後端一致。

## 主要 API

### 價格

```http
GET /price
```

回傳三種幣目前價格、最近價格歷史、最新新聞。前端每 3 秒會呼叫一次。

### 統一交易

```http
POST /trade
```

```json
{
  "team_name": "Zeroth",
  "crypto_symbol": "INFOR",
  "quantity": 0.1,
  "trade_type": "buy"
}
```

`trade_type` 可用 `buy` 或 `sell`。

舊版端點仍保留：

- `POST /trade/buy`
- `POST /trade/sell`

### 上帝模式

```http
POST /admin/market-event
X-Admin-Token: jmec-staff
```

```json
{
  "event_type": "pump",
  "symbol": "INFOR",
  "percent": 5,
  "headline": "建中資訊社社員在 APCS 取得好成績"
}
```

`event_type` 可用：

- `pump`
- `crash`

`symbol` 可填 `INFOR`、`CMIOC`、`IZCC`，或留空套用全市場。舊代號 `BTC`、`ETH`、`SOL` 仍會自動對應到新代號，方便舊版 Bot 暫時過渡。

## 市場更新邏輯

後端啟動後會每 10 秒自動更新價格，公式包含：

- Trend：每個幣種的基礎趨勢
- Volatility：隨機波動
- Impact：買賣交易形成的買壓或賣壓
- News/Event：隨機新聞或上帝模式事件；自動新聞會造成 5% 到 10% 的漲跌幅

每次更新都會寫入 `price_history`，前端折線圖會從 `/price` 的 history 即時繪製。
