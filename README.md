# dbai local AI agent

dbai is a local, lightweight CLI AI agent designed for general use with a focus on low token use.

Designed to run on locally hosted LLMs through the [LM Studio](https://lmstudio.ai/) server.

The agent provides an interactive terminal interface that provides support for:

- Local LLM conversations.
- Switching models mid-session without restarting.
- Reading files directly from chat.
- Creating and modifying files, with targeted edits to existing files.
- Retrieving public web pages with *explicit user approval*.
- Executing terminal commands with *explicit user approval*.
- Conversation management.
- Token usage report.


## Install

To install:
1. `cd dbai`
2. Make the install script executable with `chmod +x install.sh`
3. Run the install script with `./install.sh`

Start the LM Studio server before starting the agent (see [Requirements](#lm-studio) below).


## Features
The main features include the following options. More options are available at `/help`.

### Chat

Start the agent directly from the terminal:
```bash
dbai
```

And select your desired model.

---

### `/model`

Switch to a different model without restarting dbai.

```text
/model
```

Lists every model in your LM Studio catalog and lets you pick by number. You can also select to a model by name:

```text
/model qwen2.5-coder-7b-instruct
```

dbai unloads the current model and loads the new one using LM Studio's `lms` command-line tool. dbai automatically rebuilds context for you, along with any files still added via `/read`, as a single message so the new model picks up where the last one left off. 

Nothing is lost, but note that this context replay is sent as fresh input, so it does add to that turn's token usage.

If loading the new model fails for any reason, dbai attempts to reload your previous model automatically.

---

### `/read`
Adds text files to the AI's context. Wildcards are supported, as well as recursive patterns.

```text
/read hello.c
```

```text
/read *.md
```

```text
/read **/*.py
```

Using `.` reads all files in the current directory:

```text
/read .
```

The files remain available to the AI as part of the conversation history.

---

### `/read-ls`

Display the files currently added to the conversation:

```text
/read-ls
```

---

### `/files`

List files underneath the current directory:

```text
/files
```

Hidden directories are ignored.

---

### `/write`

Ask the AI to create or modify a file.

For example:

```text
/write create a C program called hello.c that prints every number from 1 to 100
```

The AI generates the file contents and the program writes the resulting file to disk.

*The `/write` command is intended to allow the AI to work with files without requiring the user to manually create or write the files themselves.*

---

### `/run`

Ask the AI to generate a terminal command.

For example:

```text
/run compile hello.c into an executable called hello
```

The command is then displayed and the user must explicitly approve it.

```text
<run_command>
gcc hello.c -o hello
</run_command>
```

The command will **not** execute unless the user enters `yes`.

---

### `/web`

Ask the AI to retrieve public web pages to help answer your question.

For example:

```text
/web what's the latest stable version of Rust?
```

The AI requests one or more URLs to fetch, and each request is displayed and requires explicit approval before anything is downloaded:

```text
<get_url>
https://example.com
</get_url>
```

The page will **not** be fetched unless the user enters `yes`.

How `/web` works:

- **GET only.** dbai never sends any other HTTP method — it can only read pages, never submit forms or trigger actions.
- **Public URLs only.** Requests to `localhost`, loopback addresses, and private/internal IP ranges (`10.x`, `172.16–31.x`, `192.168.x`, `.local` hosts) are rejected automatically, even if the AI requests them.
- **HTML is converted to plain text** before being added to context, stripping scripts, styles, and markup so the model gets readable content instead of raw HTML.
- **Content is capped** at roughly 12,000 characters per page to keep token usage predictable, anything beyond that is truncated.
- **Up to 3 URLs per request, and up to 3 retrieval rounds** per `/web` command, so the AI can follow up with another page if the first one wasn't enough.

---

## Requirements

### Operating system

This project is intended to run on Linux, tested on Ubuntu 26.04 LTS.

### Python

Python 3 is required.

Check your version:

```bash
python3 --version
```

### LM Studio

You must have [LM Studio](https://lmstudio.ai/) installed and running locally, with its OpenAI-compatible local server enabled.

The application currently connects to:

```text
http://localhost:1234/v1
```

The API key is:

```text
lm-studio
```

This is the local API configuration used by LM Studio and is not a secret API key.

`/model` also requires LM Studio's `lms` command-line tool to be available on your `PATH`. `lms` ships with LM Studio itself, but needs to be bootstrapped once:

```bash
~/.lmstudio/bin/lms bootstrap
```

Open a new terminal afterward and confirm it worked by running `lms`.

## Disclaimer

This software is provided AS-IS, without warranty of any kind.

This agent provides the AI with read/write/execute control on your terminal, filesystem, and computer, as well as the ability to request web page retrieval. Run it at your own risk and review every command or URL before accepting it.

I'm not responsible for misuse of this tool.

---

Made with ❤️ by Dario Simpson