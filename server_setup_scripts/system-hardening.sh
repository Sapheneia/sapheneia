#!/bin/bash
# =============================================================================
# System Hardening Script for NVIDIA DIGITS / DGX Spark Servers
# =============================================================================
# User-friendly security hardening with multiple modes.
#
# Usage:
#   sudo ./system-hardening.sh              # Interactive menu
#   sudo ./system-hardening.sh --check      # Just show security status
#   sudo ./system-hardening.sh --quick      # Apply recommended settings
#   sudo ./system-hardening.sh --undo       # Undo hardening changes
#
# For non-technical users: Use --check first to see status, then --quick
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

# Mode flags
MODE="interactive"
NOTIFICATION_EMAIL=""

# =============================================================================
# Parse Arguments
# =============================================================================

show_help() {
    cat << EOF
System Hardening Script for DIGITS/DGX Spark

Usage: sudo ./system-hardening.sh [OPTIONS]

Options:
  --check       Show current security status (no changes made)
  --quick       Apply recommended settings automatically
  --undo        Undo/remove hardening configurations
  --notify EMAIL  Set up login notifications to this email
  --help        Show this help message

Examples:
  sudo ./system-hardening.sh --check          # See what needs fixing
  sudo ./system-hardening.sh --quick          # Apply safe defaults
  sudo ./system-hardening.sh --notify you@email.com  # Get login alerts

EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --check) MODE="check"; shift ;;
        --quick) MODE="quick"; shift ;;
        --undo) MODE="undo"; shift ;;
        --notify) NOTIFICATION_EMAIL="$2"; shift 2 ;;
        --help|-h) show_help ;;
        *) echo "Unknown option: $1"; show_help ;;
    esac
done

# =============================================================================
# Pre-flight Checks
# =============================================================================

if [[ $EUID -ne 0 ]] && [[ "$MODE" != "check" ]]; then
    echo -e "${RED}This script must be run as root (use sudo)${NC}"
    echo "For checking status only, you can run without sudo."
    exit 1
fi

ACTUAL_USER="${SUDO_USER:-$USER}"

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
  ╔═══════════════════════════════════════════╗
  ║     SYSTEM SECURITY HARDENING             ║
  ║     for NVIDIA DIGITS / DGX Spark         ║
  ╚═══════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

print_section() {
    echo ""
    echo -e "${CYAN}─────────────────────────────────────────────${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}─────────────────────────────────────────────${NC}"
}

