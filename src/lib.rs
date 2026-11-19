// SPDX-License-Identifier: Apache-2.0
//! SigmaOS-quickshell — SigmaOS quickshell component inspired by Linux Mint / Omarchy / Arch Linux.
//!
//! Omarchy/Hyprland-style shell config: monitors, keybinds, exec-once; fail-fast validation, deterministic render.
//! Principles: single responsibility, fail-fast, defensive programming,
//! component isolation, stable API, deterministic tests.

#![forbid(unsafe_code)]

use std::fmt;
use std::collections::BTreeMap;

/// Errors for `DesktopError` operations. Fail-fast: invalid input is rejected.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DesktopError {
    /// Monitor spec must be `NAME,WxH@R,x,y,scale`
    BadMonitor(String),
    /// Keybind requires non-empty mods, key, dispatcher, and arg
    BadBind(String),
    /// Identical keybind already configured
    DuplicateBind(String),
    /// exec-once command must not be empty
    EmptyExec,
    /// General key must not be empty
    EmptyGeneral,
}

impl fmt::Display for DesktopError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::BadMonitor(x) => write!(f, "monitor spec must be `name,wxh@r,x,y,scale`: {x}"),
            Self::BadBind(x) => write!(f, "keybind requires non-empty mods, key, dispatcher, and arg: {x}"),
            Self::DuplicateBind(x) => write!(f, "identical keybind already configured: {x}"),
            Self::EmptyExec => write!(f, "exec-once command must not be empty"),
            Self::EmptyGeneral => write!(f, "general key must not be empty"),
        }
    }
}

impl std::error::Error for DesktopError {}

/// A Hyprland/Omarchy-style keybind: `mods, key, dispatcher, arg`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Keybind {
    /// Modifier string, e.g. `SUPER`, `SUPER SHIFT`, `ALT`.
    pub mods: String,
    /// Key name, e.g. `Return`, `Q`, `space`.
    pub key: String,
    /// Dispatcher, e.g. `exec`, `killactive`, `workspace`.
    pub dispatcher: String,
    /// Dispatcher argument.
    pub arg: String,
}

/// Desktop shell configuration (Hyprland/waybar/Omarchy inspired).
#[derive(Debug, Default)]
pub struct DesktopConfig {
    general: BTreeMap<String, String>,
    monitors: Vec<String>,
    binds: Vec<Keybind>,
    exec_once: Vec<String>,
}

impl DesktopConfig {
    /// Empty configuration.
    pub fn new() -> Self { Self::default() }

    /// Set a `[general]`-style option (`key = value`).
    pub fn general(&mut self, key: &str, value: impl Into<String>) -> Result<(), DesktopError> {
        if key.trim().is_empty() { return Err(DesktopError::EmptyGeneral); }
        self.general.insert(key.to_string(), value.into());
        Ok(())
    }

    /// Add a monitor line; must contain `,WxH@R` resolution and position.
    pub fn monitor(&mut self, spec: impl Into<String>) -> Result<(), DesktopError> {
        let spec = spec.into();
        let ok = spec.split(',').count() >= 4
            && spec.split(',').nth(1).map_or(false, |m| {
                let m = m.trim();
                (m.contains('x') && m.contains('@'))
                    || matches!(m, "preferred" | "highres" | "highrr")
            });
        if !ok { return Err(DesktopError::BadMonitor(spec)); }
        self.monitors.push(spec);
        Ok(())
    }

    /// Add a keybind; all four fields must be non-empty, no exact duplicates.
    pub fn bind(&mut self, b: Keybind) -> Result<(), DesktopError> {
        if b.mods.trim().is_empty() || b.key.trim().is_empty()
            || b.dispatcher.trim().is_empty() || b.arg.trim().is_empty()
        {
            return Err(DesktopError::BadBind(format!(
                "{},{},{},{}", b.mods, b.key, b.dispatcher, b.arg)));
        }
        if self.binds.contains(&b) {
            return Err(DesktopError::DuplicateBind(format!("{}+{}", b.mods, b.key)));
        }
        self.binds.push(b);
        Ok(())
    }

