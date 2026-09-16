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
            
    def mousePressEvent(self, event):
        self.begin = event.globalPos()
        self.end = self.begin
        self.update()
        
    def mouseMoveEvent(self, event):
        self.end = event.globalPos()
        self.update()
        
    def mouseReleaseEvent(self, event):
        self.hide()
        if self.begin and self.end:
            rect = QRect(self.begin, self.end).normalized()
            screen = QApplication.screenAt(rect.topLeft())
            if screen:
                screen_rect = screen.geometry()
                local_rect = rect.translated(-screen_rect.topLeft())
                pixmap = screen.grabWindow(0, local_rect.x(), local_rect.y(), local_rect.width(), local_rect.height())
                self.snip_completed.emit(pixmap)
        self.close()
