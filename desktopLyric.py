from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
import sys
from ui.lyricWidget import LyricWidget
from utils.hacktool import MemoryHookTool
import logging as log
import socket
import json
import threading
import time
import os

"""
先搞个简单版本吧, 只显示单行歌词
"""
class Demo(QWidget):
    # 组播地址和端口
    MULTICAST_ADDR = '239.255.255.250'  # 使用标准组播地址
    MULTICAST_PORT = 31314

    def __init__(self):
        self.refresh_interval = 300  # 歌词刷新间隔，单位：毫秒
        self.is_master = False  # 是否是主设备
        self.last_lyric = None  # 上一次的歌词
        self.last_lyric_time = 0  # 上一次歌词的时间戳

        super().__init__(parent=None)

        # 初始化网络
        self.init_network()

        # 加载工具
        self.hookTool = MemoryHookTool(
            process_name = "kwmusic.exe",
            dll_name="UIDeskLyric.dll"
        )
        # 创建桌面歌词
        self.desktopLyric = QWidget()
        self.lyricWidget = LyricWidget(self.desktopLyric)

        self.desktopLyric.setAttribute(Qt.WA_TranslucentBackground)
        self.desktopLyric.setWindowFlags(
            Qt.FramelessWindowHint | Qt.SubWindow | Qt.WindowStaysOnTopHint)
        self.desktopLyric.resize(1200, 150)  # 减小高度，因为只显示一行
        self.lyricWidget.resize(1200, 150)
        
        # 必须有这一行才能显示桌面歌词界面
        self.desktopLyric.show()

        # 初始化歌词
        self.current_lyric = ["loading"]
        self.lyricWidget.setLyric(self.current_lyric, [1000])
        self.lyricWidget.setPlay(True)

        # 创建定时器并启动
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateLyric)
        self.timer.start(self.refresh_interval)

    def init_network(self):
        """初始化网络"""
        try:
            # 创建UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 设置组播选项
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                               socket.inet_aton(self.MULTICAST_ADDR) + socket.inet_aton('0.0.0.0'))
            
            # 绑定到组播端口
            self.sock.bind(('', self.MULTICAST_PORT))
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self.receive_lyric, daemon=True)
            self.receive_thread.start()
            
            # 询问是否作为主设备
            reply = QMessageBox.question(
                self, '选择模式',
                '是否作为主设备？\n主设备将读取本地音乐播放器的歌词并广播给其他设备。\n从设备将接收主设备广播的歌词。',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            self.is_master = reply == QMessageBox.Yes
            
            if not self.is_master:
                log.info("已设置为从设备模式，等待接收歌词...")
            else:
                log.info("已设置为主设备模式，开始读取并广播歌词...")
                
        except Exception as e:
            log.error(f"网络初始化失败: {e}")
            QMessageBox.critical(self, '错误', f'网络初始化失败: {e}')
            sys.exit(1)

    def receive_lyric(self):
        """接收歌词的线程函数"""
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                if not self.is_master:  # 只有从设备才处理接收到的歌词
                    lyric_data = json.loads(data.decode())
                    # 检查是否是新的歌词
                    if lyric_data['lyric'] != self.last_lyric or \
                       time.time() - self.last_lyric_time > 1:  # 如果超过1秒也更新
                        self.last_lyric = lyric_data['lyric']
                        self.last_lyric_time = time.time()
                        # 在主线程中更新UI
                        QApplication.instance().processEvents()
                        self.lyricWidget.setLyric([lyric_data['lyric']], [lyric_data['duration']], update=True)
                        self.lyricWidget.setPlay(True)
            except Exception as e:
                log.error(f"接收歌词失败: {e}")

    def broadcast_lyric(self, lyric, duration):
        """发送组播歌词"""
        if not self.is_master:
            return
            
        try:
            data = json.dumps({
                'lyric': lyric,
                'duration': duration,
                'timestamp': time.time()
            }).encode()
            self.sock.sendto(data, (self.MULTICAST_ADDR, self.MULTICAST_PORT))
        except Exception as e:
            log.error(f"发送歌词失败: {e}")

    def getLyric(self) -> str:
        if not self.is_master:
            return self.last_lyric or ["等待主设备发送歌词..."]
            
        base_address = self.hookTool.get_module_base()
        if base_address is None:
            log.error("无法获取模块地址")
            return ["无法获取模块地址"]
        lyrics_address = self.hookTool.get_process_pointer(base_address, 0x2B7B8, [0x8, 0x1F4, 0x0])
        if lyrics_address is None:
            log.error("无法解析多级指针")
            return ["无法解析多级指针"]
        raw_bytes = self.hookTool.read_bytes(lyrics_address)
        if raw_bytes is None:
            log.error("读取失败")
            return ["读取失败"]
        lyrics_line = MemoryHookTool.clean_lyrics(raw_bytes, encode='gbk')
        log.debug(f"歌词: {lyrics_line}")
        return [lyrics_line]

    def updateLyric(self):
        """ 定时更新歌词 """
        new_lyric = self.getLyric()
        if new_lyric != self.current_lyric:
            self.current_lyric = new_lyric
            self.lyricWidget.setLyric(new_lyric, [3000], update=True)
            self.lyricWidget.setPlay(True)
            
            # 如果是主设备，广播新歌词
            if self.is_master:
                self.broadcast_lyric(new_lyric[0], 3000)

if __name__ == '__main__':
    log.basicConfig(level=log.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    w = Demo()
    app.exec_()