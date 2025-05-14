from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtGui import QPainter, QColor
import sys
from ui.lyricWidget import LyricWidget
from utils.hacktool import MemoryHookTool
from utils.network import LyricNetwork
import logging as log
import time

class HoverContainerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mouse_over = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
    def enterEvent(self, event):
        """Called when the mouse enters the widget's area."""
        self.mouse_over = True
        self.update()

    def leaveEvent(self, event):
        """Called when the mouse leaves the widget's area."""
        self.mouse_over = False
        self.update()

    def paintEvent(self, event):
        """Paint the widget. If mouse is over, draw the background."""
        if self.mouse_over:
            painter = QPainter(self)
            painter.setRenderHints(QPainter.Antialiasing)
            background_color = QColor(0, 0, 0, 100)
            painter.fillRect(self.rect(), background_color)

    def resizeEvent(self, event):
        """Called when the widget is resized."""
        super().resizeEvent(event)
        for child in self.findChildren(LyricWidget):
            child.resize(self.size())

class Demo(QWidget):
    def __init__(self):
        super().__init__(parent=None)

        self.refresh_interval = 300
        self.is_master = False
        self.last_lyric = None
        self.last_lyric_time = 0

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
            self.lyricWidget = LyricWidget(self.desktopLyric) # LyricWidget is a child

            self.desktopLyric.resize(1200, 150)
            self.lyricWidget.resize(self.desktopLyric.width(), self.desktopLyric.height())
            
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
        super().closeEvent(event)

if __name__ == '__main__':
    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    w = Demo()
    app.exec_()