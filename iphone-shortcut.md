# iPhone setup: Apple Clock → your Python service → speech

Create this manually in Apple's Shortcuts app. No signed `.shortcut` file is
included. Menu wording may vary with your iOS version.

## A. Test the alarm and speaker before networking

1. In Shortcuts, create a new shortcut named **Morning Briefing Test**.
2. Add a **Text** action containing a short test sentence.
3. Add **Speak Text**, with the Text action's output as its input.
4. Run it manually. Approve any first-run requests, adjust media volume, and
   confirm whether sound is routed to your phone or Bluetooth headphones.
5. Create a temporary alarm in Apple Clock for a few minutes from now.
6. In Shortcuts → Automation, create an **Alarm** automation, choose **Is Stopped**,
   and select that specific test alarm. Choose **Run Immediately** or the available
   equivalent for automatic execution. Use **Run Shortcut** to run your test shortcut.
7. Lock the phone. When the alarm rings, stop it and check whether speech plays.

Complete the fixed-text test before making the automation call Python.

Apple's documented Clock alarm trigger does not establish support for Alarmy.
Alarmy dismissal integration is unverified and is not part of this version.
Using “Alarmy is closed” would be a different event from successfully dismissing
an alarm, so this guide does not substitute that trigger.

## B. Make your computer reachable on your home network

On your computer, stop the localhost-only server with Ctrl+C and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

In another terminal, run `ipconfig` and find the IPv4 address of your active
Wi-Fi/Ethernet connection, for example `192.168.1.42`. The example is not your
actual address. Keep your iPhone and computer on the same trusted home network.
If Windows prompts for firewall access, allow only your trusted private network.
Guest networks or client isolation can prevent devices from reaching each other.

On the iPhone, open `http://YOUR-PC-IP:8000/health` in Safari. Replace `YOUR-PC-IP`
with the actual address. You should see a small JSON status response. Do not
use `0.0.0.0` or `127.0.0.1` as the phone's server address.

This HTTP setup is for a trusted local development network using fictional data.
The bearer token is not encrypted over HTTP. Before using sensitive real data,
set up authenticated HTTPS or an encrypted private network. Do not forward port
8000 to the internet. This starter has no public-service rate limiting.

## C. Create the API-backed briefing shortcut

Create a new shortcut named **Morning Briefing** with these actions in order:

| Order | Action | Setting |
| --- | --- | --- |
| 1 | URL | `http://YOUR-PC-IP:8000/briefing` for the fictional LAN test; use your HTTPS URL for real data. |
| 2 | Get Contents of URL | Method: GET. Add header `Authorization` with value `Bearer YOUR-ASSISTANT-TOKEN`. |
| 3 | Get Dictionary Value | Get the value for key `speech` from Contents of URL. |
| 4 | If | Check that Dictionary Value has a value. |
| 5 | Speak Text | Speak Dictionary Value inside the If branch. |
| 6 | Otherwise | Add Show Notification with a brief message that the briefing is unavailable. |
| 7 | End If | End the conditional. |

Read `ASSISTANT_TOKEN` from your computer's private `.env`; copy just its value
after the equals sign, without quotes or spaces. This token is different from
an OpenAI API key. Never put an OpenAI API key in this Shortcut.

Run the shortcut manually while the server is running. Authorize the network
request when prompted. It should speak a clearly labeled fictional briefing.
The If branch handles a missing speech field; transport errors may stop the
Shortcut before that branch. A network-outage fallback is a later improvement.

## D. Attach the real shortcut to a test alarm

Change your test automation to run **Morning Briefing**. Repeat the locked-phone
test and confirm that it requests the service and speaks. If it fails, work
backward: manual API shortcut, `/health`, then fixed-text alarm test.

Once it works, select your actual morning Clock alarm. Keep only the automation
you want enabled to avoid duplicate briefings. If you delete and recreate the
Clock alarm later, check which alarm the automation references.

Your computer must be awake, the Python server running, and the address reachable
when the alarm is dismissed. A home LAN address will not work over cellular.
Your computer's address can change; reserve it in your router or update the URL.
An always-on HTTPS service is the later everyday-use milestone.

## E. Add an on-demand shortcut

Duplicate **Morning Briefing**, rename it **Brief Me Now**, and change the URL to:

```text
http://YOUR-PC-IP:8000/briefing?mode=now&available_minutes=20
```

Use your HTTPS address for real data. You can later replace the number with an
Ask for Input action and add the shortcut to your Home Screen. The Python service
will shorten that window if the next entered event starts sooner, leaving a
10-minute transition buffer, and will avoid suggesting a task during an ongoing
entered event. It does not know your commute or events missing from the file.