    /// Convenience keybind constructor.
    pub fn keybind(&mut self, mods: &str, key: &str, dispatcher: &str, arg: &str)
        -> Result<(), DesktopError>
    {
        self.bind(Keybind {
            mods: mods.to_string(),
            key: key.to_string(),
            dispatcher: dispatcher.to_string(),
            arg: arg.to_string(),
        })
    }

    /// Add an `exec-once` startup command.
    pub fn exec_once(&mut self, cmd: impl Into<String>) -> Result<(), DesktopError> {
        let cmd = cmd.into();
        if cmd.trim().is_empty() { return Err(DesktopError::EmptyExec); }
        self.exec_once.push(cmd);
        Ok(())
    }

    /// Render deterministic config text (Omarchy/Hyprland `key = value` style).
    pub fn render(&self) -> String {
        let mut out = String::new();
        for (k, v) in &self.general {
            out.push_str(&format!("{k} = {v}\n"));
        }
        for m in &self.monitors {
            out.push_str(&format!("monitor={m}\n"));
        }
        for b in &self.binds {
            out.push_str(&format!("bind={}, {}, {}, {}\n",
                b.mods, b.key, b.dispatcher, b.arg));
        }
        for c in &self.exec_once {
            out.push_str(&format!("exec-once = {c}\n"));
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build() -> Result<DesktopConfig, DesktopError> {
        let mut c = DesktopConfig::new();
        c.general("layout", "dwindle")?;
        c.monitor("DP-1,2560x1440@144,0x0,1")?;
        c.monitor("HDMI-A-1,preferred,auto-right,auto,1")?;
        c.keybind("SUPER", "Return", "exec", "kitty")?;
        c.keybind("SUPER SHIFT", "E", "exec", "nautilus")?;
        c.exec_once("waybar")?;
        c.exec_once("swaybg -i /usr/share/backgrounds/omarchy.png")?;
        Ok(c)
    }

    #[test]
    fn renders_omarchy_style_config() {
        let text = build().unwrap().render();
        assert!(text.contains("layout = dwindle"));
        assert!(text.contains("monitor=DP-1,2560x1440@144,0x0,1"));
        assert!(text.contains("bind=SUPER, Return, exec, kitty"));
        assert!(text.contains("exec-once = waybar"));
    }

    #[test]
    fn bad_monitor_fails() {
        let mut c = DesktopConfig::new();
        assert!(matches!(c.monitor("DP-1"), Err(DesktopError::BadMonitor(_))));
        assert!(matches!(c.monitor("DP-1,1920x1080@60,0x0,1"), Ok(())));
    }

    #[test]
    fn empty_bind_field_fails() {
        let mut c = DesktopConfig::new();
        assert!(matches!(c.keybind("SUPER", "", "exec", "x"), Err(DesktopError::BadBind(_))));
    }

    #[test]
    fn duplicate_bind_fails() {
        let mut c = DesktopConfig::new();
        c.keybind("SUPER", "Q", "killactive", "").unwrap_err();
        c.keybind("SUPER", "Q", "killactive", "force").unwrap();
        assert!(matches!(
            c.keybind("SUPER", "Q", "killactive", "force"),
            Err(DesktopError::DuplicateBind(_))));
    }

    #[test]
    fn empty_exec_fails() {
        let mut c = DesktopConfig::new();
        assert!(matches!(c.exec_once("  "), Err(DesktopError::EmptyExec)));
    }

}

/// Backwards-compatible component handle (kept for existing callers/tests).
#[derive(Debug, Default)]
pub struct Component {
    name: &'static str,
}

impl Component {
    /// Create the component handle.
    pub fn new() -> Self {
        Self { name: "SigmaOS Component" }
    }

    /// Returns the component name.
    pub fn name(&self) -> &'static str {
        self.name
    }
}
