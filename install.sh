#!/usr/bin/env bash

set -e

echo "========================================"
echo " Local AI Installer"
echo "========================================"
echo

# --------------------------------------------------
# Determine the repository location dynamically
# --------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "Installation directory:"
echo "  $SCRIPT_DIR"
echo

# --------------------------------------------------
# Check Python
# --------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

echo "Python found:"
python3 --version
echo

# --------------------------------------------------
# Check that dbai.py exists
# --------------------------------------------------

if [ ! -f "$SCRIPT_DIR/dbai.py" ]; then
    echo "Error: dbai.py was not found in:"
    echo "  $SCRIPT_DIR"
    exit 1
fi

# --------------------------------------------------
# Check that requirements.txt exists
# --------------------------------------------------

if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Error: requirements.txt was not found in:"
    echo "  $SCRIPT_DIR"
    exit 1
fi

# --------------------------------------------------
# Create virtual environment
# --------------------------------------------------

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists."
fi

echo

# --------------------------------------------------
# Install dependencies
# --------------------------------------------------

echo "Installing dependencies..."

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt"

echo

# --------------------------------------------------
# Make dbai.py executable
# --------------------------------------------------

chmod +x "$SCRIPT_DIR/dbai.py"

# --------------------------------------------------
# Create ~/.local/bin
# --------------------------------------------------

LOCAL_BIN="$HOME/.local/bin"

mkdir -p "$LOCAL_BIN"

# --------------------------------------------------
# Remove ANY previous dbai installation
#
# This handles:
#   - old symlinks
#   - old executable launchers
#   - old shell wrapper scripts
#   - broken symlinks
# --------------------------------------------------

DBAI_COMMAND="$LOCAL_BIN/dbai"

if [ -e "$DBAI_COMMAND" ] || [ -L "$DBAI_COMMAND" ]; then
    echo "Removing existing dbai command..."
    rm -f "$DBAI_COMMAND"
fi

# --------------------------------------------------
# Create a clean launcher
#
# IMPORTANT:
# The repository's dbai.py is NOT modified.
#
# This launcher directly executes the Python interpreter
# inside the repository's virtual environment.
# --------------------------------------------------

cat > "$DBAI_COMMAND" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/dbai.py" "\$@"
EOF

chmod +x "$DBAI_COMMAND"

echo "Created:"
echo "  $DBAI_COMMAND"
echo

# --------------------------------------------------
# Add ~/.local/bin to PATH
#
# We don't assume a particular shell.
# We update common shell startup files only if needed.
# --------------------------------------------------

PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

add_to_path_file() {
    local file="$1"

    if [ ! -f "$file" ]; then
        touch "$file"
    fi

    if ! grep -Fqx "$PATH_LINE" "$file"; then
        echo "$PATH_LINE" >> "$file"
        echo "Added ~/.local/bin to $file"
    fi
}

# Bash
if [ -n "${BASH_VERSION:-}" ]; then
    add_to_path_file "$HOME/.bashrc"
fi

# Zsh
if [ -n "${ZSH_VERSION:-}" ]; then
    add_to_path_file "$HOME/.zshrc"
fi

# Profile for login shells
add_to_path_file "$HOME/.profile"

# --------------------------------------------------
# Make the command available immediately
# in the current installer shell
# --------------------------------------------------

export PATH="$LOCAL_BIN:$PATH"

# --------------------------------------------------
# Verify installation
# --------------------------------------------------

echo
echo "Verifying installation..."

if [ ! -x "$DBAI_COMMAND" ]; then
    echo "Error: dbai command was not created correctly."
    exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Error: virtual environment Python was not found."
    exit 1
fi

# Test that Python can import OpenAI
if ! "$VENV_DIR/bin/python" -c "import openai" >/dev/null 2>&1; then
    echo "Error: OpenAI Python package could not be imported."
    exit 1
fi

echo "Installation verified successfully."
echo

# --------------------------------------------------
# Done
# --------------------------------------------------

echo "========================================"
echo " Installation complete!"
echo "========================================"
echo
echo "Repository:"
echo "  $SCRIPT_DIR"
echo
echo "Virtual environment:"
echo "  $VENV_DIR"
echo
echo "Command:"
echo "  $DBAI_COMMAND"
echo
echo "You can run:"
echo "  dbai"
echo
echo "Make sure LM Studio is running with its"
echo "local server enabled before starting dbai."
echo