ok() { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${GRAY}$1${NC}"; }

check_installed() {
    dpkg -l "$1" &>/dev/null
}

check_service() {
    systemctl is-active --quiet "$1" 2>/dev/null
}

ask() {
    local prompt=$1
    read -p "$prompt [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

backup_file() {
    local file=$1
    if [[ -f "$file" ]] && [[ ! -f "${file}.hardening-backup" ]]; then
        cp "$file" "${file}.hardening-backup"
    fi
}

restore_file() {
    local file=$1
    if [[ -f "${file}.hardening-backup" ]]; then
        mv "${file}.hardening-backup" "$file"
        return 0
    fi
    return 1
}

# =============================================================================
# Security Status Check (--check mode)
# =============================================================================

check_security_status() {
    print_banner
    echo -e "${BOLD}Security Status Report${NC}"
    echo -e "${GRAY}Generated: $(date)${NC}"
    echo -e "${GRAY}Hostname: $(hostname)${NC}"
    echo ""

    local score=0
    local max_score=10

    # 1. System Updates
    print_section "System Updates"
    local updates=$(apt list --upgradable 2>/dev/null | grep -c upgradable || echo "0")
    if [[ "$updates" -eq 0 ]]; then
        ok "System is up to date"
        ((score++))
    else
        warn "$updates packages can be updated"
        info "Run: sudo apt update && sudo apt upgrade"
    fi

    # 2. Automatic Updates
    print_section "Automatic Security Updates"
    if check_installed unattended-upgrades && [[ -f /etc/apt/apt.conf.d/50unattended-upgrades ]]; then
        ok "Automatic security updates enabled"
        ((score++))
    else
        warn "Automatic updates not configured"
        info "Recommended: Keeps server patched automatically"
    fi

    # 3. Firewall
    print_section "Firewall (UFW)"
    if check_service ufw; then
        ok "Firewall is active"
        ((score++))
        ufw status | grep -E "^[0-9]" | head -5 | while read line; do
            info "  $line"
        done
    else
        fail "Firewall is NOT active"
        info "Your server is exposed to the internet!"
    fi

    # 4. SSH Security
    print_section "SSH Security"
    local ssh_issues=0

    if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null; then
        ok "Root login disabled"
    else
        warn "Root login may be enabled"
        ((ssh_issues++))
    fi

    if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null; then
        ok "Password authentication disabled (key-only)"
    else
        warn "Password authentication enabled (less secure)"
        ((ssh_issues++))
    fi

    [[ $ssh_issues -eq 0 ]] && ((score++))

    # 5. Fail2ban
    print_section "Brute Force Protection (Fail2ban)"
    if check_service fail2ban; then
        ok "Fail2ban is active"
        ((score++))
        local banned=$(fail2ban-client status sshd 2>/dev/null | grep "Currently banned" | awk '{print $NF}')
        [[ -n "$banned" ]] && info "Currently banned IPs: $banned"
    else
        warn "Fail2ban not running"
        info "Your server is vulnerable to brute force attacks"
    fi

    # 6. Login Notifications
    print_section "Login Notifications"
    if [[ -f /etc/profile.d/login-notify.sh ]]; then
        ok "Login notifications enabled"
        ((score++))
    else
        info "Not configured (optional)"
        info "Get notified when someone logs into your server"
    fi

    # 7. Container Security
    print_section "Container Security (Podman)"
    if check_installed podman; then
        ok "Podman installed"
        if id -nG "$ACTUAL_USER" | grep -qw "podman\|docker"; then
            ok "User in container group"
        fi
        local running=$(podman ps -q 2>/dev/null | wc -l)
        info "$running containers running"
    else
        info "Podman not installed"
    fi

    # 8. Kernel Hardening
    print_section "Kernel Security"
    if [[ -f /etc/sysctl.d/99-hardening.conf ]]; then
        ok "Kernel hardening applied"
        ((score++))
    else
        info "Default kernel settings"
    fi

    # 9. Audit Logging
    print_section "Security Logging"
    if check_service auditd; then
        ok "Audit logging enabled"
        ((score++))
    else
        info "Basic logging only"
    fi

    # 10. NVIDIA/GPU
    print_section "GPU Security"
    if command -v nvidia-smi &>/dev/null; then
        ok "NVIDIA drivers installed"
        ((score++))
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | while read line; do
            info "  $line"
        done
    fi

    # Score Summary
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo ""

    local percent=$((score * 100 / max_score))
    local grade

    if [[ $percent -ge 80 ]]; then
        grade="${GREEN}GOOD${NC}"
    elif [[ $percent -ge 50 ]]; then
        grade="${YELLOW}FAIR${NC}"
    else
        grade="${RED}NEEDS WORK${NC}"
    fi

    echo -e "  Security Score: ${BOLD}$score / $max_score${NC} ($percent%)"
    echo -e "  Grade: $grade"
    echo ""

    if [[ $score -lt $max_score ]]; then
        echo -e "  ${CYAN}To improve your security, run:${NC}"
        echo -e "  ${BOLD}sudo ./system-hardening.sh --quick${NC}"
        echo ""
    fi
}

# =============================================================================
# Quick Mode (--quick) - Apply Recommended Settings
# =============================================================================

quick_harden() {
    print_banner
    echo -e "${BOLD}Quick Hardening Mode${NC}"
    echo ""
    echo "This will apply recommended security settings:"
    echo "  • Update system packages"
    echo "  • Enable automatic security updates"
    echo "  • Configure firewall (UFW)"
    echo "  • Install brute-force protection (Fail2ban)"
    echo "  • Apply kernel hardening"
    echo ""
    echo -e "${YELLOW}Note: SSH hardening is skipped in quick mode for safety.${NC}"
    echo -e "${YELLOW}Run interactively to enable SSH hardening.${NC}"
    echo ""

    if ! ask "Continue with quick hardening?"; then
        echo "Cancelled."
        exit 0
    fi

    echo ""

    # 1. System Updates
    echo -e "${BLUE}[1/5] Updating system...${NC}"
    apt update -qq
    apt upgrade -y -qq
    ok "System updated"

    # 2. Automatic Updates
    echo -e "${BLUE}[2/5] Enabling automatic security updates...${NC}"
    apt install -y -qq unattended-upgrades apt-listchanges

    cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Package-Blacklist {
    "nvidia-";
    "cuda-";
};
Unattended-Upgrade::Automatic-Reboot "false";
EOF

    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

    systemctl enable unattended-upgrades --quiet
    ok "Automatic updates enabled"

    # 3. Firewall
    echo -e "${BLUE}[3/5] Configuring firewall...${NC}"
    apt install -y -qq ufw
    ufw --force reset >/dev/null
    ufw default deny incoming >/dev/null
    ufw default allow outgoing >/dev/null
    ufw allow 22/tcp >/dev/null      # SSH
    ufw allow 12130/tcp >/dev/null   # InfluxDB
    ufw allow 12210/tcp >/dev/null   # Sapheneia
    ufw allow 12700/tcp >/dev/null   # Aleutian
    ufw allow 12710/tcp >/dev/null   # Chronos
    ufw --force enable >/dev/null
    ok "Firewall enabled (SSH + Sapheneia ports open)"

    # 4. Fail2ban
    echo -e "${BLUE}[4/5] Installing brute-force protection...${NC}"
    apt install -y -qq fail2ban

    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
banaction = ufw

[sshd]
enabled = true
maxretry = 3
EOF

    systemctl enable fail2ban --quiet
    systemctl restart fail2ban --quiet
    ok "Fail2ban installed"

    # 5. Kernel Hardening
    echo -e "${BLUE}[5/5] Applying kernel hardening...${NC}"

    cat > /etc/sysctl.d/99-hardening.conf << 'EOF'
net.ipv4.conf.all.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.tcp_syncookies = 1
kernel.randomize_va_space = 2
EOF

    sysctl --system >/dev/null 2>&1
    ok "Kernel hardening applied"

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Quick hardening complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "Run ${BOLD}./system-hardening.sh --check${NC} to verify."
    echo ""
}

# =============================================================================
# Undo Mode (--undo)
# =============================================================================

undo_hardening() {
    print_banner
    echo -e "${BOLD}Undo Hardening${NC}"
    echo ""
    echo "This will remove hardening configurations."
    echo ""

    if ! ask "Continue?"; then
        echo "Cancelled."
        exit 0
    fi

    # Disable UFW
    if check_service ufw; then
        echo "Disabling firewall..."
        ufw --force disable >/dev/null
        ok "Firewall disabled"
    fi

    # Remove hardening configs
    rm -f /etc/ssh/sshd_config.d/hardening.conf 2>/dev/null && ok "SSH hardening removed"
    rm -f /etc/sysctl.d/99-hardening.conf 2>/dev/null && ok "Kernel hardening removed"
    rm -f /etc/profile.d/login-notify.sh 2>/dev/null && ok "Login notifications removed"

    # Restore backups
    for file in /etc/ssh/sshd_config /etc/sysctl.conf; do
        if restore_file "$file"; then
            ok "Restored $file from backup"
        fi
    done

    # Restart SSH if config changed
    if [[ -f /etc/ssh/sshd_config ]]; then
        systemctl restart sshd 2>/dev/null || true
    fi

    sysctl --system >/dev/null 2>&1

    echo ""
    ok "Hardening configurations removed"
    echo ""
    echo "Note: Packages (fail2ban, ufw, etc.) were not uninstalled."
    echo "Run 'sudo apt remove fail2ban ufw' to remove them."
    echo ""
}

# =============================================================================
# Login Notifications
# =============================================================================

setup_login_notifications() {
    print_section "Login Notifications"

    echo "Get notified when someone logs into your server."
    echo ""
    echo "Options:"
    echo "  1. Slack webhook"
    echo "  2. Discord webhook"
    echo "  3. Email (requires mail server)"
    echo "  4. Skip"
    echo ""

    read -p "Choose [1-4]: " choice

    case $choice in
        1)
            read -p "Paste your Slack webhook URL: " webhook
            if [[ -z "$webhook" ]]; then
                warn "No webhook provided, skipping"
                return
            fi

            cat > /etc/profile.d/login-notify.sh << EOF
#!/bin/bash
# Login notification to Slack
if [[ -n "\$SSH_CONNECTION" ]]; then
    curl -s -X POST -H 'Content-type: application/json' \\
        --data "{\"text\":\"🔐 SSH Login: \$USER@\$(hostname) from \$(echo \$SSH_CONNECTION | awk '{print \$1}') at \$(date)\"}" \\
        "$webhook" >/dev/null 2>&1 &
fi
EOF
            chmod +x /etc/profile.d/login-notify.sh
            ok "Slack notifications enabled"
            ;;

        2)
            read -p "Paste your Discord webhook URL: " webhook
            if [[ -z "$webhook" ]]; then
                warn "No webhook provided, skipping"
                return
            fi

            cat > /etc/profile.d/login-notify.sh << EOF
#!/bin/bash
# Login notification to Discord
if [[ -n "\$SSH_CONNECTION" ]]; then
    curl -s -X POST -H 'Content-type: application/json' \\
        --data "{\"content\":\"🔐 SSH Login: \$USER@\$(hostname) from \$(echo \$SSH_CONNECTION | awk '{print \$1}') at \$(date)\"}" \\
        "$webhook" >/dev/null 2>&1 &
fi
EOF
            chmod +x /etc/profile.d/login-notify.sh
            ok "Discord notifications enabled"
            ;;

        3)
            read -p "Email address: " email
            if [[ -z "$email" ]]; then
                warn "No email provided, skipping"
                return
            fi

            apt install -y -qq mailutils 2>/dev/null || apt install -y -qq bsd-mailx

            cat > /etc/profile.d/login-notify.sh << EOF
