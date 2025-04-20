#!/bin/bash

# TGAI-Bennet Installation Script
# Sets up the TGAI-Bennet service on a Linux system (optimized for Raspberry Pi)

set -e  # Exit on any error

# Text formatting
BOLD="\e[1m"
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
RESET="\e[0m"

# Installation directory (get the directory where this script is located)
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"
SERVICE_NAME="tgai-bennet"
SERVICE_FILE="${INSTALL_DIR}/systemd/${SERVICE_NAME}.service"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Log messages
info() {
    echo -e "${BLUE}${BOLD}[INFO]${RESET} $1"
}

success() {
    echo -e "${GREEN}${BOLD}[SUCCESS]${RESET} $1"
}

warning() {
    echo -e "${YELLOW}${BOLD}[WARNING]${RESET} $1"
}

error() {
    echo -e "${RED}${BOLD}[ERROR]${RESET} $1"
    exit 1
}

# Check if running as root for systemd service installation
check_root() {
    if [[ $EUID -ne 0 ]]; then
        warning "This script is not running as root."
        warning "Service installation will require sudo privileges."
        echo ""
        read -p "Do you want to continue? (y/n): " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            error "Installation aborted by user."
        fi
    fi
}

# Check system requirements
check_requirements() {
    info "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Please install Python 3.7 or newer."
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    
    if [[ "$PYTHON_MAJOR" -lt 3 || ("$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 7) ]]; then
        error "Python 3.7 or newer is required. Found: Python $PYTHON_VERSION"
    fi
    
    info "Found Python $PYTHON_VERSION"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        warning "pip3 not found. Attempting to install..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3-pip
        else
            error "pip3 is not installed and couldn't be installed automatically."
        fi
    fi
    
    # Check systemd
    if ! command -v systemctl &> /dev/null; then
        warning "systemd not found. Service installation will be skipped."
        USE_SYSTEMD=false
    else
        USE_SYSTEMD=true
    fi
    
    # Check for virtual environment support
    if ! python3 -c "import venv" &> /dev/null; then
        warning "Python venv module not found. Attempting to install..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3-venv
        else
            error "Python venv module is not available and couldn't be installed automatically."
        fi
    fi
    
    success "All system requirements are met."
}

# Create and configure virtual environment
setup_virtualenv() {
    info "Setting up Python virtual environment..."
    
    # Check if virtual environment exists and ask if user wants to delete it
    if [[ -d "$VENV_DIR" ]]; then
        warning "Virtual environment already exists at $VENV_DIR"
        read -p "Do you want to delete the existing virtual environment and create a new one? (y/n): " DELETE_VENV
        if [[ "$DELETE_VENV" =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
            info "Deleted existing virtual environment"
            python3 -m venv "$VENV_DIR"
            success "Created new virtual environment at $VENV_DIR"
        else
            info "Using existing virtual environment"
        fi
    else
        python3 -m venv "$VENV_DIR"
        success "Created virtual environment at $VENV_DIR"
    fi
    
    # Activate virtual environment
    source "${VENV_DIR}/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Check if Rust and Cargo are installed (needed for pydantic)
    info "Checking for Rust and Cargo installation..."
    if ! command -v cargo &> /dev/null || ! command -v rustc &> /dev/null; then
        warning "Rust and/or Cargo not found. Installing Rust toolchain..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
        success "Rust toolchain installed successfully"
    else
        RUST_VERSION=$(rustc --version | cut -d' ' -f2)
        CARGO_VERSION=$(cargo --version | cut -d' ' -f2)
        info "Found Rust $RUST_VERSION and Cargo $CARGO_VERSION"
    fi
    
    # Install requirements
    info "Installing dependencies..."
    pip install -r "${INSTALL_DIR}/requirements.txt"
    
    success "Virtual environment is ready."
}

# Configure the application
configure_app() {
    info "Configuring TGAI-Bennet..."
    
    # Check if .env exists, create from sample if not
    if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
        if [[ -f "${INSTALL_DIR}/.env.sample" ]]; then
            cp "${INSTALL_DIR}/.env.sample" "${INSTALL_DIR}/.env"
            warning "Created .env file from sample. Please edit it with your actual settings."
            warning "You'll need to set Telegram and API keys before running the service."
            echo ""
            # Ask if the user wants to edit the file now
            read -p "Would you like to edit the .env file now? (y/n): " EDIT_ENV
            if [[ "$EDIT_ENV" =~ ^[Yy]$ ]]; then
                if command -v nano &> /dev/null; then
                    nano "${INSTALL_DIR}/.env"
                elif command -v vi &> /dev/null; then
                    vi "${INSTALL_DIR}/.env"
                else
                    warning "No editor found. Please edit the .env file manually."
                fi
            fi
        else
            error ".env.sample not found. Cannot configure the application."
        fi
    else
        info ".env file already exists."
    fi
    
    # Create necessary directories
    mkdir -p "${INSTALL_DIR}/logs"
    mkdir -p "${INSTALL_DIR}/data"
    
    success "Configuration complete."
}

# Install systemd service
install_service() {
    if [[ "$USE_SYSTEMD" != "true" ]]; then
        warning "Skipping service installation (systemd not found)."
        return
    fi
    
    info "Installing systemd service..."
    
    # Check if service file exists
    if [[ ! -f "$SERVICE_FILE" ]]; then
        error "Service file not found: $SERVICE_FILE"
    fi
    
    # Get the current user
    CURRENT_USER=$(whoami)
    
    # Create a temporary service file with correct paths
    TMP_SERVICE_FILE="/tmp/${SERVICE_NAME}.service"
    cat "$SERVICE_FILE" > "$TMP_SERVICE_FILE"
    
    # Update paths in the service file
    sed -i "s|%INSTALL_DIR%|${INSTALL_DIR}|g" "$TMP_SERVICE_FILE"
    sed -i "s|%VENV_DIR%|${VENV_DIR}|g" "$TMP_SERVICE_FILE"
    sed -i "s|%USER%|${CURRENT_USER}|g" "$TMP_SERVICE_FILE"
    
    # Copy service file to systemd directory
    sudo cp "$TMP_SERVICE_FILE" "$SYSTEM_SERVICE_FILE"
    sudo chmod 644 "$SYSTEM_SERVICE_FILE"
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable the service
    sudo systemctl enable "$SERVICE_NAME"
    
    success "Service installed successfully."
    info "You can start the service with: sudo systemctl start $SERVICE_NAME"
    info "You can check the service status with: sudo systemctl status $SERVICE_NAME"
    info "Service logs can be viewed with: sudo journalctl -u $SERVICE_NAME"
}

# Display final instructions
show_instructions() {
    echo ""
    echo -e "${BOLD}TGAI-Bennet Installation Complete${RESET}"
    echo ""
    echo "Next steps:"
    echo "  1. Edit the .env file with your API keys if you haven't already"
    echo "  2. Configure any module settings in conf.yml"
    
    if [[ "$USE_SYSTEMD" == "true" ]]; then
        echo "  3. Start the service: sudo systemctl start $SERVICE_NAME"
    else
        echo "  3. Start the application manually: cd $INSTALL_DIR && venv/bin/python -m src.main"
    fi
    
    echo ""
    echo "For more information, refer to the README.md file."
    echo ""
}

# Main installation process
main() {
    info "Starting TGAI-Bennet installation..."
    echo ""
    
    check_root
    check_requirements
    setup_virtualenv
    configure_app
    install_service
    
    success "TGAI-Bennet installation is complete!"
    show_instructions
}

# Start the installation
main
