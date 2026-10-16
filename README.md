# Personal Voice Assistant — first working milestone

A Python project you can extend into your own daily assistant. An iPhone
Shortcut requests a briefing from FastAPI, extracts its `speech` field, and
reads it with Speak Text. Apple Clock can trigger that Shortcut when you stop
a selected alarm.

This starter implements the briefing service. Your iPhone automation still
needs to be created and tested on your phone.

## What works now

- An authenticated `GET /briefing` endpoint.
- Morning briefings from manually entered events and tasks.
- `mode=now&available_minutes=20` for a suggested task.
- Local New York dates, ongoing shifts, overdue tasks, and completed-task filtering.
- A 10-minute transition buffer before the next entered event. It does not
  calculate travel time or know about commitments absent from your data.
- Optional AI wording through the OpenAI Responses API, with a template fallback.
- Spoken labels for fictional examples, disconnected sources, and old manual data.
- Offline behavior tests.

Email, calendar syncing, Notion syncing, live market prices, background polling,
conversational voice, screen access, and Alarmy integration are future work.
Neither the service nor its sample data represents a live account connection.

## 1. Set up Python on Windows

Use Python 3.12 or newer and a terminal opened in this extracted project folder.
You can get Python from [python.org](https://www.python.org/downloads/).

Create an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_project.py
```

If your installation uses the `py` launcher, use `py -3` instead of `python`
for the first command. The later commands use the environment's exact Python
path, so PowerShell activation policies do not get in the way.

Setup creates two private files:

- `.env`: a random assistant token and your local settings.
- `data.json`: fictional events and tasks dated for the day you run setup.

Running setup again preserves existing files. It does not refresh old sample
dates. No key or connected account is required for template mode.

## 2. Start and test the service on your computer

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Leave that terminal running. In a second terminal, in the same project folder:

```powershell
$assistantToken = .\.venv\Scripts\python.exe -c "from dotenv import dotenv_values; print(dotenv_values('.env')['ASSISTANT_TOKEN'])"
$assistantHeaders = @{ Authorization = "Bearer $assistantToken" }
$briefing = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/briefing' -Headers $assistantHeaders
$briefing.speech
```

You should see a response beginning with a demo label. Finished sample events
will be omitted depending on what time you run it.

For an on-demand suggestion:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/briefing?mode=now&available_minutes=20' -Headers $assistantHeaders
```

Stop the server with Ctrl+C. For phone access, use the LAN setup in
[iphone-shortcut.md](iphone-shortcut.md); `127.0.0.1` on your phone refers to
your phone, not your computer.

## 3. Make it speak after your alarm

Follow [iphone-shortcut.md](iphone-shortcut.md). First test a Shortcut with a
fixed sentence, then the API response, and finally the alarm trigger. This
separates audio permissions, network problems, and your Python code.

Your acceptance test is: stop a temporary Apple Clock alarm with the phone
locked and hear a clearly labeled demo briefing. Do not depend on it for a
real work morning until that test succeeds on your device.

## 4. Replace examples with your own manual data

Open `data.json` in your editor. Replace example entries, set `is_demo` to
`false`, and set `updated_at` to the current time. This flag only changes the
demo label; it does not connect accounts.

All timestamps need an explicit UTC offset, such as `2026-10-16T06:00:00-04:00`,
or a trailing `Z` for UTC. Offsets must match the date's daylight-saving status.
The server displays times in `ASSISTANT_TIMEZONE`, defaulting to New York.
Use the real date of each event, rather than reusing the example date daily.

Event fields: `title`, `start`, `end`. End must follow start.

Task fields: `title`, `due` (timestamp or null), `priority` (`high`, `medium`,
or `low`), `estimated_minutes`, `completed` (true or false).

The service selects overdue tasks first, then priority, then due time. The
briefing includes up to five remaining events and three pending tasks. On-demand
suggestions can select another pending task if it fits the available time.
Estimates and manually entered schedules can be incomplete; recommendations
are candidates for you to choose from.

Data more than 36 hours old gets a spoken warning. Do not change `updated_at`
unless you have actually checked the data. Save the complete valid JSON file
before making another request.

## 5. Enable optional AI summaries

Edit your local `.env`:

```dotenv
USE_AI=true
OPENAI_API_KEY=your-own-api-key
OPENAI_MODEL=a-text-model-id-available-in-your-api-account
```

Replace those placeholder values, then restart the server. Do not paste your
API key into chat, into your Shortcut, or into a committed file. The Shortcut
uses only your assistant token; the model key stays on the service.

With AI enabled, the selected event and task details are sent to OpenAI to
generate wording. This starter requests `store=False`; that is an API setting,
not a claim about all provider retention policies. ChatGPT and API billing are
separate. No paid API request has been made while testing this starter.

If credentials are absent or a request fails, the service explicitly announces
the fallback and returns the standard briefing. The SDK is configured for no
automatic retries and a 12-second timeout. End-to-end response time still needs
testing on your network. The response tells you `engine` and `ai_status`.

## Learn the project

| File | What you can learn or change |
| --- | --- |
| `setup_project.py` | Create local configuration and fictional starting data. |
| `briefing.py` | Validate data, rank tasks, handle dates, and write fallback speech. |
| `main.py` | Build routes, verify tokens, load data, and call the AI provider. |
| `test_assistant.py` | Exercise behavior without using your accounts or API credits. |
| `iphone-shortcut.md` | Connect and test the phone trigger and spoken output. |

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

The `requirements.txt` direct dependencies are pinned to the versions used for
the local verification. `requirements-lock.txt` also pins their transitive
dependencies. Use `-r requirements-lock.txt` for that complete tested set.

## Next milestones

1. Connect Google Calendar read-only and replace manual event loading with a
   source adapter. Verify all-day events, recurring events, and timezone handling.
2. Choose the source for your work shifts. Calendar events, a supported work
   scheduling integration, or manually entered shifts are separate choices.
3. Connect your assignment tracker read-only and map due dates and status fields.
4. Connect Gmail read-only; rank messages using sender, requested action, deadlines,
   and your own feedback. Treat email text as untrusted data, not instructions.
5. Add a market-data provider with timestamps and explicit delay/session labels.
6. Add authenticated HTTPS hosting and scheduled refreshes so your PC need not
   stay awake. Precompute/cache briefings if live generation is too slow.
7. Add voice questions, notification preferences, and later a companion interface.

Account authorizations belong to this project. Connections inside ChatGPT do
not automatically grant this service access. Screen awareness can be a later,
separate feature with controls for when capture is active.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `python` opens the Microsoft Store or is missing | Install Python or try your installed `py -3` launcher. |
| HTTP 401 | Shortcut's Authorization header must be `Bearer ` followed by the exact assistant token. |
| HTTP 503 | Run setup; validate data.json, timestamps, and the token configuration. |
| Phone cannot connect | Server binding, PC IP, same network, private-network firewall access, PC sleep state. |
| AI unavailable | Model ID, API account access/billing, key, network. Template mode still works. |
| No spoken output | Test fixed Speak Text first; check media volume, audio route, and phone-lock behavior. |
| No events listed | Sample times may have ended or the examples may be dated for another day. |

## Technical references

- [Apple: alarm event triggers](https://support.apple.com/guide/shortcuts/event-triggers-apd932ff833f/ios)
- [Apple: API requests in Shortcuts](https://support.apple.com/guide/shortcuts/request-your-first-api-apd58d46713f/ios)
- [FastAPI: first steps](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [OpenAI: text generation](https://developers.openai.com/api/docs/guides/text)
- [OpenAI: separate ChatGPT and API billing](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)

Verified locally: the offline behavior tests and local HTTP service. Not verified
on your device: the iPhone Shortcut, locked-phone playback, alarm automation,
LAN/firewall access, or a live paid model request.