#!/bin/bash
# Login notification via email
if [[ -n "\$SSH_CONNECTION" ]]; then
    echo "SSH Login: \$USER@\$(hostname) from \$(echo \$SSH_CONNECTION | awk '{print \$1}') at \$(date)" | \\
        mail -s "SSH Login Alert: \$(hostname)" "$email" 2>/dev/null &
fi
EOF
            chmod +x /etc/profile.d/login-notify.sh
            ok "Email notifications enabled"
            warn "Note: Requires working mail server (sendmail/postfix)"
            ;;

        *)
            info "Skipped"
            ;;
    esac
}

# =============================================================================
# SSH Hardening (Interactive only)
# =============================================================================

do_ssh_hardening() {
    print_section "SSH Hardening"

    echo -e "${RED}${BOLD}⚠️  READ CAREFULLY:${NC}"
    echo ""
    echo "This will disable password login - you'll need SSH keys."
    echo ""
    echo "Before continuing:"
    echo "  1. Open a NEW terminal window"
    echo "  2. SSH to this server"
    echo "  3. Keep that session open as backup"
    echo ""

    if ! ask "Do you have SSH key access working?"; then
        echo ""
        echo "Set up SSH keys first:"
        echo "  1. On your computer: ssh-keygen -t ed25519"
        echo "  2. Copy to server: ssh-copy-id $ACTUAL_USER@$(hostname -I | awk '{print $1}')"
        echo "  3. Test it works, then run this again"
        return
    fi

    if ! ask "Apply SSH hardening now?"; then
        return
    fi

    backup_file /etc/ssh/sshd_config

    cat > /etc/ssh/sshd_config.d/hardening.conf << 'EOF'
# SSH Hardening
PermitRootLogin no
PasswordAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
EOF

    if sshd -t; then
        systemctl restart sshd
        ok "SSH hardened"
        echo ""
        echo -e "${YELLOW}TEST NOW: Open a new terminal and verify SSH still works!${NC}"
    else
        fail "SSH config error - reverting"
        rm /etc/ssh/sshd_config.d/hardening.conf
    fi
}

