import os

import streamlit as st
from decouple import config, UndefinedValueError

SPREADSHEET_ID = config("SPREADSHEET_ID")


def main():
    st.write("## GenAI community appeal form")

    if st.session_state.get("success"):
        st.success("Thanks! You'll not be removed from the group.")
        return

    if "query" not in st.session_state:
        st.session_state["query"] = (
            st.experimental_get_query_params().get("q", [""])[0] or ""
        ).strip()

    with st.form("search"):
        st.write("Enter your Name (or whatever alias you have on whatsapp)")
        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input(
                "name",
                label_visibility="collapsed",
                placeholder="John Appleseed",
                key="query",
            ).strip()
        with col2:
            submitted = st.form_submit_button("Search")

    if submitted:
        st.experimental_set_query_params(q=query)
        last_query = st.session_state.get("last_query")
        if last_query != query:
            st.session_state["last_query"] = query
            st.session_state.pop("cached_result", None)

    spreadsheets = get_spreadsheet_service()

    if "cached_result" not in st.session_state:
        with st.spinner("Searching..."):
            st.session_state["cached_result"] = find_row(spreadsheets, query)
    cached_result = st.session_state["cached_result"]
    if not cached_result:
        st.error("No results found")
        return
    row, details = cached_result

    header = get_header(spreadsheets)
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}#gid=0?range={row}:{row}"
    st.write(f"### [Row {row}]({url})")
    for k, v in zip(header, details):
        st.write(f"**{k}**: {v}")
    st.write("---")

    if st.checkbox("I confirm that the information above is correct, and is mine."):
        st.warning("Are you sure?")
        if st.button("Yes, I'm here and please don't remove me!"):
            with st.spinner("Running..."):
                delete_row(spreadsheets, row, details)
                st.session_state["success"] = True
                st.session_state.pop("cached_result", None)
                st.experimental_rerun()


def delete_row(spreadsheets, row, details):
    spreadsheets.batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": 0,
                            "dimension": "ROWS",
                            "startIndex": row - 1,
                            "endIndex": row,
                        },
                    },
                },
                {
                    "appendCells": {
                        "sheetId": 1,
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {
                                            "stringValue": v,
                                        },
                                    }
                                    for v in details
                                ],
                            },
                        ],
                        "fields": "*",
                    }
                },
            ],
        },
    ).execute()


def find_row(spreadsheets, query: str) -> tuple[int, list[str]] | None:
    # find query in spreadsheet
    names = (
        spreadsheets.values()
        .get(spreadsheetId=SPREADSHEET_ID, range="A2:A")
        .execute()
        .get("values", [])
    )
    for i, name in enumerate(names):
        name = name and name[0]
        if not name:
            continue
        if query.upper() in name.upper():
            row = i + 2
            details = (
                spreadsheets.values()
                .get(spreadsheetId=SPREADSHEET_ID, range=f"{row}:{row}")
                .execute()
                .get("values", [[]])[0]
            )
            if not details:
                continue
            return row, details


@st.cache_resource
def get_header(_spreadsheets) -> list[str]:
    header = (
        _spreadsheets.values()
        .get(spreadsheetId=SPREADSHEET_ID, range="1:1")
        .execute()
        .get("values", [[]])
    )[0]
    assert header, "No header found in spreadsheet"
    return header


def get_spreadsheet_service():
    from oauth2client.service_account import ServiceAccountCredentials
    from googleapiclient.discovery import build

    # Authenticate with the Google Sheets API using a service account
    scope = [
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        get_service_account_key_path(), scope
    )
    service = build("sheets", "v4", credentials=creds)
    return service.spreadsheets()


@st.cache_resource
def get_service_account_key_path() -> str:
    service_account_key_path = "serviceAccountKey.json"
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_key_path
    # save json file from env var if available
    try:
        _json = config("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    except UndefinedValueError:
        pass
    else:
        with open(service_account_key_path, "w") as f:
            f.write(_json)

    return service_account_key_path


if __name__ == "__main__":
    main()
