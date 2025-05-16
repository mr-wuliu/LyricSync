from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt5.QtWidgets import (QWidget, QApplication, QMessageBox, QPushButton, 
                           QHBoxLayout, QVBoxLayout, QSystemTrayIcon, QMenu, QStyle)
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QIcon
import sys
from ui.lyricWidget import LyricWidget
from utils.hacktool import MemoryHookTool
from utils.network import LyricNetwork
import logging as log
import time

class HoverContainerWidget(QWidget):
    closeRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mouse_over = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        
        # 主垂直布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 菜单栏
        self.menu_bar = QWidget(self)
        self.menu_bar.setFixedHeight(40)
        self.menu_layout = QHBoxLayout(self.menu_bar)
        self.menu_layout.setContentsMargins(10, 5, 10, 5)
        self.menu_layout.setSpacing(10)
        
        # 示例按钮（可根据需要添加/替换）
        self.close_button = QPushButton("×", self.menu_bar)
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: white;
                font-size: 20px;
                border: none;
            }
            QPushButton:hover {
                background: #ff5555;
            }
        """)
        self.close_button.clicked.connect(self.closeRequested.emit)
        self.menu_layout.addStretch()
        self.menu_layout.addWidget(self.close_button)
        
        self.main_layout.addWidget(self.menu_bar)
        # 初始为全透明
        self.set_background_and_menu_visible(False)
        
        self._drag_active = False
        self._drag_pos = None

        # 让菜单栏接受鼠标事件
        self.menu_bar.mousePressEvent = self.menu_bar_mousePressEvent
        self.menu_bar.mouseMoveEvent = self.menu_bar_mouseMoveEvent
        self.menu_bar.mouseReleaseEvent = self.menu_bar_mouseReleaseEvent

    def set_background_and_menu_visible(self, visible):
        if visible:
            self.menu_bar.setStyleSheet("""
                background: rgba(80,80,80,0.8);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom: 1px solid #aaa;
            """)
        else:
            self.menu_bar.setStyleSheet("""
                background: rgba(80,80,80,0.0);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom: 1px solid rgba(0,0,0,0);  /* 变为全透明 */
            """)
        self.repaint()

    def enterEvent(self, event):
        """Called when the mouse enters the widget's area."""
        self.mouse_over = True
        self.set_background_and_menu_visible(True)
        self.update()

    def leaveEvent(self, event):
        """Called when the mouse leaves the widget's area."""
        self.mouse_over = False
        self.set_background_and_menu_visible(False)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        radius = 20
        path = QPainterPath()
        rect = QRectF(self.rect())
        path.addRoundedRect(rect, radius, radius)
        if self.mouse_over:
            background_color = QColor(0, 0, 0, 100)
        else:
            background_color = QColor(0, 0, 0, 0)  # 全透明
        painter.fillPath(path, background_color)

    def resizeEvent(self, event):
        """Called when the widget is resized."""
        super().resizeEvent(event)
        for child in self.findChildren(LyricWidget):
            child.resize(self.size())

    def menu_bar_mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def menu_bar_mouseMoveEvent(self, event):
        if self._drag_active and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def menu_bar_mouseReleaseEvent(self, event):
        self._drag_active = False
        event.accept()

class Demo(QWidget):
    def __init__(self):
        super().__init__(parent=None)

        self.refresh_interval = 300
        self.is_master = False
        self.last_lyric = None
        self.last_lyric_time = 0

        # 创建系统托盘
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        
        # 创建托盘菜单
        self.tray_menu = QMenu()
        self.quit_action = self.tray_menu.addAction("退出")
        self.quit_action.triggered.connect(self.close)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

        self.init_network()
        if self.is_master:
            self.hookTool = MemoryHookTool(
                process_name = "kwmusic.exe",
                dll_name="UIDeskLyric.dll"
            )
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.updateLyric)
            self.timer.start(self.refresh_interval)
        else:
            self.desktopLyric = HoverContainerWidget()
            self.desktopLyric.closeRequested.connect(self.close)
            self.lyricWidget = LyricWidget(self.desktopLyric)
            self.desktopLyric.main_layout.addWidget(self.lyricWidget, 1)  # 让歌词区在菜单栏下方自动填满
            self.desktopLyric.resize(1200, 150)
            self.desktopLyric.show()

            self.current_lyric = ["loading"]
            self.lyricWidget.setLyric(self.current_lyric, [1000])
            self.lyricWidget.setPlay(True)

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.updateLyric)
            self.timer.start(self.refresh_interval)

    def init_network(self):
        """初始化网络"""
        try:
            reply = QMessageBox.question(
                self, '选择模式',
                '是否作为主设备？\n主设备将读取本地音乐播放器的歌词并广播给其他设备。\n从设备将接收主设备广播的歌词。',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            self.is_master = reply == QMessageBox.Yes
            self.network = LyricNetwork()
            if not self.network.init_network(self.is_master):
                raise Exception("网络初始化失败")
            
            if not self.is_master:
                log.info("已设置为从设备模式，等待接收歌词...")
            else:
                log.info("已设置为主设备模式，开始读取并广播歌词...")
                
        except Exception as e:
            log.error(f"网络初始化失败: {e}")
            QMessageBox.critical(self, '错误', f'网络初始化失败: {e}')
            sys.exit(1)

    def load_lyric_mem(self) -> str:
        """从内存读取歌词"""
        if not self.is_master:
            return None
            
        if not hasattr(self, 'hookTool'):
            log.error("主设备未正确初始化 Hook 工具")
            return None

        base_address = self.hookTool.get_module_base()
        if base_address is None:
            log.error("无法获取模块地址")
            return None
            
        lyrics_address = self.hookTool.get_process_pointer(base_address, 0x2B7B8, [0x8, 0x1F4, 0x0])
        if lyrics_address is None:
            log.error("无法解析多级指针")
            return None
            
        raw_bytes = self.hookTool.read_bytes(lyrics_address)
        if raw_bytes is None:
            log.error("读取失败")
            return None
            
        return MemoryHookTool.clean_lyrics(raw_bytes, encode='gbk')

    def load_lyric_net(self) -> tuple:
        """从网络读取歌词"""
        if self.is_master:
            return None, None
        return self.network.get_lyric()

    def updateLyric(self):
        """定时更新歌词"""
        if self.is_master:
            new_lyric = self.load_lyric_mem()
            if new_lyric and new_lyric != self.last_lyric:
                self.last_lyric = new_lyric
                self.network.send_lyric(new_lyric)
        else:
            result = self.load_lyric_net()
            if result:
                lyric, duration = result
                if lyric != self.last_lyric:
                    self.last_lyric = lyric
                    self.lyricWidget.setLyric([lyric], [duration], update=True)
                    self.lyricWidget.setPlay(True)

    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        if hasattr(self, 'network'):
            self.network.close()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        super().closeEvent(event)

if __name__ == '__main__':
    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    w = Demo()
    app.exec_()