    def update_activation_label(self, mode: str):
        if mode == 'premium':
            self.activation_label.setText("Premium Mode")
            self.activation_label.setStyleSheet("font-size: 11px; color: #FFD700; font-weight: bold; padding-right: 10px;") # Gold
        elif mode == 'local':
            self.activation_label.setText("Local Mode")
            self.activation_label.setStyleSheet("font-size: 11px; color: #00FF00; font-weight: bold; padding-right: 10px;") # Green
        else:
            self.activation_label.setText("Basic Mode")
            self.activation_label.setStyleSheet(f"font-size: 11px; color: {self.theme['base_text']}; font-weight: bold; padding-right: 10px;")
