# Design System

## Style
- Modern, stealthy, and minimal.
- Dark mode first to reduce eye strain.
- Clean grid layouts using QFormLayout and padded QFrame boxes.

## Typography
- Font Family: Inter (or system sans-serif like Segoe UI).
- Global UI Font Size: 15px minimum for readability.
- Header Font Size: 16px to 18px.

## Colors
- **Background (Main)**: #1E1E1E (Dark gray/black)
- **Background (Panel/Frame)**: #2D2D2D
- **Text (Primary)**: #FFFFFF
- **Text (Muted/Secondary)**: #A0A0A0
- **Accent (Primary)**: #4CAF50 (Green for active/success states)
- **Accent (Secondary)**: #2196F3 (Blue for informational highlights)
- **Destructive**: #F44336 (Red for errors/stopping)

## UI Requirements
- Elements should use 1px solid borders with a 6px border radius.
- Sliders must respond to click-and-drag only (disable mouse-wheel scrolling to prevent accidental changes).
- Buttons should be modern solid-color QPushButton elements rather than native checkboxes.
- The main overlay must be transparent, frameless (Qt.FramelessWindowHint), and support clicking through when inactive.