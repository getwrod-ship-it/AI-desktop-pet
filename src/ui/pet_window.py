# -*- coding: utf-8 -*-
"""桌面宠物 UI 模块"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication,
    QGraphicsOpacityEffect, QLineEdit, QHBoxLayout, QPushButton,
    QMenu, QTextEdit, QDialog, QScrollArea, QFrame, QSlider
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QRect
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QKeyEvent, QAction, QCursor


class BubbleWidget(QWidget):
    """对话气泡组件"""

    # 信号：气泡隐藏
    bubble_hidden = pyqtSignal()

    def __init__(self, text: str, duration: int = 5000, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.is_user = is_user
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._setup_ui(text)
        self._setup_timer()

    def _setup_ui(self, text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(250)
        self.label.setFont(QFont("Microsoft YaHei", 10))

        # 根据类型设置不同样式
        if self.is_user:
            # 用户气泡 - 蓝色
            self.label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    background-color: rgba(66, 153, 225, 240);
                    border-radius: 10px;
                    padding: 10px;
                }
            """)
        else:
            # 宠物气泡 - 白色
            self.label.setStyleSheet("""
                QLabel {
                    color: #333333;
                    background-color: rgba(255, 255, 255, 230);
                    border-radius: 10px;
                    padding: 10px;
                    border: 1px solid rgba(200, 200, 200, 100);
                }
            """)

        layout.addWidget(self.label)
        self.setLayout(layout)
        self.adjustSize()

    def _setup_timer(self):
        """设置自动隐藏定时器"""
        # 注意：不再使用单独的定时器来隐藏
        # 隐藏逻辑由 show_and_hide 中的淡出动画完成后触发
        # 淡出动画效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

    def show_and_hide(self):
        """显示气泡并在一段时间后自动隐藏"""
        self.show()
        # 在隐藏前开始淡出
        QTimer.singleShot(self.duration - 500, self._start_fade_out)
        # 确保在duration后完全隐藏（作为备份，正常情况下淡出动画会完成）
        QTimer.singleShot(self.duration + 100, self._on_hide)

    def _start_fade_out(self):
        """开始淡出动画"""
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.start()
        self.animation.finished.connect(self._on_hide)

    def _on_hide(self):
        """隐藏时发送信号"""
        self.bubble_hidden.emit()
        self.hide()


