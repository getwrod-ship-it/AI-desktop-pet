"""屏幕捕获模块"""
import mss
import numpy as np
from PIL import Image
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ScreenConfig:
    """屏幕捕获配置"""
    monitor: int = 1
    capture_interval: float = 5.0
    change_threshold: float = 0.05


class ScreenCapture:
    """屏幕捕获类，支持变化检测"""

    def __init__(self, config: ScreenConfig):
        self.config = config
        self._last_frame: Optional[np.ndarray] = None
        self._monitor_info: Optional[dict] = None

    def _get_monitor(self) -> dict:
        """获取显示器信息"""
        if self._monitor_info is None:
            with mss.mss() as sct:
                monitors = sct.monitors
                # monitors[0] 是所有显示器的总和，monitors[1] 是第一个显示器
                monitor_index = min(self.config.monitor, len(monitors) - 1)
                monitor_index = max(1, monitor_index)  # 至少为 1
                self._monitor_info = monitors[monitor_index]
        return self._monitor_info

    def capture(self) -> Optional[Image.Image]:
        """截取屏幕"""
        try:
            monitor = self._get_monitor()
            # 每次截图时创建新的 mss 实例（线程安全）
            with mss.mss() as sct:
                screenshot = sct.grab(monitor)
                # 转换为 PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                return img
        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def capture_with_change_detection(self) -> Tuple[Optional[Image.Image], bool]:
        """
        截取屏幕并检测是否有变化

        Returns:
            Tuple[Optional[Image.Image], bool]: (截图, 是否有变化)
        """
        current_frame = self.capture()
        if current_frame is None:
            return None, False

        # 转换为 numpy 数组进行变化检测
        current_array = np.array(current_frame)

        if self._last_frame is None:
            self._last_frame = current_array
            return current_frame, True

        # 计算帧间差异
        has_changed = self._detect_change(self._last_frame, current_array)
        self._last_frame = current_array

        return current_frame, has_changed

    def _detect_change(self, frame1: np.ndarray, frame2: np.ndarray) -> bool:
        """
        检测两帧之间的变化

        Args:
            frame1: 上一帧
            frame2: 当前帧

        Returns:
            bool: 变化是否超过阈值
        """
        # 计算差异
        diff = np.abs(frame1.astype(np.float32) - frame2.astype(np.float32))

        # 计算变化像素比例
        # 使用阈值来判断像素是否发生变化
        pixel_threshold = 30  # 像素值差异阈值
        changed_pixels = np.sum(diff > pixel_threshold)
        total_pixels = diff.size

        change_ratio = changed_pixels / total_pixels

        return change_ratio > self.config.change_threshold

    def get_screen_size(self) -> Tuple[int, int]:
        """获取屏幕尺寸"""
        monitor = self._get_monitor()
        return monitor["width"], monitor["height"]

    def close(self):
        """关闭资源"""
        pass
