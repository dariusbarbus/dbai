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


def get_file_content(path):
    # Read a single existing file.
    #
    # Return the file contents if successful.
    # Return None if the file cannot be read.
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        # Report the error without crashing the program.
        print(f"Could not read {path}: {e}")
        return None


def write_new_file(path, content):
    # Create a new file or overwrite a file when explicitly requested
    # through a write_file block.
    try:
        # Create the parent directory if one was specified.
        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        # Write the supplied content to the file.
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip("\n"))

        print(f"\nFile written: {path}")
        return True

    except Exception as e:
        # Report file-writing errors without crashing the program.
        print(f"\nCould not write {path}: {e}")
        return False


def apply_ai_edits(answer):
    # Find targeted edits returned by the AI.
    #
    # The AI must use this format:
    #
    # <edit_file path="hello.c">
    # <find>
    # exact existing text
    # </find>
    # <replace>
    # replacement text
    # </replace>
    # </edit_file>
    #
    # The existing text must occur exactly once.
    #
    # This prevents accidental modifications when the AI guesses
    # incorrectly or the file has changed.

    pattern = (
        r'<edit_file path="([^"]+)">\s*'
        r'<find>\s*(.*?)\s*</find>\s*'
        r'<replace>\s*(.*?)\s*</replace>\s*'
        r'</edit_file>'
    )

    matches = re.findall(
        pattern,
        answer,
        re.DOTALL,
    )

    # If the AI did not provide the required format,
    # nothing is modified.
    if not matches:
        print("\nNo valid <edit_file> block returned by the AI.")
        return

    # Process every edit requested by the AI.
    for path, find_text, replace_text in matches:

        # Remove only the formatting whitespace introduced around
        # the XML-like blocks.
        find_text = find_text.strip("\n")
        replace_text = replace_text.strip("\n")

        print()
        print("=" * 60)
        print("FILE EDIT REQUEST")
        print("=" * 60)
        print(f"File: {path}")
        print("=" * 60)

        # The file must exist for an edit.
        if not os.path.isfile(path):
            print("Edit rejected: file does not exist.")
            continue

        # Read the current version of the file.
        current_content = get_file_content(path)

        if current_content is None:
            continue

        # Count exact matches of the requested section.
        match_count = current_content.count(find_text)

        # Reject the edit if the target text does not exist.
        if match_count == 0:
            print("Edit rejected: target text was not found.")
            print("The file was NOT modified.")
            continue

        # Reject the edit if the target text appears more than once.
        if match_count > 1:
            print(
                f"Edit rejected: target text appears "
                f"{match_count} times."
            )
            print("The file was NOT modified.")
            continue

        # Show the section that is going to change.
        print()
        print("Existing section:")
        print("-" * 60)
        print(find_text)
        print("-" * 60)

        # Show the replacement text.
        print()
        print("Replacement:")
        print("-" * 60)
        print(replace_text)
        print("-" * 60)

        # Require explicit approval before modifying the file.
        approval = input(
            "\nApply this edit? Type 'yes' to approve: "
        ).strip().lower()

        # Only the full word "yes" approves the edit.
        if approval != "yes":
            print("Edit NOT applied.")
            continue

        # Apply exactly one replacement.
        new_content = current_content.replace(
            find_text,
            replace_text,
            1,
        )

        try:
            # Write the modified content back to the existing file.
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            print(f"\nFile updated: {path}")

        except Exception as e:
            # Report file-writing errors without crashing the program.
            print(f"\nCould not update {path}: {e}")


def write_ai_files(answer):
    # Find files that the AI requested to create.
    #
    # The AI must use this format:
    #
    # <write_file path="filename.ext">
    # file contents
    # </write_file>
    #
    # This is used only when the requested file does not already exist.

    pattern = r'<write_file path="([^"]+)">(.*?)</write_file>'

    matches = re.findall(
        pattern,
        answer,
        re.DOTALL,
    )

    # If the AI did not provide the required format,
    # nothing is written.
    if not matches:
        print("\nNo valid <write_file> block returned by the AI.")
        return

    # Process every file requested by the AI.
    for path, content in matches:

        # Never blindly overwrite an existing file.
        #
        # Existing files must be modified using <edit_file>.
        if os.path.exists(path):
            print()
            print("=" * 60)
            print("WRITE REJECTED")
            print("=" * 60)
            print(f"File already exists: {path}")
            print(
                "The AI must use <edit_file> to modify an existing file."
            )
            print("The existing file was NOT modified.")
            continue

        # Create the brand-new file.
        write_new_file(path, content)


