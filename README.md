# My-Ai

A personal AI assistant that handles my desktop work: the repetitive, time-consuming computer tasks that don't need my judgment, done accurately so I can focus on the work that does.

> **Status:** Early planning. No code yet. This README describes the goal and the intended design.

## Goal

Hand off routine computer work to an AI agent that can:

- Understand a task described in plain language
- Plan the steps needed to complete it
- Carry those steps out on my computer and in my online accounts
- Report back what it did, and stop to ask when something is unclear or risky

## Planned capabilities

| Area | Examples |
|------|----------|
| **Files & folders** | Sort downloads, rename and file scanned documents, clean up duplicates |
| **Email** | Triage the inbox, draft replies, flag anything that looks like a scam or phishing |
| **Calendar & scheduling** | Book meetings, find open time, send reminders |
| **Documents** | Draft reports, fill in templates, convert between PDF / Word / spreadsheets |
| **Spreadsheets & finances** | Update logs, reconcile records, organize tax documents |
| **Research** | Gather information from the web and summarize it with sources |
| **Desktop apps** | Operate applications by reading the screen and using the mouse and keyboard |

## Design principles

1. **Accuracy first.** Check results rather than guessing. When unsure, say so.
2. **Safety.** Stop and alert me to anything that looks fraudulent, like a scam or harmful. Confirm before irreversible actions such as deleting files, sending money or sending messages to new recipients.
3. **Privacy.** Keep secrets (API keys, passwords) out of the code and out of this repository. They live in a local `.env` file, which is excluded by `.gitignore`.
4. **Transparency.** Keep a log of every action taken so any task can be reviewed or undone.
5. **Efficiency.** Automate the recurring tasks, and make each new task quicker to set up than the last.

## Intended architecture

```
You (plain-language request)
        │
        ▼
  AI model (Claude) ── plans the task and chooses tools
        │
        ▼
  Tools / integrations
   ├─ File system
   ├─ Email & calendar
   ├─ Documents & spreadsheets
   ├─ Web browser
   └─ Desktop control (screen reading, mouse, keyboard)
        │
        ▼
  Action log + summary reported back to you
```

## Roadmap

- [ ] Choose the language and framework (likely Python with the Claude API / Agent SDK)
- [ ] Set up the project structure and secure secret handling (`.env`)
- [ ] First tool: file organization (sorting and renaming files)
- [ ] Add email and calendar integration
- [ ] Add document and spreadsheet handling
- [ ] Add browser and desktop control
- [ ] Add an action log and a review/undo step
- [ ] Schedule recurring tasks (for example, a daily inbox cleanup)

## Getting started

Setup instructions will be added once the first working version exists.

## License

Private, personal project. All rights reserved.
