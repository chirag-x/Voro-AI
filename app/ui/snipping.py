from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QScreen, QPixmap
from PySide6.QtCore import Qt, QRect, Signal

class SnipOverlay(QWidget):
    snip_completed = Signal(QPixmap)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Use a completely normal mouse pointer so viewers on a screen share don't get suspicious
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        geom = QRect()
        for screen in QApplication.screens():
            geom = geom.united(screen.geometry())
        self.setGeometry(geom)
        
        self.begin = None
        self.end = None
        
    def showEvent(self, event):
        super().showEvent(event)
        self._apply_privacy_flag()
        # Grab pristine background so dark overlay doesn't contaminate the snip
        self._screenshots = {}
        for screen in QApplication.screens():
            self._screenshots[screen] = screen.grabWindow(0)

    def _apply_privacy_flag(self):
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                WDA_EXCLUDEFROMCAPTURE = 0x11
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except Exception as e:
                print(f"Could not set SnipOverlay privacy flag: {e}")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if self.begin and self.end:
            rect = QRect(self.begin, self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 150, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.begin = None
            self.end = None
            self.hide()
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        self.begin = pos
        self.end = self.begin
        self.update()
        
    def mouseMoveEvent(self, event):
        pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        self.end = pos
        self.update()
        
    def mouseReleaseEvent(self, event):
        pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        self.end = pos
        self.hide()
        if self.begin and self.end:
            rect = QRect(self.begin, self.end).normalized()
            if rect.width() >= 10 and rect.height() >= 10:
                screen = QApplication.screenAt(rect.topLeft()) or QApplication.primaryScreen()
                if screen and hasattr(self, '_screenshots') and screen in self._screenshots:
                    full_pm = self._screenshots[screen]
                    screen_rect = screen.geometry()
                    local_rect = rect.translated(-screen_rect.topLeft())
                    dpr = screen.devicePixelRatio()
                    crop_rect = QRect(
                        int(local_rect.x() * dpr),
                        int(local_rect.y() * dpr),
                        int(local_rect.width() * dpr),
                        int(local_rect.height() * dpr)
                    )
                    cropped = full_pm.copy(crop_rect)
                    self.snip_completed.emit(cropped)
                elif screen:
                    screen_rect = screen.geometry()
                    local_rect = rect.translated(-screen_rect.topLeft())
                    pixmap = screen.grabWindow(0, local_rect.x(), local_rect.y(), local_rect.width(), local_rect.height())
                    self.snip_completed.emit(pixmap)
        self.begin = None
        self.end = None
        self.close()
