# SigmaOS Quickshell Component (`SigmaOS-quickshell`)

Reactive QML status bar, notification daemon, application launcher, and ambient desktop widgets for SigmaOS and Omarchy Linux, backed by Wayland layer-shell protocol.

---

## Architecture & Subsystems

This repository provides the core desktop shell environment for SigmaOS:

1. **Status Bar (`qml/shell.qml`)**:
   - Hyprland workspace indicator bindings
   - AI token usage & model breakdown card (dispatches to `sigmaos-agent-usage`)
   - System telemetry (CPU, RAM, thermals)
   - Clock, audio volume, and network status
   - Session controller (wlogout / power menu)

2. **Toast Notifications (`qml/notifications.qml`)**:
   - Hardware-accelerated Wayland notification server
   - Critical alerts and agent diagnostic notifications
   - Auto-dismiss and interactive action buttons

3. **Application Launcher (`qml/launcher.qml`)**:
   - Fullscreen animated application grid
   - Real-time fuzzy filtering of desktop entries
   - Category navigation (Development, Gaming, Media, System)

4. **Desktop Widgets (`qml/widgets.qml`)**:
   - Ambient desktop canvas widgets on Wayland bottom background layer
   - Live telemetry gauges for CPU, Memory, and Swap
   - Active AI agent status and quick-launch buttons

5. **Shell Lifecycle Orchestrator (`bin/sigmaos-quickshell`)**:
   - High-reliability daemon supervisor with graceful Waybar fallback
   - Commands: `start`, `stop`, `reload`, `status`, `toggle`

---

## Build & Test

```bash
# Run unit & integration tests
cargo test

# Validate all QML component files
cargo run -- check

# Start the desktop shell
cargo run -- start
# or
./bin/sigmaos-quickshell start
```
