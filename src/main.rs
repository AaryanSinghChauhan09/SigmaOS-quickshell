// SPDX-License-Identifier: Apache-2.0
//! SigmaOS-quickshell CLI daemon & QML validator
//! Provides runtime management and syntax validation for SigmaOS Quickshell desktop shells.

#![forbid(unsafe_code)]

use std::env;
use std::fs;
use std::path::Path;
use std::process::{Command, ExitCode};

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let cmd = args.get(1).map(|s| s.as_str()).unwrap_or("status");

    println!("╔════════════════════════════════════════════╗");
    println!("║       SigmaOS Quickshell Desktop Engine    ║");
    println!("╚════════════════════════════════════════════╝");

    match cmd {
        "check" | "validate" => {
            println!("[*] Validating QML files in ./qml/ ...");
            let qml_dir = Path::new("qml");
            if !qml_dir.exists() {
                eprintln!("[!] QML directory not found: ./qml");
                return ExitCode::FAILURE;
            }

            let mut valid = 0;
            let files = ["shell.qml", "notifications.qml", "launcher.qml", "widgets.qml"];
            for file in files {
                let p = qml_dir.join(file);
                if p.exists() {
                    match fs::read_to_string(&p) {
                        Ok(content) => {
                            if content.contains("import Quickshell") && content.contains("import QtQuick") {
                                println!("  ✔  qml/{} — valid Quickshell component", file);
                                valid += 1;
                            } else {
                                eprintln!("  ⚠  qml/{} — missing Quickshell imports", file);
                            }
                        }
                        Err(e) => eprintln!("  ✘  qml/{} — read error: {}", file, e),
                    }
                } else {
                    eprintln!("  ✘  qml/{} — missing", file);
                }
            }

            if valid == files.len() {
                println!("[✓] All {} Quickshell QML components validated.", valid);
                ExitCode::SUCCESS
            } else {
                eprintln!("[!] Validation incomplete ({}/{} passed)", valid, files.len());
                ExitCode::FAILURE
            }
        }
        "start" | "stop" | "reload" | "status" | "toggle" => {
            let script = Path::new("bin/sigmaos-quickshell");
            if script.exists() {
                let status = Command::new("bash")
                    .arg(script)
                    .arg(cmd)
                    .status();
                match status {
                    Ok(s) if s.success() => ExitCode::SUCCESS,
                    _ => ExitCode::FAILURE,
                }
            } else {
                eprintln!("[!] Shell orchestrator bin/sigmaos-quickshell not found");
                ExitCode::FAILURE
            }
        }
        _ => {
            println!("Usage: sigmaos_quickshell [check|start|stop|reload|status|toggle]");
            ExitCode::SUCCESS
        }
    }
}
