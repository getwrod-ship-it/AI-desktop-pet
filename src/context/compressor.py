"""记忆压缩模块"""
import time
import threading
from datetime import datetime, timedelta
from typing import List, Callable, Optional
from dataclasses import dataclass

from src.context.models import (
    ScreenEvent,
    DialogTurn,
    TimeSlotSummary
)
from src.context.database import DatabaseManager


@dataclass
class CompressorConfig:
    """压缩器配置"""
    recent_window_minutes: int = 10       # 近期时间窗口
    keep_recent_dialogs: int = 10        # 保留的完整对话数（10条以内保留）
    keep_recent_screens: int = 3          # 保留的完整屏幕事件数（近3条保留）
    compress_trigger_count: int = 15      # 触发压缩的数据数量阈值（降低触发阈值）
    compress_interval_minutes: int = 5    # 定时压缩间隔（更频繁）
    compress_on_each_event: bool = True   # 是否每次添加数据都触发压缩


class MemoryCompressor:
    """记忆压缩器"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        config: CompressorConfig,
        llm_compress_func: Optional[Callable[[str, str], str]] = None
    ):
        """
        初始化压缩器

        Args:
            db_manager: 数据库管理器
            config: 压缩器配置
            llm_compress_func: LLM压缩函数 (prompt_type, content) -> summary
                              prompt_type: "dialog" 或 "screen"
        """
        self.db_manager = db_manager
        self.config = config
        self.llm_compress_func = llm_compress_func

        # 压缩状态
        self._last_compress_time = datetime.now()
        self._compress_lock = threading.Lock()

        # 回调函数
        self._on_compress_complete: Optional[Callable[[TimeSlotSummary], None]] = None

    def set_compress_callback(self, callback: Callable[[TimeSlotSummary], None]):
        """设置压缩完成回调"""
        self._on_compress_complete = callback

    def should_compress(self, dialogs: List[DialogTurn], screens: List[ScreenEvent]) -> bool:
        """
        判断是否需要压缩

        Args:
            dialogs: 当前对话列表
            screens: 当前屏幕事件列表

        Returns:
            是否需要压缩
        """
        # 只需要检查是否超过数量限制
        compress_on_each = getattr(self.config, 'compress_on_each_event', True)

        if compress_on_each:
            # 每次都触发压缩
            return True

        # 数量触发
        if len(dialogs) >= self.config.compress_trigger_count:
            return True
        if len(screens) >= self.config.compress_trigger_count:
            return True

        return False

    def compress(
        self,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent]
    ) -> tuple[List[DialogTurn], List[ScreenEvent], Optional[TimeSlotSummary]]:
        """
        执行压缩操作

        Args:
            dialogs: 当前对话列表
            screens: 当前屏幕事件列表

        Returns:
            (保留的对话, 保留的屏幕事件, 压缩的摘要)
        """
        with self._compress_lock:
            return self._do_compress(dialogs, screens)

    def _do_compress(
        self,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent]
    ) -> tuple[List[DialogTurn], List[ScreenEvent], Optional[TimeSlotSummary]]:
        """执行压缩的核心逻辑"""
        # 按数量压缩策略：超过限制的进行概括
        old_dialogs = []
        recent_dialogs = dialogs

        # 对话压缩：超过10条，只保留最后10条，前面的进行概括
        if len(dialogs) > 10:
            old_dialogs = dialogs[:-10]
            recent_dialogs = dialogs[-10:]

        old_screens = []
        recent_screens = screens

        # 屏幕压缩：超过3条，只保留最后3条，前面的进行概括
        if len(screens) > 3:
            old_screens = screens[:-3]
            recent_screens = screens[-3:]

        # 如果没有远期数据，不需要压缩
        if not old_dialogs and not old_screens:
            return dialogs, screens, None

        # 生成时间段标识（使用当前时间）
        now = datetime.now()
        time_slot = self._generate_time_slot(now)

        # 压缩对话：如果超过10条，进行概括
        dialog_summary = ""
        kept_dialogs = []
        if old_dialogs:
            if len(old_dialogs) > 10:
                # 超过10条，概括并只保留最后10条
                dialog_summary = self._compress_dialogs(old_dialogs)
                kept_dialogs = old_dialogs[-10:]
            else:
                # 不超过10条，直接保留
                kept_dialogs = old_dialogs

        # 压缩屏幕事件：只保留最近3条完整记录
        screen_summary = ""
        kept_screens = []
        if old_screens:
            if len(old_screens) > 3:
                # 概括屏幕事件
                screen_summary = self._compress_screens(old_screens)
                # 只保留最近3条完整屏幕
                kept_screens = old_screens[-3:]
            else:
                # 不超过3条，直接保留
                kept_screens = old_screens

        # 提取话题
        topics = self._extract_topics(old_dialogs, old_screens)

        # 创建时间段摘要
        summary = TimeSlotSummary(
            time_slot=time_slot,
            start_time=old_dialogs[0].timestamp if old_dialogs else
                      (old_screens[0].timestamp if old_screens else now.isoformat()),
            end_time=now.isoformat(),
            dialog_summary=dialog_summary,
            recent_dialogs=[d.to_dict() for d in kept_dialogs],
            screen_summary=screen_summary,
            recent_screens=[s.to_dict() for s in kept_screens],
            topics=topics
        )

        # 不保存到数据库（只保留在内存中用于构建上下文）
        # self.db_manager.save_time_slot_summary(summary)

        # 更新压缩时间
        # self._last_compress_time = now  # 时间压缩策略已废弃

        # 触发回调
        if self._on_compress_complete:
            try:
                self._on_compress_complete(summary)
            except Exception as e:
                print(f"[Compressor] 回调执行失败: {e}")

        # 返回保留的数据
        return recent_dialogs + kept_dialogs, recent_screens + kept_screens, summary

    # _is_after方法已废弃（时间压缩策略已废弃）

    def _generate_time_slot(self, time: datetime) -> str:
        """生成时间段标识"""
        # 向下取整到10分钟
        minute = (time.minute // 10) * 10
        return time.strftime(f"%Y-%m-%d-%H:{minute:02d}")

    def _compress_dialogs(self, dialogs: List[DialogTurn]) -> str:
        """压缩对话记录"""
        if not dialogs:
            return ""

        # 格式化对话内容
        dialog_text = "\n".join([
            f"[{d.timestamp.split('T')[1][:8] if 'T' in d.timestamp else d.timestamp}] "
            f"{d.role}: {d.content}"
            for d in dialogs
        ])

        # 如果有LLM压缩函数，使用LLM压缩
        if self.llm_compress_func:
            try:
                summary = self.llm_compress_func("dialog", dialog_text)
                return summary
            except Exception as e:
                print(f"[Compressor] LLM对话压缩失败: {e}")

        # 降级方案：统计和关键词
        user_msgs = [d for d in dialogs if d.role == "user"]
        assistant_msgs = [d for d in dialogs if d.role == "assistant"]

        summary_parts = [f"用户发送{len(user_msgs)}条消息，助手回复{len(assistant_msgs)}条"]

        # 提取关键词
        keywords = self._extract_keywords([d.content for d in dialogs])
        if keywords:
            summary_parts.append(f"主要话题: {', '.join(keywords[:3])}")

        return "。".join(summary_parts)

    def _compress_screens(self, screens: List[ScreenEvent]) -> str:
        """压缩屏幕事件"""
        if not screens:
            return ""

        # 格式化屏幕事件
        screen_text = "\n".join([
            f"[{s.timestamp.split('T')[1][:8] if 'T' in s.timestamp else s.timestamp}] "
            f"{s.description}"
            for s in screens
        ])

        # 如果有LLM压缩函数，使用LLM压缩
        if self.llm_compress_func:
            try:
                summary = self.llm_compress_func("screen", screen_text)
                return summary
            except Exception as e:
                print(f"[Compressor] LLM屏幕压缩失败: {e}")

        # 降级方案：统计应用和活动类型
        app_counts: dict = {}
        activity_counts: dict = {}

        for s in screens:
            if s.app_name:
                app_counts[s.app_name] = app_counts.get(s.app_name, 0) + 1
            activity_counts[s.activity_type] = activity_counts.get(s.activity_type, 0) + 1

        summary_parts = [f"共{len(screens)}次屏幕活动"]

        if app_counts:
            top_apps = sorted(app_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            summary_parts.append(f"主要应用: {', '.join([a[0] for a in top_apps])}")

        if activity_counts:
            top_activities = sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)[:2]
            summary_parts.append(f"活动类型: {', '.join([a[0] for a in top_activities])}")

        return "。".join(summary_parts)

    def _extract_topics(self, dialogs: List[DialogTurn], screens: List[ScreenEvent]) -> List[str]:
        """提取话题"""
        topics = set()

        # 从对话中提取
        for d in dialogs:
            words = self._extract_keywords([d.content])
            topics.update(words[:3])

        # 从屏幕事件中提取
        for s in screens:
            words = self._extract_keywords([s.description])
            topics.update(words[:2])

        return list(topics)[:10]

    def _extract_keywords(self, texts: List[str]) -> List[str]:
        """简单关键词提取"""
        # 停用词
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "他", "她", "它", "什么", "怎么", "这个", "那个", "可以",
            "能", "做", "让", "还", "把", "被", "比", "更", "最", "吗", "呢", "啊", "哦",
            "嗯", "哈", "吧", "呀", "嘿", "哎", "唉", "噢", "喂", "嗨", "呵", "啦"
        }

        # 简单分词（按空格和标点）
        import re
        word_counts: dict = {}

        for text in texts:
            # 提取中文词汇（2-4个字）和英文单词
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
            english_words = re.findall(r'[a-zA-Z]{3,}', text)

            for word in chinese_words + english_words:
                word = word.lower()
                if word not in stop_words and len(word) >= 2:
                    word_counts[word] = word_counts.get(word, 0) + 1

        # 按频率排序
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]

    def compress_async(
        self,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent],
        callback: Optional[Callable[[List[DialogTurn], List[ScreenEvent], Optional[TimeSlotSummary]], None]] = None
    ):
        """
        异步执行压缩

        Args:
            dialogs: 当前对话列表
            screens: 当前屏幕事件列表
            callback: 压缩完成回调 (kept_dialogs, kept_screens, summary)
        """
        def _compress_task():
            try:
                kept_dialogs, kept_screens, summary = self.compress(dialogs, screens)
                if callback:
                    callback(kept_dialogs, kept_screens, summary)
            except Exception as e:
                print(f"[Compressor] 异步压缩失败: {e}")
                if callback:
                    callback(dialogs, screens, None)

        thread = threading.Thread(target=_compress_task, daemon=True)
        thread.start()
        return thread
