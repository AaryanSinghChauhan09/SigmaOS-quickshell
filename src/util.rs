//! quickshell model — QML-based Wayland desktop shell.

#[derive(Debug, Clone)]
pub struct Shell {
    pub config_path: String,
    pub loaded: bool,
    pub modules: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Model {
    pub shell: Option<Shell>,
}

impl Default for Model {
    fn default() -> Self { Self { shell: None } }
}

impl Model {
    pub fn new() -> Self { Self::default() }

    pub fn load(&mut self, config: &str) -> bool {
        self.shell = Some(Shell {
            config_path: config.into(),
            loaded: true,
            modules: vec!["bar".into(), "launcher".into(), "notifications".into()],
        });
        true
    }

    pub fn is_loaded(&self) -> bool {
        self.shell.as_ref().map_or(false, |s| s.loaded)
    }

    pub fn modules(&self) -> &[String] {
        self.shell.as_ref().map_or(&[], |s| &s.modules)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn load_modules() {
        let mut q = Model::new();
        assert!(q.load("~/.config/quickshell/shell.qml"));
        assert!(q.is_loaded());
        assert_eq!(q.modules().len(), 3);
    }
}
