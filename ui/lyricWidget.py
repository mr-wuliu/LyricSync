from PyQt5.QtCore import QPointF, QPropertyAnimation, Qt, pyqtProperty
from PyQt5.QtGui import (
    QColor, QFont, QFontMetrics,
    QPainter, QPainterPath, QPen
)
from typing import List
from dataclasses import dataclass
from PyQt5.QtWidgets import QWidget
from config import config
import logging

log = logging.getLogger(__name__)

@dataclass
class LyricWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 歌词
        self.lyric = ""
        # 当前歌词的持续时间
        self.duration = 0
        # 歌词高亮显示的宽度
        self.__maskWidth = 0
        # 歌词在部件中的水平位置
        self.__textX = 0
        
        # 初始化动画对象
        self.maskWidthAni = QPropertyAnimation(self, b'maskWidth', self)
        self.textXAni = QPropertyAnimation(self, b'textX', self)

    def paintEvent(self, e):
        """绘制歌词"""
        if not self.lyric:
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        # 绘制歌词
        self.__drawLyric(
            painter,
            self.__textX,
            config["lyric.font-size"],
            self.__maskWidth,
            self.lyricFont,
            self.lyric
        )

    def __drawLyric(self, painter: QPainter, x, y, width, font: QFont, text: str):
        """绘制单行歌词"""
        painter.setFont(font)

        # 绘制背景文本
        path = QPainterPath()
        path.addText(QPointF(x, y), font, text)
        painter.strokePath(path, QPen(
            QColor(*config["lyric.stroke-color"]), config["lyric.stroke-size"]))
        painter.fillPath(path, QColor(*config['lyric.font-color']))

        # 绘制高亮文本
        painter.fillPath(
            self.__getMaskedLyricPath(path, width),
            QColor(*config['lyric.highlight-color'])
        )

    def __getMaskedLyricPath(self, path: QPainterPath, width: float):
        """获取遮罩后的歌词路径"""
        subPath = QPainterPath()
        rect = path.boundingRect()
        rect.setWidth(width)
        subPath.addRect(rect)
        return path.intersected(subPath)

    def setLyric(self, lyric: list, duration: List[int], update=False):
        """设置歌词

        Parameters
        ----------
        lyric: list
            list contains one line of lyric

        duration: List[int]
            list contains duration in milliseconds

        update: bool
            update immediately or not
        """
        if not lyric:
            return
            
        self.lyric = lyric[0]
        self.duration = max(duration[0], 1)
        self.__maskWidth = 0

        # 停止正在运行的动画
        for ani in [self.maskWidthAni, self.textXAni]:
            if ani.state() == ani.Running:
                ani.stop()

        # 处理歌词
        fontMetrics = QFontMetrics(self.lyricFont)
        w = fontMetrics.width(self.lyric)
        
        # 如果歌词长度超过窗口宽度，需要滚动显示
        if w > self.width():
            self.__textX = 10  # 起始位置
            self.__setAnimation(self.textXAni, 10, self.width() - w - 10, self.duration)
        else:
            # 歌词居中显示
            self.__textX = (self.width() - w) // 2
            self.textXAni.setEndValue(None)  # 不需要滚动动画

        self.__setAnimation(self.maskWidthAni, 0, w, self.duration)

        if update:
            self.update()

    def __setAnimation(self, ani: QPropertyAnimation, start, end, duration: int):
        """设置动画参数"""
        if ani.state() == ani.Running:
            ani.stop()

        ani.setStartValue(start)
        ani.setEndValue(end)
        ani.setDuration(duration)

    def setPlay(self, isPlay: bool):
        """设置播放状态"""
        for ani in [self.maskWidthAni, self.textXAni]:
            if isPlay and ani.state() != ani.Running and ani.endValue() is not None:
                ani.start()
            elif not isPlay and ani.state() == ani.Running:
                ani.pause()

    def minimumHeight(self) -> int:
        """计算最小高度"""
        size = config["lyric.font-size"]
        return int(size * 1.5 + 20)

    @property
    def lyricFont(self):
        """获取歌词字体"""
        font = QFont(config["lyric.font-family"])
        font.setPixelSize(config["lyric.font-size"])
        return font

    # 属性定义
    def getMaskWidth(self):
        return self.__maskWidth

    def setMaskWidth(self, pos: int):
        self.__maskWidth = pos
        self.update()

    def getTextX(self):
        return self.__textX

    def setTextX(self, pos: int):
        self.__textX = pos
        self.update()

    maskWidth = pyqtProperty(float, getMaskWidth, setMaskWidth)
    textX = pyqtProperty(float, getTextX, setTextX)

