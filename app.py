import streamlit as st
import anthropic
import requests
import json

# ---------- page setup ----------
st.set_page_config(page_title="Daily Log Agent", page_icon="🏗️")
st.title("🏗️ Daily Log Agent")
st.caption("Paste messy field notes - get a formatted daily report. Built for the Construction AI Summit 2026.")

# ---------- simple access code ----------
access = st.text_input("Access code", type="password")
if access != st.secrets["ACCESS_CODE"]:
    st.info("Enter the access code from the bootcamp session to use the agent.")
    st.stop()

# ---------- connect to Claude ----------
client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# ---------- weather tool ----------
def get_weather(location, date):
    api_key = st.secrets["WEATHER_API_KEY"]
    url = "https://api.openweathermap.org/data/2.5/weather"
    query = location.replace(", ", ",")
    if query.count(",") == 1:
        query = query + ",US"
    params = {"q": query, "appid": api_key, "units": "imperial"}
    response = requests.get(url, params=params)
    data = response.json()
    if response.status_code != 200:
        return {"error": f"Weather lookup failed: {data.get('message', 'unknown error')}"}
    return {
        "location": location,
        "date": date,
        "note": "Current conditions",
        "conditions": data["weather"][0]["description"],
        "temp_f": round(data["main"]["temp"]),
        "high_f": round(data["main"]["temp_max"]),
        "low_f": round(data["main"]["temp_min"]),
        "wind_mph": round(data["wind"]["speed"]),
        "humidity_pct": data["main"]["humidity"]
    }

weather_tool = {
    "name": "get_weather",
    "description": "Gets weather for a location on a date. Location must be a city and state like 'Tempe, AZ' - never a street address. Use this when field notes don't mention weather.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City and state, e.g. 'Tempe, AZ'"},
            "date": {"type": "string", "description": "Date of the log"}
        },
        "required": ["location", "date"]
    }
}

# ---------- the template ----------
my_template = """
# DAILY CONSTRUCTION REPORT

**PROJECT:** ___  **DATE:** ___
**AUTHOR:** ___  **DAY OF WEEK:** ___

---

## SUMMARY
(one or two sentence overview of the day's work)

## WEATHER
Conditions: ___ | High/Low: ___ | Wind: ___ | Humidity: ___

## MANPOWER
(list each trade and count)

## EQUIPMENT ON SITE
(list equipment)

## WORK PERFORMED
(numbered list of work items, as many as needed)

## MATERIALS USED / DELIVERED
(list materials)

## DELAYS / ISSUES
(describe, or 'None reported')

## SAFETY
Incidents: ___ | Notes: ___

## PLANNED FOR TOMORROW
(list items)

---
*The information contained in this report represents, to the best
knowledge of the preparer, the activities and events that occurred
based on site observations made at the time.*
"""

# ---------- the agent ----------
def notes_to_report(messy_notes):
    system_prompt = f"""You are a construction administrative assistant.
Convert the contractor's rough notes into a daily report using EXACTLY
this template - same sections, same order, same headings:

{my_template}

Rules:
- Fill in only what the notes support. Write 'Not reported' for any
  field the notes don't mention.
- If weather is missing, use the get_weather tool. If the notes give
  only a street address, ask for or infer the city; never pass a
  street address to the tool.
- Never invent details."""

    messages = [{"role": "user", "content": messy_notes}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system_prompt,
            tools=[weather_tool],
            messages=messages
        )
        if response.stop_reason == "tool_use":
            tool_call = next(b for b in response.content if b.type == "tool_use")
            result = get_weather(**tool_call.input)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(result)
                }]
            })
        else:
            return response.content[0].text

# ---------- the page ----------
notes = st.text_area("Paste your field notes here:", height=200,
                     placeholder="6 guys framing today started 7am, concrete late again...")

if st.button("Generate Daily Report", type="primary"):
    if notes.strip():
        with st.spinner("Agent is working..."):
            report = notes_to_report(notes)
        st.markdown(report)
        st.download_button("Download report", report, file_name="daily_report.md")
    else:
        st.warning("Paste some notes first.")