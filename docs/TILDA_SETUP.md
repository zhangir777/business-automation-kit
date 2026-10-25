# Connect a Tilda form (and Google Forms)

Your server must be reachable from the internet with HTTPS, e.g. `https://leads.example.kz` (VPS + domain, or a tunnel like Cloudflare Tunnel for testing).

## Tilda
1. Tilda → **Site settings** → **Forms** → **Webhook**.
2. Webhook URL:
   ```
   https://leads.example.kz/webhook/tilda?secret=YOUR_WEBHOOK_SECRET
   ```
   (`WEBHOOK_SECRET` from `.env`; Tilda can't send custom headers, so the secret goes in the URL.)
3. Tilda sends a test request (`test=test`) — the server answers 200 and the service is connected.
4. Tick **Send UTM** (in the same settings) if you want UTM tags in the sheet.
5. Open each form block → **Content** → **Receivers** → tick the webhook → **Save** → **Publish** the page.
6. Name form fields `Name`, `Phone`, `Email`, `Comments` (Tilda defaults). Russian names (`Имя`, `Телефон`) also work.

Check: submit the form on the live page → row in the sheet + message in Telegram within seconds.

## Any website / landing builder (JSON)
POST to `https://leads.example.kz/webhook/json` with header `X-Webhook-Secret: YOUR_WEBHOOK_SECRET`:
```json
{"name": "Аня", "phone": "8 777 123 45 67", "email": "a@mail.kz", "comment": "Нужна консультация", "source": "landing", "utm_source": "instagram"}
```

## Google Forms
1. Open the form → **Responses** → link to a Google Sheet (any).
2. In that sheet: **Extensions** → **Apps Script**, paste:
   ```javascript
   function onFormSubmit(e) {
     UrlFetchApp.fetch("https://leads.example.kz/webhook/google-form", {
       method: "post",
       contentType: "application/json",
       headers: {"X-Webhook-Secret": "YOUR_WEBHOOK_SECRET"},
       payload: JSON.stringify({namedValues: e.namedValues})
     });
   }
   ```
3. **Triggers** (clock icon) → **Add trigger** → `onFormSubmit`, event: **From spreadsheet → On form submit** → Save and allow access.

Questions titled "Имя"/"Name", "Телефон"/"Phone", "Email", "Комментарий"/"Comment" are recognized automatically.