def run_ai_command(answer):
    # Find commands that the AI explicitly requested to execute.
    #
    # The AI MUST use this format:
    #
    # <run_command>
    # command here
    # </run_command>
    #
    # Commands outside this format are ignored.

    pattern = r"<run_command>\s*(.*?)\s*</run_command>"

    matches = re.findall(
        pattern,
        answer,
        re.DOTALL,
    )

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

        # The command is never executed automatically.
        approval = input(
            "Execute this command? Type 'yes' to approve: "
        ).strip().lower()

        # Require the full word "yes".
        #
        # This is intentionally stricter than accepting "y".
        if approval != "yes":
            print("Command NOT executed.")

            # Save the rejection so the AI knows the command
            # was not executed.
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
            # Report command execution errors without crashing
            # the entire program.
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

    # Ask the user which model to use.
    choice = input("\nSelect model: ").strip()

    try:
        # Select the model using the user's numbered choice.
        model = models[int(choice) - 1]

    except (ValueError, IndexError):
        # Handle invalid model selections.
        print("Invalid selection.")
        sys.exit(1)

    # Show the selected model.
    print(f"\nUsing: {model}")

    # Conversation history sent to the model.
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful local AI assistant. "
                "Follow the user's instructions exactly. "

                "Answer normal questions normally. "

                "When files are provided, use their contents as context. "

                "When the user uses /write, you are allowed to create "
                "or modify files. "

                "IMPORTANT /write RULES: "

                "If the requested file does NOT exist, create it using "
                "exactly this format: "
                "<write_file path=\"filename.ext\">FILE CONTENT</write_file>. "

                "If the requested file ALREADY EXISTS, NEVER regenerate "
                "the entire file. Instead create a targeted edit using "
                "exactly this format: "
                "<edit_file path=\"filename.ext\">"
                "<find>EXACT EXISTING TEXT</find>"
                "<replace>NEW TEXT</replace>"
                "</edit_file>. "

                "The find section must contain text copied exactly from "
                "the existing file. "

                "Only include the smallest relevant section necessary "
                "for the requested change. "

                "Do not remove or rewrite unrelated existing code. "

                "Do not use markdown code fences inside write_file or "
                "edit_file blocks. "

                "Never use write_file for an existing file. "

                "When the user uses /run, generate terminal commands "
                "using ONLY the required <run_command> format. "

                "Never put executable commands outside a "
                "<run_command> block. "

                "Never assume a command has been approved. "
                "The terminal program will ask the user for approval "
                "before executing every command."
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

            # Display all available commands.
            print()
            print("Available commands:")
            print("  /help        Show available commands")
            print("  /files       List files in current directory")
            print("  /read FILE   Add a file to context")
            print("  /read-ls     List files currently added to context")
            print("  /write DESC  Create or modify a file using AI")
            print("  /run DESC    Generate and run a command using AI")
            print("  /tokens      Show token count")
            print("  /clear       Clear conversation")
            print("  /exit        Exit")
            print()

            continue

        if user_input == "/tokens":

            # Show a message if no model request has been completed yet.
            if last_prompt_tokens is None:
                print("No token count available yet.")

            else:
                # Display the token counts reported by LM Studio.
                print(
                    f"Prompt tokens:     {last_prompt_tokens:,}"
                )
                print(
                    f"Completion tokens: {last_completion_tokens:,}"
                )
                print(
                    f"Total tokens:      {last_total_tokens:,}"
                )

            continue

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

        if user_input == "/files":

            # Walk through the current directory recursively.
            for root, dirs, files in os.walk("."):

                # Ignore hidden directories.
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                ]

                # Display every visible file.
                for file in files:
                    path = os.path.join(root, file)
                    print(path)

            continue

        if user_input == "/read-ls":

            # Tell the user if no files have been added.
            if not read_files_list:
                print(
                    "No files have been added to the conversation."
                )

            else:
                # Display every file currently in the conversation.
                print("Files currently added:")

                for path in read_files_list:
                    print(f"  {path}")

            continue

        if user_input.startswith("/read "):

            # Everything after "/read " is treated as the file pattern.
            pattern = user_input[6:].strip()

            # Read the matching files.
            content, added_files = read_files(pattern)

            # Only add files to the conversation if content was found.
            if content:

                # Add the file contents as a user message.
                messages.append({
                    "role": "user",
                    "content": (
                        "Here are the files I want you to read:\n\n"
                        f"{content}"
                    ),
                })

                # Remember which files were added.
                read_files_list.extend(added_files)

                print(
                    f"Added files matching: {pattern}"
                )

            continue

        if user_input.startswith("/write "):

            # Everything after "/write " is treated as the file request.
            request = user_input[7:].strip()

            if not request:
                print("Usage: /write DESCRIPTION")
                continue

            # Determine whether the user explicitly named an existing
            # file in the request.
            #
            # Relevant existing files are provided to the AI so it can
            # make a targeted edit instead of regenerating the whole file.
            existing_files = []

            # Check simple paths mentioned in the request.
            words = request.split()

            for word in words:

                # Remove common punctuation around filenames.
                cleaned = word.strip(
                    "\"'`.,:;()[]{}"
                )

                # Add the path if it refers to an existing file.
                if os.path.isfile(cleaned):
                    existing_files.append(cleaned)

            # Build the file context that will be sent to the AI.
            file_context = ""

            # Read every explicitly referenced existing file.
            for path in existing_files:

                content = get_file_content(path)

                if content is not None:

                    file_context += (
                        f"\n===== EXISTING FILE: {path} =====\n"
                        f"{content}\n"
                        f"===== END EXISTING FILE =====\n"
                    )

            # Tell the AI whether it needs to create a new file
            # or make a targeted edit to an existing file.
            messages.append({
                "role": "user",
                "content": (
                    "The user wants you to create or modify a file.\n\n"
                    f"User request:\n{request}\n\n"

                    + (
                        "The following file already exists. "
                        "Modify ONLY the necessary section. "
                        "Do NOT regenerate the whole file:\n"
                        f"{file_context}\n"
                        if file_context
                        else
                        "No existing file was found from the request. "
                        "If a new file is needed, create it with "
                        "<write_file>.\n"
                    )

                    +

                    "For an existing file, output ONLY a targeted "
                    "<edit_file> block using this exact structure:\n\n"

                    '<edit_file path="filename.ext">\n'
                    "<find>\n"
                    "EXACT EXISTING TEXT\n"
                    "</find>\n"
                    "<replace>\n"
                    "NEW TEXT\n"
                    "</replace>\n"
                    "</edit_file>\n\n"

                    "The text inside <find> MUST match the existing "
                    "file exactly. "

                    "Only include the smallest section necessary "
                    "for the requested change. "

                    "Do not modify unrelated code. "

                    "If the file does not exist, use:\n\n"

                    '<write_file path="filename.ext">\n'
                    "COMPLETE FILE CONTENT\n"
                    "</write_file>\n\n"

                    "Do not use markdown code fences."
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

            # Anything that isn't a recognized command is treated as
            # a normal message for the AI.
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
                stream_options={
                    "include_usage": True
                },
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
                    last_prompt_tokens = (
                        chunk.usage.prompt_tokens
                    )

                    last_completion_tokens = (
                        chunk.usage.completion_tokens
                    )

                    last_total_tokens = (
                        chunk.usage.total_tokens
                    )

                # Some streaming chunks contain usage information only
                # and therefore don't contain any choices.
                if not chunk.choices:
                    continue

                # Get the newly generated text from this chunk.
                text = chunk.choices[0].delta.content

                # Print the text immediately and save it for the
                # conversation history.
                if text:
                    print(
                        text,
                        end="",
                        flush=True
                    )

                    answer += text

            # Move to a new line after the streamed response.
            print()

            # If this was a /write request, process targeted edits
            # and new file creation requests.
            if user_input.startswith("/write "):

                # First process targeted edits to existing files.
                apply_ai_edits(answer)

                # Then process requests for brand-new files.
                write_ai_files(answer)

            # If this was a /run request, process requested commands.
            command_result = None

            if user_input.startswith("/run "):

                # Ask for approval before executing every command.
                command_result = run_ai_command(answer)

            # Add the completed AI response to the conversation history.
            messages.append({
                "role": "assistant",
                "content": answer,
            })

            # If a command was executed or rejected, give the result
            # back to the AI so it knows what happened.
            if command_result:

                messages.append({
                    "role": "user",
                    "content": command_result,
                })

        except Exception as e:

            # Display API or connection errors without crashing
            # the entire program.
            print(f"\nError: {e}")


# Only run main() when this file is executed directly.
#
# This prevents main() from automatically running if this file is
# imported by another Python program.
if __name__ == "__main__":
    main()