# =============================================================================
# Interactive Menu
# =============================================================================

interactive_menu() {
    print_banner

    echo "What would you like to do?"
    echo ""
    echo "  1. Check security status (recommended first)"
    echo "  2. Quick harden (apply recommended settings)"
    echo "  3. Full interactive setup"
    echo "  4. Set up login notifications"
    echo "  5. Harden SSH (advanced)"
    echo "  6. Undo all hardening"
    echo "  7. Exit"
    echo ""

    read -p "Choose [1-7]: " choice

    case $choice in
        1) check_security_status ;;
        2) quick_harden ;;
        3)
            quick_harden
            echo ""
            if ask "Also set up login notifications?"; then
                setup_login_notifications
            fi
            if ask "Also harden SSH? (advanced)"; then
                do_ssh_hardening
            fi
            ;;
        4) setup_login_notifications ;;
        5) do_ssh_hardening ;;
        6) undo_hardening ;;
        7) echo "Bye!"; exit 0 ;;
        *) echo "Invalid choice"; exit 1 ;;
    esac
}

# =============================================================================
# Main
# =============================================================================

main() {
    case $MODE in
        check)
            check_security_status
            ;;
        quick)
            quick_harden
            ;;
        undo)
            undo_hardening
            ;;
        interactive)
            interactive_menu
            ;;
    esac
}

main "$@"
