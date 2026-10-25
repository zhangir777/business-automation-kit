from . import generic_json, google_form, tilda

SOURCES = {
    "tilda": tilda.parse,
    "json": generic_json.parse,
    "google-form": google_form.parse,
}
