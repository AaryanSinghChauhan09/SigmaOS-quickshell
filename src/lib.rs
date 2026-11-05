#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WidgetDescriptor {
    pub name: String,
    pub qml_file: String,
    pub anchor_edge: String,
}

#[derive(Debug, Default)]
pub struct QuickShellHost {
    widgets: Vec<WidgetDescriptor>,
}

impl QuickShellHost {
    pub fn new() -> Self { Self { widgets: Vec::new() } }
    pub fn load_widget(&mut self, name: &str, qml: &str, edge: &str) {
        self.widgets.push(WidgetDescriptor {
            name: name.into(),
            qml_file: qml.into(),
            anchor_edge: edge.into(),
        });
    }
    pub fn widget_count(&self) -> usize { self.widgets.len() }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_quickshell_host_aaa() {
        // Arrange
        let mut host = QuickShellHost::new();
        // Act
        host.load_widget("ClockBar", "/usr/share/quickshell/clock.qml", "Top");
        // Assert
        assert_eq!(host.widget_count(), 1);
    }
}
