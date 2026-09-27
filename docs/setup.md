# Setting up the driving assistant

This guide covers setup from start to finish. You do each step once, and the whole thing takes about 45 minutes.

**What you end up with:** you say *"Hey Siri, Ask My Assistant"* in the car, then speak a request such as "Any important emails this morning?" or "Reply to Mike and say I'll call him after 3". Siri speaks back a short answer. Emails are **only sent after you say "yes"** to a read-back of the draft.

```
iPhone Shortcut ──(your words)──▶ Python service (your Mac) ──▶ Claude + Gmail
       ◀──────────(short spoken answer)──────────┘
```

---

## 1. Install Python packages

On your Mac, in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Get a Claude API key

1. Go to https://console.anthropic.com, sign in, and add a payment method.
2. Under **API Keys**, create a key.
3. Copy `.env.example` to `.env` and paste the key after `ANTHROPIC_API_KEY=`.
4. Create the assistant password and paste it after `ASSISTANT_TOKEN=`:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

**Cost:** each spoken request typically costs a few cents (roughly 2–10¢, depending on how many emails it reads). You can set a monthly spending limit in the console.

## 3. Give the assistant access to Gmail

1. Go to https://console.cloud.google.com and create a project (any name, e.g. "My-Ai").
2. **APIs & Services → Library**: search for **Gmail API** and click **Enable**.
3. **APIs & Services → OAuth consent screen**: choose **External**, fill in the app name and your email, and add your own Gmail address under **Test users**.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**, then choose **Desktop app**. Download the JSON file and save it in the project folder as `credentials.json`.
5. Run the one-time sign-in:
   ```bash
   python scripts/authorize_gmail.py
   ```
   A browser window opens. Sign in and approve access. Google will warn that the app is unverified; that's expected, because it's your own private app. This creates `token.json`.

The assistant requests only **read** and **send** permission. It cannot delete email or change your Gmail settings.

**The Gmail sign-in expires every 7 days while the app is in "Testing" mode.** This is a Google rule for unpublished apps. When it expires, the assistant tells you it couldn't reach Gmail. Fix it by re-running `python scripts/authorize_gmail.py`. To stop the weekly expiry, go to the OAuth consent screen and click **Publish app**. You don't need Google's review for your own account.

`credentials.json`, `token.json` and `.env` are all listed in `.gitignore`, so they never get uploaded to GitHub.

## 4. Start the service

```bash
uvicorn assistant.server:app --host 0.0.0.0 --port 8000
```

Check it's running by opening http://localhost:8000/health. It should show `{"ok": true}`.

## 5. Let your iPhone reach your Mac from anywhere

While you're driving, your phone is on cellular data, not your home Wi-Fi. The simplest private way to connect them is **Tailscale**, which is free for personal use:

1. Install Tailscale on your Mac (https://tailscale.com/download) and on your iPhone (App Store). Sign in to both with the same account.
2. In the Tailscale app on the Mac, note the Mac's name, e.g. `my-macbook`.
3. Your service address is now `http://my-macbook:8000/ask`. It works only from your own devices.

The Mac has to be on and awake with the service running. To keep it awake, go to System Settings → Battery/Energy and turn on **Prevent automatic sleeping when the display is off**. Moving the service to a small cloud server removes this requirement; that's a later roadmap step.

## 6. Build the iPhone Shortcut

Open the **Shortcuts** app, tap **+**, and name the shortcut **Ask My Assistant**. The name is what you say to Siri. Add these actions in order:

1. **Repeat** (set it to 10 times). This lets you have a back-and-forth conversation without saying "Hey Siri" again. Put steps 2–7 inside the Repeat.
2. **Dictate Text**, with *Stop Listening* set to **After Pause**.
3. **If** *Dictated Text* **contains** `goodbye`, then add **Stop This Shortcut**, then **End If**. Saying "goodbye" or "that's all, goodbye" ends the conversation.
4. **Get Contents of URL**:
   - URL: `http://my-macbook:8000/ask` (use your Mac's Tailscale name)
   - Method: **POST**
   - Headers: `Authorization` = `Bearer ` followed by your ASSISTANT_TOKEN (note the space after "Bearer")
   - Request Body: **JSON**, with one field `text` (Text) = *Dictated Text*
5. **Get Dictionary Value**: key `speech`, taken from *Contents of URL*.
6. **Speak Text**: *Dictionary Value*.
7. (End of Repeat.)

**Test it with the car parked first.** Say "Hey Siri, Ask My Assistant", then try:
- "Do I have any unread emails today?"
- "Read me the one from the bank."
- "Is that email a scam?"
- "Reply and say thanks, I'll look at it tonight." The assistant reads the draft back and asks "Should I send it?". Answer "yes" or "no".

If **Dictate Text** doesn't work through CarPlay, replace it with **Ask for Input** (Input Type: Text). When the shortcut is run by Siri, Siri asks for the input by voice.

---

## How sending is kept safe

- Claude can only **prepare** a draft. It has no ability to send.
- The Python code sends a draft only if your **very next** reply is a plain "yes", "send it" or "go ahead". Anything else, including "yes but change the time", is treated as a new instruction.
- A draft is thrown away if you say anything else, or after 10 minutes of silence.
- Suspicious emails (payment pressure, gift cards, password "verification", mismatched senders) are called out out loud first.

## Running the tests

```bash
pip install pytest
python -m pytest
```

The tests use a fake Claude and a fake Gmail, so they need no keys or network access.
