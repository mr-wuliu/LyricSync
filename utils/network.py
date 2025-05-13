import socket
import json
import threading
import time
import logging as log
from queue import Queue
from typing import Optional, Tuple

class LyricNetwork:
    MULTICAST_ADDR = '239.255.255.250'
    MULTICAST_PORT = 31314
    
    def __init__(self):
        self.sock = None
        self.is_master = False
        self.lyric_queue = Queue()
        self.receive_thread = None
        self.running = True
        
    def init_network(self, is_master: bool) -> bool:
        """初始化网络"""
        try:
            self.is_master = is_master
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # 设置组播TTL为2，允许跨子网
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            # 允许端口重用
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 绑定到所有接口
            self.sock.bind(('0.0.0.0', self.MULTICAST_PORT))
            
            # 加入组播组
            mreq = socket.inet_aton(self.MULTICAST_ADDR) + socket.inet_aton('0.0.0.0')
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # 设置组播回环
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            
            # 设置组播接口
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('0.0.0.0'))
            
            self.receive_thread = threading.Thread(target=self._receive_lyric, daemon=True)
            self.receive_thread.start()
            
            return True
                
        except Exception as e:
            log.error(f"网络初始化失败: {e}")
            return False
            
    def _receive_lyric(self):
        """接收歌词的线程函数"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                if not self.is_master:
                    lyric_data = json.loads(data.decode())
                    self.lyric_queue.put(lyric_data)
                    log.debug(f"收到来自 {addr} 的歌词")
            except Exception as e:
                log.error(f"接收歌词失败: {e}")
                
    def send_lyric(self, lyric: str, duration: int = 3000) -> bool:
        """发送歌词"""
        if not self.is_master or not self.sock:
            return False
            
        try:
            data = json.dumps({
                'lyric': lyric,
                'duration': duration,
                'timestamp': time.time()
            }).encode()
            self.sock.sendto(data, (self.MULTICAST_ADDR, self.MULTICAST_PORT))
            log.debug(f"发送歌词: {lyric[:20]}...")
            return True
        except Exception as e:
            log.error(f"发送歌词失败: {e}")
            return False
            
    def get_lyric(self) -> Optional[Tuple[str, int]]:
        """从队列获取歌词"""
        try:
            if self.lyric_queue.empty():
                return None
            data = self.lyric_queue.get_nowait()
            return data['lyric'], data['duration']
        except:
            return None
            
    def close(self):
        """关闭网络连接"""
        self.running = False
        if self.sock:
            try:
                # 离开组播组
                mreq = socket.inet_aton(self.MULTICAST_ADDR) + socket.inet_aton('0.0.0.0')
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            except:
                pass
            self.sock.close()