class HistoryDialog(QWidget):
    """对话历史记录对话框"""

    def __init__(self, history: list, parent=None):
        super().__init__(parent)
        self.history = history

        self.setWindowTitle("对话历史")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedSize(450, 550)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 标题
        title = QLabel("📝 对话历史记录")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #333333;")
        layout.addWidget(title)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #f5f5f5;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)

        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(12)

        if not self.history:
            # 无历史记录
            empty_label = QLabel("暂无对话记录")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #999999; font-size: 14px; padding: 50px;")
            content_layout.addWidget(empty_label)
        else:
            # 显示历史记录
            for item in self.history:
                role = item.get("role", "")
                content = item.get("content", "")

                # 使用 QTextEdit 显示消息，支持自动高度调整
                msg_text = QTextEdit()
                msg_text.setPlainText(content)
                msg_text.setReadOnly(True)
                msg_text.setFont(QFont("Microsoft YaHei", 10))
                msg_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
                msg_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                msg_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                msg_text.setMaximumWidth(360)
                msg_text.setMinimumWidth(100)

                # 计算文档高度并设置固定高度
                doc = msg_text.document()
                doc.setTextWidth(340)  # 设置文档宽度用于计算高度
                height = doc.size().height() + 20  # 加上内边距
                msg_text.setFixedHeight(max(40, int(height)))

                if role == "user":
                    # 用户消息 - 蓝色
                    msg_text.setStyleSheet("""
                        QTextEdit {
                            color: white;
                            background-color: #4299e1;
                            border: none;
                            border-radius: 10px;
                            padding: 8px;
                        }
                    """)
                    content_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
                else:
                    # 助手消息 - 白色
                    msg_text.setStyleSheet("""
                        QTextEdit {
                            color: #333333;
                            background-color: white;
                            border: 1px solid #e0e0e0;
                            border-radius: 10px;
                            padding: 8px;
                        }
                    """)
                    content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                content_layout.addWidget(msg_text)

            # 添加弹簧，让内容从上方开始
            content_layout.addStretch()

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(35)
        close_btn.clicked.connect(self.hide)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 13px;
            }
        """)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def closeEvent(self, event):
        """重写关闭事件，只隐藏窗口"""
        event.ignore()
        self.hide()

    def keyPressEvent(self, event):
        """按ESC键关闭"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class InputDialog(QWidget):
    """用户输入对话框"""

    # 信号：用户提交输入
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 输入框
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.setFont(QFont("Microsoft YaHei", 10))
        self.input_field.setMinimumWidth(200)
        self.input_field.returnPressed.connect(self._on_submit)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 8px;
                color: #333333;
            }
            QLineEdit:focus {
                border: 1px solid #66afe9;
            }
        """)

        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_button.setFont(QFont("Microsoft YaHei", 9))
        self.send_button.setFixedSize(50, 32)
        self.send_button.clicked.connect(self._on_submit)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        layout.addWidget(self.input_field)
        layout.addWidget(self.send_button)

        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(240, 240, 240, 230);
                border-radius: 8px;
            }
        """)

        self.adjustSize()
        self.setFixedHeight(self.height())

    def _on_submit(self):
        """提交输入"""
        text = self.input_field.text().strip()
        if text:
            self.submitted.emit(text)
            self.input_field.clear()
            self.hide()

    def show_at(self, pos: QPoint):
        """在指定位置显示"""
        self.move(pos)
        self.show()
        self.input_field.setFocus()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class SizeDialog(QWidget):
    """大小调节对话框"""

    # 信号：大小改变
    size_changed = pyqtSignal(int)

    def __init__(self, current_size: int = 150, parent=None):
        super().__init__(parent)
        self.current_size = current_size

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)

        # 标题
        title = QLabel("调节大小")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 大小显示标签
        self.size_label = QLabel(f"{self.current_size}px")
        self.size_label.setFont(QFont("Microsoft YaHei", 9))
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.size_label)

        # 滑块
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(80)
        self.slider.setMaximum(300)
        self.slider.setValue(self.current_size)
        self.slider.setFixedWidth(150)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #e0e0e0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #45a049;
            }
        """)

        layout.addWidget(self.slider)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFont(QFont("Microsoft YaHei", 9))
        cancel_btn.setFixedSize(60, 28)
        cancel_btn.clicked.connect(self.hide)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        btn_layout.addWidget(cancel_btn)

        # 确认按钮
        confirm_btn = QPushButton("确认")
        confirm_btn.setFont(QFont("Microsoft YaHei", 9))
        confirm_btn.setFixedSize(60, 28)
        confirm_btn.clicked.connect(self._on_confirm)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 245);
                border-radius: 8px;
                border: 1px solid #cccccc;
            }
        """)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def _on_slider_changed(self, value: int):
        """滑块值改变"""
        self.size_label.setText(f"{value}px")
        self.current_size = value
        self.size_changed.emit(value)

    def _on_confirm(self):
        """确认按钮"""
        self.hide()

    def show_at(self, pos: QPoint):
        """在指定位置显示"""
        self.move(pos)
        self.show()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class FrameAnimator:
    """帧动画播放器"""

    def __init__(self, pet_label: QLabel, fps: int = 10):
        self.pet_label = pet_label
        self.fps = fps
        self.frames: list[QPixmap] = []
        self.current_frame = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._next_frame)
        self.is_playing = False
        self.loop = True

    def load_frames(self, folder_path: str, size: int = 150):
        """加载帧动画图片"""
        self.frames.clear()
        folder = Path(folder_path)
        if not folder.exists():
            return False

        # 查找所有 png 文件并排序
        frame_files = sorted(folder.glob("*.png"))

        for frame_path in frame_files:
            pixmap = QPixmap(str(frame_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.frames.append(scaled)

        return len(self.frames) > 0

    def load_single_image(self, image_path: str, size: int = 150):
        """加载单张静态图片"""
        self.frames.clear()
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            # 图片加载失败
            return False

        # 图片加载成功，缩放并添加到帧列表
        scaled = pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.frames.append(scaled)
        return True

    def start(self, loop: bool = True):
        """开始播放动画"""
        if not self.frames:
            return

        self.loop = loop
        self.current_frame = 0
        self.is_playing = True
        interval = int(1000 / self.fps)
        self.timer.start(interval)
        self._show_current_frame()

    def stop(self):
        """停止动画"""
        self.timer.stop()
        self.is_playing = False

    def _next_frame(self):
        """播放下一帧"""
        self.current_frame += 1

        if self.current_frame >= len(self.frames):
            if self.loop:
                self.current_frame = 0
            else:
                # 非循环动画播放完毕，停在最后一帧
                self.current_frame = len(self.frames) - 1
                self.timer.stop()
                self.is_playing = False
                return

        self._show_current_frame()

    def _show_current_frame(self):
        """显示当前帧"""
        if self.frames and 0 <= self.current_frame < len(self.frames):
            self.pet_label.setPixmap(self.frames[self.current_frame])


class PetWindow(QWidget):
    """桌面宠物窗口"""

    # 信号：用户点击宠物
    clicked = pyqtSignal()
    # 信号：用户请求对话
    dialog_requested = pyqtSignal(str)
    # 信号：退出应用
    quit_requested = pyqtSignal()
    # 信号：清除历史
    clear_history_requested = pyqtSignal()
    # 信号：查看历史
    view_history_requested = pyqtSignal()

    def __init__(self, pet_name: str = "小爪", bubble_duration: int = 5000):
        super().__init__()
        self.pet_name = pet_name
        self.bubble_duration = bubble_duration

        # 窗口属性设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 宠物大小
        self._pet_size = 200

        # 固定窗口大小
        self.setFixedSize(self._pet_size + 30, self._pet_size + 30)

        # 拖拽相关
        self._drag_pos = QPoint()
        self._is_dragging = False

        # 宠物状态
        self._current_state = "idle"

        # 气泡组件
        self._bubble: BubbleWidget = None

        # 输入对话框
        self._input_dialog: InputDialog = None
        # 输入框打开标志（用于阻止主动交互）
        self._input_dialog_open: bool = False

        # 大小调节对话框
        self._size_dialog: SizeDialog = None

        # 先设置UI（创建pet_label）
        self._setup_ui()

        # 初始化帧动画播放器（pet_label已在_setup_ui中创建）
        self._animator = FrameAnimator(self.pet_label, fps=12)

        # 加载初始状态图片
        self._load_state_image("idle")

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 宠物图标
        self.pet_label = QLabel()
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pet_label.setFixedSize(self._pet_size, self._pet_size)
        layout.addWidget(self.pet_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

        # 设置背景透明
        self.setStyleSheet("background: transparent;")

    def _set_default_icon(self):
        """设置默认图标（使用 Unicode 表情）"""
        self.pet_label.setText("🐧")
        self.pet_label.setStyleSheet("""
            QLabel {
                font-size: 80px;
                background: transparent;
            }
        """)

    def set_pet_state(self, state: str):
        """
        设置宠物状态

        Args:
            state: 状态名称 (idle/doubt/think)
        """
        self._current_state = state
        self._load_state_image(state)

    def _load_state_image(self, state: str):
        """根据状态加载对应的图片/动画"""
        # 先停止当前动画
        self._animator.stop()

        size = self._pet_size

        # 静态图片状态（单张图片）
        static_states = {
            "doubt": "assets/pet/doubt/制作思考的png序列帧 (5).png",
            "sad": "assets/pet/sad/制作思考的png序列帧 (2).png",
            "cry": "assets/pet/cry/制作思考的png序列帧 (3).png",
        }

        # 动画状态（文件夹）
        animation_states = {
            "idle": "assets/pet/idle",
            "think": "assets/pet/think",
            "happy": "assets/pet/happy",
            "angry": "assets/pet/angry",
        }

        # 处理帧动画状态
        if state in animation_states:
            folder_path = animation_states[state]
            if Path(folder_path).exists():
                if self._animator.load_frames(folder_path, size):
                    # idle 状态循环播放，其他状态播放一次
                    loop = (state == "idle")
                    self._animator.start(loop=loop)
                    return

        # 处理静态图片状态
        if state in static_states:
            image_path = static_states[state]
            if Path(image_path).exists():
                if self._animator.load_single_image(image_path, size):
                    self._animator.start(loop=False)
                    return

        # 如果指定状态加载失败，回退到 idle
        if state != "idle":
            self._load_state_image("idle")
        else:
            # idle 也加载失败，记录错误但不显示企鹅
            print(f"[PetWindow] 无法加载图片: {state}")

    def set_pet_size(self, size: int):
        """设置宠物大小"""
        self._pet_size = size
        # 更新窗口大小
        self.setFixedSize(size + 30, size + 30)
        # 更新标签大小
        self.pet_label.setFixedSize(size, size)
        # 重新加载当前状态的图片
        self._load_state_image(self._current_state)

    def show_bubble(self, text: str, is_user: bool = False):
        """
        显示对话气泡

        Args:
            text: 气泡内容
            is_user: 是否为用户气泡（蓝色），False 为宠物气泡（白色）
        """
        # 隐藏之前的气泡
        if self._bubble:
            self._bubble.hide()
            self._bubble.deleteLater()

        # 创建新气泡
        self._bubble = BubbleWidget(text, self.bubble_duration, is_user, self)

        # 连接气泡隐藏信号
        self._bubble.bubble_hidden.connect(self._on_bubble_hidden)

        # 计算气泡位置（在宠物上方）
        pet_pos = self.pos()
        bubble_width = self._bubble.width()
        bubble_height = self._bubble.height()

        # 气泡居中显示在宠物上方
        bubble_x = pet_pos.x() + (self.width() - bubble_width) // 2
        bubble_y = pet_pos.y() - bubble_height - 10

        # 确保气泡不会超出屏幕
        screen = QApplication.primaryScreen().geometry()
        bubble_x = max(0, min(bubble_x, screen.width() - bubble_width))
        bubble_y = max(0, bubble_y)

        self._bubble.move(bubble_x, bubble_y)
        self._bubble.show_and_hide()

    def _on_bubble_hidden(self):
        """气泡隐藏后恢复到 idle 状态"""
        print(f"[PetWindow] _on_bubble_hidden 被调用，当前状态: {self._current_state}")
        # 只有当前是宠物回复的气泡才恢复 idle
        if self._current_state not in ["idle", "doubt"]:
            print(f"[PetWindow] 恢复到 idle 状态")
            self.set_pet_state("idle")
        else:
            print(f"[PetWindow] 状态无需改变")

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self._is_dragging = False
            self.clicked.emit()

    def mouseMoveEvent(self, event):
        """鼠标移动事件（拖拽）"""
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._is_dragging = True

            # 移动时同步移动气泡
            if self._bubble and self._bubble.isVisible():
                self._update_bubble_position()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                # 单击事件（非拖拽）
                self._on_click()
            self._is_dragging = False

    def _on_click(self):
        """单击宠物时的处理"""
        # 显示输入对话框
        self._show_input_dialog()

    def _show_input_dialog(self):
        """显示或隐藏输入对话框"""
        # 如果输入框已存在且可见，则隐藏它
        if self._input_dialog is not None and self._input_dialog.isVisible():
            self._input_dialog.hide()
            self.set_pet_state("idle")
            self._input_dialog_open = False  # 标记输入框已关闭
            return

        # 切换到疑惑状态（用户正在输入）
        self.set_pet_state("doubt")
        self._input_dialog_open = True  # 标记输入框已打开

        if self._input_dialog is None:
            self._input_dialog = InputDialog()
            self._input_dialog.submitted.connect(self._on_input_submitted)

        # 计算输入框位置（在宠物下方，靠近脚部）
        pet_pos = self.pos()
        pet_height = self.height()
        pet_width = self.width()

        # 输入框显示在宠物下方，稍微偏移一点
        dialog_x = pet_pos.x() + (pet_width - self._input_dialog.width()) // 2
        dialog_y = pet_pos.y() + pet_height - 5  # 在宠物底部附近

        # 确保不超出屏幕
        screen = QApplication.primaryScreen().geometry()
        dialog_x = max(0, min(dialog_x, screen.width() - self._input_dialog.width()))
        dialog_y = max(0, dialog_y)

        self._input_dialog.show_at(QPoint(dialog_x, dialog_y))

    def _on_input_submitted(self, text: str):
        """用户提交输入"""
        self.dialog_requested.emit(text)

    def contextMenuEvent(self, event):
        """右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
                color: white;
            }
        """)

        # 对话动作
        chat_action = QAction("💬 对话", self)
        chat_action.triggered.connect(self._on_click)
        menu.addAction(chat_action)

        menu.addSeparator()

        # 查看历史
        history_action = QAction("📜 查看历史", self)
        history_action.triggered.connect(self._on_view_history)
        menu.addAction(history_action)

        menu.addSeparator()

        # 清除历史
        clear_action = QAction("🗑️ 清除记忆", self)
        clear_action.triggered.connect(self._on_clear_history)
        menu.addAction(clear_action)

        menu.addSeparator()

        # 调节大小
        resize_action = QAction("📐 调节大小", self)
        resize_action.triggered.connect(self._on_resize)
        menu.addAction(resize_action)

        menu.addSeparator()

        # 退出动作
        quit_action = QAction("❌ 退出", self)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        # 显示菜单
        menu.exec(QCursor.pos())

    def _on_view_history(self):
        """查看历史记录"""
        self.view_history_requested.emit()

    def _on_clear_history(self):
        """清除历史记录"""
        self.clear_history_requested.emit()
        self.show_bubble("记忆已清除~", is_user=False)

    def _on_resize(self):
        """调节大小"""
        if self._size_dialog is None:
            self._size_dialog = SizeDialog(self._pet_size)
            self._size_dialog.size_changed.connect(self.set_pet_size)

        # 计算对话框位置（在宠物上方）
        pet_pos = self.pos()
        dialog_x = pet_pos.x() + (self.width() - self._size_dialog.width()) // 2
        dialog_y = pet_pos.y() - self._size_dialog.height() - 10

        # 确保不超出屏幕
        screen = QApplication.primaryScreen().geometry()
        dialog_x = max(0, min(dialog_x, screen.width() - self._size_dialog.width()))
        dialog_y = max(0, dialog_y)

        # 更新滑块当前值
        self._size_dialog.slider.setValue(self._pet_size)

        self._size_dialog.show_at(QPoint(dialog_x, dialog_y))

    def _on_quit(self):
        """退出应用"""
        self.quit_requested.emit()

    def _update_bubble_position(self):
        """更新气泡位置"""
        if self._bubble:
            pet_pos = self.pos()
            bubble_x = pet_pos.x() + (self.width() - self._bubble.width()) // 2
            bubble_y = pet_pos.y() - self._bubble.height() - 10
            self._bubble.move(bubble_x, bubble_y)

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self._bubble:
            self._bubble.hide()
            self._bubble.deleteLater()

        if self._input_dialog:
            self._input_dialog.hide()
            self._input_dialog.deleteLater()

        super().closeEvent(event)
