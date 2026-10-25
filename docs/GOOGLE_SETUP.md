# Google Sheets setup (10 minutes, no experience needed)

The program writes leads to a Google Sheet through a **service account** — a technical Google "user" with its own key file. You give it access to one sheet only.

## 1. Create a project
1. Open https://console.cloud.google.com/ and sign in with your Google account.
2. At the top, click the project selector → **New project** → name it `leads-automation` → **Create**.
3. Make sure the new project is selected at the top.

## 2. Turn on the Google Sheets API
1. Menu ☰ → **APIs & Services** → **Library**.
2. Search **Google Sheets API** → open it → **Enable**.

## 3. Create the service account
1. Menu ☰ → **IAM & Admin** → **Service accounts** → **Create service account**.
2. Name: `leads-writer` → **Create and continue** → skip roles → **Done**.
3. Copy its email, it looks like `leads-writer@leads-automation.iam.gserviceaccount.com`.

## 4. Download the key
1. Click the service account → tab **Keys** → **Add key** → **Create new key** → **JSON** → **Create**.
2. A `.json` file downloads. **This is a password**: never send it in chats, never put it in git.
3. Move it to the project folder as `secrets/google-service-account.json`.

> If Google shows "Service account key creation is disabled" (organization policy), use a personal Gmail account for the project, or ask the admin to allow keys.

## 5. Create the sheet and share it
1. Create a new Google Sheet, e.g. "Leads".
2. Click **Share**, paste the service account email from step 3, role **Editor**, untick "Notify people" → **Share**.
3. Copy the sheet ID from the address bar:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

## 6. Configure
In `.env`:
```
GOOGLE_SHEET_ID=THIS_PART
GOOGLE_CREDENTIALS_FILE=secrets/google-service-account.json
```
Restart the app. On first start it creates the **Leads** tab with the header, frozen first row and the status dropdown (Новая / В работе / Закрыта / Спам).

## Check
`uv run python scripts/send_test_lead.py` → a new row appears in the sheet.

---
**Кратко по-русски:** создайте проект в Google Cloud, включите Google Sheets API, создайте сервисный аккаунт и JSON-ключ, положите ключ в `secrets/`, откройте таблице доступ «Редактор» для email сервисного аккаунта и впишите ID таблицы в `.env`. Ключ никому не пересылайте.
