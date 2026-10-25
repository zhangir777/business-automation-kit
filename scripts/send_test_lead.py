"""Send a test lead to the local server.

uv run python scripts/send_test_lead.py [--url http://localhost:8000] [--source json|tilda]
"""

import argparse
import os
import random

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--source", default="json", choices=["json", "tilda", "google-form"])
parser.add_argument("--secret", default=os.getenv("WEBHOOK_SECRET", "change-me"))
args = parser.parse_args()

phone = f"8 777 {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
lead = {
    "name": "Тестовый клиент",
    "phone": phone,
    "email": "test@example.com",
    "comment": "Хочу узнать цену (тестовая заявка)",
    "utm_source": "instagram",
}
url = f"{args.url}/webhook/{args.source}"
headers = {"X-Webhook-Secret": args.secret}
if args.source == "tilda":
    tilda = {
        "Name": lead["name"],
        "Phone": phone,
        "Email": lead["email"],
        "Comments": lead["comment"],
        "formname": "Заявка",
        "utm_source": "instagram",
    }
    resp = httpx.post(url, data=tilda, headers=headers)
else:
    resp = httpx.post(url, json=lead, headers=headers)
print(resp.status_code, resp.text)
