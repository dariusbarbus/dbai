#!/usr/bin/env python3

import os
import sys
import glob
import readline
import re
import subprocess

from openai import OpenAI


BASE_URL = "http://localhost:1234/v1"

API_KEY = "lm-studio"


# API client
client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


# Commands used for tab autocomplete
COMMANDS = [
    "/help",
    "/files",
    "/read",
    "/read-ls",
    "/write",
    "/run",
    "/tokens",
    "/clear",
    "/exit",
]


def get_models():
    # Lists the client's available models.
    models = client.models.list()

    return [m.id for m in models.data]


def read_files(pattern):
    # If "." is used, read all files in the current directory.
    if pattern == ".":
        files = [
            os.path.join(".", name)
            for name in os.listdir(".")
            if os.path.isfile(os.path.join(".", name))
        ]
    else:
        # Find files matching the supplied pattern.
        # This can be a filename, wildcard, or recursive glob.
        files = glob.glob(pattern, recursive=True)

    # Stop if the pattern didn't match anything.
    if not files:
        print(f"No files found: {pattern}")
        return "", []

    # This will hold the contents of all matching files.
    result = []

    # This will hold the filenames successfully added to the conversation.
    added_files = []

    # Process every matching path.
    for path in files:

        # Ignore directories; only read actual files.
        if not os.path.isfile(path):
            continue

        try:
            # Open the file as UTF-8 text.
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Add the filename and its contents to the result.
            # The markers make it clear to the AI where each file starts
            # and ends.
            result.append(
                f"\n===== FILE: {path} =====\n"
                f"{content}\n"
                f"===== END FILE =====\n"
            )

            # Remember this file so /read-ls can display it later.
            added_files.append(path)

        except Exception as e:
            # If a file can't be read, report the error and continue.
            print(f"Could not read {path}: {e}")

    # Combine all file contents into one string.
    return "\n".join(result), added_files


def write_ai_files(answer):
    # Find files that the AI requested to create or overwrite.
    #
    # The AI must use this format:
    #
    # <write_file path="filename.ext">
    # file contents
    # </write_file>

    pattern = r'<write_file path="([^"]+)">(.*?)</write_file>'

    matches = re.findall(pattern, answer, re.DOTALL)

    # Process every file requested by the AI.
    for path, content in matches:

        try:
            # Create the parent directory if one was specified.
            directory = os.path.dirname(path)

            if directory:
                os.makedirs(directory, exist_ok=True)

            # "w" creates the file if it doesn't exist.
            # If it already exists, it overwrites it.
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.strip("\n"))

            print(f"\nFile written: {path}")

        except Exception as e:
            # Report file-writing errors without crashing the program.
            print(f"\nCould not write {path}: {e}")


def run_ai_command(answer):
    # Find commands that the AI explicitly requested to execute.
    #
    # The AI MUST use this exact format:
    #
    # <run_command>
    # command here
    # </run_command>
    #
    # Commands outside this format are ignored.
    pattern = r"<run_command>\s*(.*?)\s*</run_command>"

    matches = re.findall(pattern, answer, re.DOTALL)

    # If the AI did not provide the required format,
    # nothing is executed.
    if not matches:
        print("\nNo valid <run_command> block was returned by the AI.")
        return None

    command_results = []

    # Every command requires its own approval.
    for command in matches:

        command = command.strip()

        # Ignore empty command blocks.
        if not command:
            print("\nEmpty <run_command> block ignored.")
            continue

        print()
        print("=" * 60)
        print("COMMAND REQUEST")
        print("=" * 60)
        print(command)
        print("=" * 60)
        print()

        # The command is NEVER executed automatically.
        approval = input(
            "Execute this command? Type 'yes' to approve: "
        ).strip().lower()

        # Require the full word "yes".
        #
        # This is intentionally stricter than accepting "y".
        if approval != "yes":
            print("Command NOT executed.")
            command_results.append(
                f"Command was rejected by the user:\n{command}"
            )
            continue

        print("\nExecuting command...\n")

        try:
            # Execute the command through the user's shell.
            # The command has already been explicitly approved by the user.
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
            )

            # Display stdout.
            if result.stdout:
                print(result.stdout, end="")

            # Display stderr.
            if result.stderr:
                print(result.stderr, end="")

            print()
            print(f"Command exited with code: {result.returncode}")

            # Save the result so the AI can see what happened.
            command_results.append(
                f"Command executed:\n"
                f"{command}\n\n"
                f"Exit code: {result.returncode}\n\n"
                f"STDOUT:\n"
                f"{result.stdout}\n\n"
                f"STDERR:\n"
                f"{result.stderr}"
            )

        except Exception as e:
            print(f"\nCould not execute command: {e}")

            command_results.append(
                f"Command could not be executed:\n"
                f"{command}\n\n"
                f"Error: {e}"
            )

    # Return all command results together.
    if command_results:
        return "\n\n".join(command_results)

    return None


