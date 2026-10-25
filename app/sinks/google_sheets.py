"""Google Sheets storage via a service account (docs/GOOGLE_SETUP.md)."""

from pathlib import Path

import gspread

from app.models import COLUMNS, STATUSES, Lead


class GoogleSheet:
    def __init__(self, credentials_file: Path, sheet_id: str, worksheet: str = "Leads"):
        self.sheet_id = sheet_id
        client = gspread.service_account(filename=str(credentials_file))
        spreadsheet = client.open_by_key(sheet_id)
        try:
            self.ws = spreadsheet.worksheet(worksheet)
        except gspread.WorksheetNotFound:
            self.ws = spreadsheet.add_worksheet(worksheet, rows=1000, cols=len(COLUMNS))
        if self.ws.row_values(1) != COLUMNS:
            self.setup()

    def setup(self) -> None:
        """Header, frozen first row, status dropdown."""
        self.ws.update([COLUMNS], "A1")
        self.ws.format("A1:I1", {"textFormat": {"bold": True}})
        self.ws.freeze(rows=1)
        self.ws.spreadsheet.batch_update(
            {
                "requests": [
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": self.ws.id,
                                "startRowIndex": 1,
                                "startColumnIndex": 5,
                                "endColumnIndex": 6,
                            },
                            "rule": {
                                "condition": {
                                    "type": "ONE_OF_LIST",
                                    "values": [{"userEnteredValue": s} for s in STATUSES],
                                },
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    }
                ]
            }
        )

    def append(self, lead: Lead) -> str:
        resp = self.ws.append_row(lead.row(), value_input_option="USER_ENTERED")
        # updatedRange looks like "Leads!A5:I5"
        rng = resp.get("updates", {}).get("updatedRange", "")
        row = rng.split("!A")[-1].split(":")[0] if "!A" in rng else ""
        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit#gid={self.ws.id}"
        return f"{url}&range=A{row}" if row else url

    def records(self) -> list[dict]:
        return self.ws.get_all_records(expected_headers=COLUMNS)
