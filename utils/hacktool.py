import ctypes
from dataclasses import dataclass
from typing import Optional, Tuple, List

import pymem

import logging

log = logging.getLogger(__name__)

@dataclass
class MemoryHookTool:
    process_name: str
    dll_name: str

    def __post_init__(self):
        self.game = pymem.Pymem(self.process_name)

    def get_module_base(self) -> Optional[int]:
        """
        获取指定模块的基址。
        """
        log.debug(self.dll_name)
        for module in self.game.list_modules():
            if module.name.lower() == self.dll_name.lower():
                return module.lpBaseOfDll
        return None

    def get_process_pointer(self, base_address: int, base_offset: int, offsets: List[int]) -> Optional[int]:
        """
        多级指针跳转，获取最终地址。
        完全模拟 CE 行为：如果 offsets 最后一项是 0，则只跳转到地址，不解引用最终地址。
        """
        kernel32 = ctypes.windll.kernel32
        addr = ctypes.c_ulong()

        start_addr = base_address + base_offset
        log.debug(f"[起始] 基址: {hex(base_address)} + 初始偏移: {hex(base_offset)} = {hex(start_addr)}")

        if not kernel32.ReadProcessMemory(self.game.process_handle, start_addr, ctypes.byref(addr), 4, None):
            log.error(f"[失败] 无法读取地址: {hex(start_addr)}")
            return None

        for i, offset in enumerate(offsets):
            next_addr = addr.value + offset
            log.debug(f"[跳转 {i+1}] 当前值地址: {hex(addr.value)} + 偏移: {hex(offset)} = 跳转目标: {hex(next_addr)}")

            if i == len(offsets) - 1:
                addr.value = next_addr  # 最后一步不解引用
                break

            if not kernel32.ReadProcessMemory(self.game.process_handle, next_addr, ctypes.byref(addr), 4, None):
                log.error(f"[失败] 无法读取地址: {hex(next_addr)}")
                return None

        log.debug(f"[完成] 最终地址: {hex(addr.value)}")
        return addr.value

    def read_bytes(self, address: int, size: int = 120) -> Optional[bytes]:
        """
        获取内存中的字节
        """
        try:
            return self.game.read_bytes(address, size)
        except Exception as e:
            log.error(f"读取内存内容失败: {e}")
            return None

    @staticmethod
    def clean_lyrics(raw_bytes: bytes, encode: str = 'gbk') -> str:
        """
        从原始内存中提取第一个 \r\n 之前的歌词。
        """
        log.debug(f"二进制:{raw_bytes}")
        try:
            text = raw_bytes.decode(encode, errors='ignore')
        except UnicodeDecodeError as e:
            print("解码失败:", e)
            return ""

        # 定位第一个 \r\n\x00 作为歌词终止标志
        end_index = text.find("\r\n\x00")
        if end_index != -1:
            return text[:end_index].strip()
        else:
            return text.strip()  # 没找到换行就返回全部
    @staticmethod
    def byte2int(raw_bytes: bytes) ->int :
        return int.from_bytes(raw_bytes, byteorder='little')
if __name__ == '__main__':
    tool = MemoryHookTool(
        process_name="kwmusic.exe",
        dll_name="UIDeskLyric.dll",
    )

    base_address = tool.get_module_base()
    if base_address is None:
        log.error("无法获取模块地址")
        exit()

    lyrics_address = tool.get_process_pointer(base_address, 0x2B7B8, [0x8, 0x1F4, 0x0])
    if lyrics_address is None:
        log.error("无法解析多级指针")
        exit()

    raw_bytes = tool.read_bytes(lyrics_address)
    if raw_bytes is None:
        log.error("读取失败")
        exit()

    lyrics = MemoryHookTool.clean_lyrics(raw_bytes, encode='gbk')
    print(f"歌词: {lyrics}")

    base_address = tool.get_module_base()
    if base_address is None:
        log.error("无法获取模块地址")
        exit()
    speed_address = tool.get_process_pointer(base_address, 0x00023874, [0x7FC])
    if speed_address is None:
        log.error("无法解析多级指针")
        exit()
    raw_bytes = tool.read_bytes(speed_address, 4)
    if raw_bytes is None:
        log.error("读取失败")
        exit()
    print(raw_bytes)
    print(tool.byte2int(raw_bytes))