def autocomplete(text, state):
    # Find commands that start with what the user has typed.
    matches = [
        command
        for command in COMMANDS
        if command.startswith(text)
    ]

    # readline calls this function repeatedly with different state values.
    if state < len(matches):
        return matches[state]

    return None


def main():
    # Enable tab autocomplete for commands.
    readline.set_completer(autocomplete)
    readline.parse_and_bind("tab: complete")

    # Get the models currently available from LM Studio.
    models = get_models()

    # Stop if LM Studio didn't return any models.
    if not models:
        print("No models available from LM Studio.")
        sys.exit(1)

    # Display the available models.
    print("Available models:")

    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")

    # Ask for the model.
    choice = input("\nSelect model: ").strip()

    try:
        # Select the model.
        model = models[int(choice) - 1]

    except (ValueError, IndexError):
        # Handle invalid input.
        print("Invalid selection.")
        sys.exit(1)

    # Show selected model.
    print(f"\nUsing: {model}")

    # Conversation history sent to the model.
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful local AI assistant. "
                "Follow the user's instructions exactly. "
                "Do not assume the user wants code or file modifications. "
                "Answer normal questions normally. "
                "When files are provided, use their contents as context. "

                "When the user uses /write, generate file contents using "
                "the required <write_file> format. "

                "When the user uses /run, generate terminal commands using "
                "ONLY the required <run_command> format. "
                "Never put executable commands outside a <run_command> block. "
                "Never assume that a command has been approved. "
                "The terminal program will ask the user for approval before "
                "executing every command."
            ),
        }
    ]

    # Files currently added through /read.
    read_files_list = []

    # Token information reported by LM Studio.
    last_prompt_tokens = None
    last_completion_tokens = None
    last_total_tokens = None

    # Main interactive chat loop.
    while True:

        try:
            # Display the current working directory before the prompt.
            user_input = input(
                f"{os.getcwd()} dbai> "
            ).strip()

        except (KeyboardInterrupt, EOFError):
            # Ctrl+C or Ctrl+D exits the program cleanly.
            print()
            break

        if not user_input:
            continue

        if user_input == "/exit":
            break

        if user_input == "/help":
            print()
            print("Available commands:")
            print("  /help        Show available commands")
            print("  /files       List files in current directory")
            print("  /read FILE   Add a file to context")
            print("  /read-ls     List files currently added to context")
            print("  /write DESC  Create or overwrite a file using AI")
            print("  /run DESC    Generate and run a command using AI")
            print("  /tokens      Show token count")
            print("  /clear       Clear conversation")
            print("  /exit        Exit")
            print()
            continue

        if user_input == "/tokens":

            if last_prompt_tokens is None:
                print("No token count available yet.")

            else:
                print(f"Prompt tokens:     {last_prompt_tokens:,}")
                print(f"Completion tokens: {last_completion_tokens:,}")
                print(f"Total tokens:      {last_total_tokens:,}")

            continue

        # Clear the conversation while keeping the system message.
        if user_input == "/clear":

            # messages[0] is the system message, so keep only that.
            messages = messages[:1]

            # Reset the displayed token information.
            last_prompt_tokens = None
            last_completion_tokens = None
            last_total_tokens = None

            # Clear the list of files added to the conversation.
            read_files_list = []

            print("Conversation cleared.")
            continue

        # List files and directories underneath the current directory.
        if user_input == "/files":

            # Walk through the current directory recursively.
            for root, dirs, files in os.walk("."):

                # Ignore hidden directories.
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                ]

                # Display files.
                for file in files:
                    path = os.path.join(root, file)
                    print(path)

            continue

        # Show files currently added through /read.
        if user_input == "/read-ls":

            if not read_files_list:
                print("No files have been added to the conversation.")

            else:
                print("Files currently added:")

                for path in read_files_list:
                    print(f"  {path}")

            continue

        if user_input.startswith("/read "):

            # Everything after "/read " is treated as the file pattern.
            pattern = user_input[6:].strip()

            # Read the matching files.
            content, added_files = read_files(pattern)

            # Only add to the conversation if files were found.
            if content:

                # Add the file contents as a user message.
                messages.append({
                    "role": "user",
                    "content": (
                        f"Here are the files I want you to read:\n\n"
                        f"{content}"
                    ),
                })

                # Remember which files were added.
                read_files_list.extend(added_files)

                print(f"Added files matching: {pattern}")

            continue

        if user_input.startswith("/write "):

            # Everything after "/write " is treated as the file creation request.
            request = user_input[7:].strip()

            if not request:
                print("Usage: /write DESCRIPTION")
                continue

            # Tell the AI to generate a file-writing block.
            messages.append({
                "role": "user",
                "content": (
                    "The user wants you to create or modify a file.\n\n"
                    f"User request:\n{request}\n\n"
                    "Generate the requested file using exactly this format:\n\n"
                    '<write_file path="filename.ext">\n'
                    "FILE CONTENT HERE\n"
                    "</write_file>\n\n"
                    "Do not use markdown code fences around the file. "
                    "If multiple files are required, output one write_file "
                    "block for each file."
                ),
            })

        elif user_input.startswith("/run "):

            # Everything after "/run " is treated as the command request.
            request = user_input[5:].strip()

            if not request:
                print("Usage: /run DESCRIPTION")
                continue

            # Tell the AI to generate a terminal command.
            messages.append({
                "role": "user",
                "content": (
                    "The user wants to execute a terminal command.\n\n"
                    f"User request:\n{request}\n\n"
                    "Determine the appropriate terminal command.\n\n"
                    "IMPORTANT:\n"
                    "Output the command ONLY inside this exact format:\n\n"
                    "<run_command>\n"
                    "COMMAND HERE\n"
                    "</run_command>\n\n"
                    "Do not put executable commands outside the "
                    "<run_command> block. "
                    "Do not use markdown code fences. "
                    "Do not claim that the command was executed. "
                    "The terminal program will ask the user for approval "
                    "before executing it."
                ),
            })

        else:
            # Anything that isn't a recognized command is treated as a
            # normal message for the AI.
            messages.append({
                "role": "user",
                "content": user_input,
            })

        try:
            # Send the entire conversation history to LM Studio.
            #
            # stream=True means the response is displayed as the model
            # generates it instead of waiting for the complete response.
            #
            # include_usage=True asks LM Studio to include actual token
            # usage information in the streaming response.
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                stream=True,
                stream_options={"include_usage": True},
            )

            # Store the complete response so it can be added to the
            # conversation history after streaming finishes.
            answer = ""

            # Create an empty line between the user's prompt and AI response.
            print()

            # Process each piece of the streaming response.
            for chunk in response:

                # LM Studio provides usage information in a final
                # streaming chunk.
                if chunk.usage is not None:

                    # Save the actual token counts reported by LM Studio.
                    last_prompt_tokens = chunk.usage.prompt_tokens
                    last_completion_tokens = chunk.usage.completion_tokens
                    last_total_tokens = chunk.usage.total_tokens

                # Some streaming chunks contain usage information only
                # and therefore don't contain any choices.
                if not chunk.choices:
                    continue

                # Get the newly generated text from this chunk.
                text = chunk.choices[0].delta.content

                # Print the text immediately and save it for the
                # conversation history.
                if text:
                    print(text, end="", flush=True)
                    answer += text

            # Move to a new line after the streamed response.
            print()

            # If this was a /write request, process any files requested
            # by the AI.
            if user_input.startswith("/write "):
                write_ai_files(answer)

            # If this was a /run request, process any commands requested
            # by the AI.
            command_result = None

            if user_input.startswith("/run "):
                command_result = run_ai_command(answer)

            # Add the completed AI response to the conversation history.
            messages.append({
                "role": "assistant",
                "content": answer,
            })

            # If a command was executed or rejected, give the result back
            # to the AI so it knows what happened.
            if command_result:
                messages.append({
                    "role": "user",
                    "content": command_result,
                })

        except Exception as e:
            # Display any API or connection errors without crashing
            # the entire program.
            print(f"\nError: {e}")


# Only run main() when this file is executed directly.
#
# This prevents main() from automatically running if this file is
# imported by another Python program.

# To run on the terminal you'll need:
#
# chmod +x ~/local-ai/ai.py
# mkdir -p ~/.local/bin
# ln -s ~/local-ai/ai.py ~/.local/bin/ai
# echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
# source ~/.zshrc

if __name__ == "__main__":
    main()