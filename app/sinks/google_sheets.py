"""Google Sheets storage via a service account (docs/GOOGLE_SETUP.md)."""

from pathlib import Path

import gspread

from app.models import COLUMNS, HEADERS, STATUS_LABELS, Lead

# Pixel widths for COLUMNS, so dates, phones and comments are readable without resizing
WIDTHS = [130, 150, 130, 130, 320, 110, 130, 180, 200]


class GoogleSheet:
    def __init__(
        self, credentials_file: Path, sheet_id: str, worksheet: str = "Leads", lang: str = "ru"
    ):
        self.sheet_id = sheet_id
        self.lang = lang
        client = gspread.service_account(filename=str(credentials_file))
        spreadsheet = client.open_by_key(sheet_id)
        try:
            self.ws = spreadsheet.worksheet(worksheet)
        except gspread.WorksheetNotFound:
            self.ws = spreadsheet.add_worksheet(worksheet, rows=1000, cols=len(COLUMNS))
        if self.ws.row_values(1) != HEADERS[lang]:
            self.setup()

    def setup(self) -> None:
        """Header, frozen first row, column widths, status dropdown."""
        self.ws.update([HEADERS[self.lang]], "A1")
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
                                    "values": [
                                        {"userEnteredValue": s} for s in STATUS_LABELS[self.lang]
                                    ],
                                },
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    },
                    *(
                        {
                            "updateDimensionProperties": {
                                "range": {
                                    "sheetId": self.ws.id,
                                    "dimension": "COLUMNS",
                                    "startIndex": i,
                                    "endIndex": i + 1,
                                },
                                "properties": {"pixelSize": width},
                                "fields": "pixelSize",
                            }
                        }
                        for i, width in enumerate(WIDTHS)
                    ),
                ]
            }
        )

    def append(self, lead: Lead) -> str:
        # RAW keeps "+7..." phones and "YYYY-MM-DD HH:MM" dates as text (USER_ENTERED reformats)
        resp = self.ws.append_row(lead.row(self.lang), value_input_option="RAW")
        # updatedRange looks like "Leads!A5:I5"
        rng = resp.get("updates", {}).get("updatedRange", "")
        row = rng.split("!A")[-1].split(":")[0] if "!A" in rng else ""
        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit#gid={self.ws.id}"
        return f"{url}&range=A{row}" if row else url

    def records(self) -> list[dict]:
        # keyed by position, so reports work with any header language
        return [dict(zip(COLUMNS, r, strict=False)) for r in self.ws.get_all_values()[1:] if any(r)]
