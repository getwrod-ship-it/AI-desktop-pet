"""上下文管理模块 - 整合记忆系统"""
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path

from src.context.models import (
    ScreenEvent,
    DialogTurn,
    DialogBuffer,
    ScreenBuffer,
    TimeSlotSummary,
    UserProfile,
    PetProfile,
    get_preset_profile
)
from src.context.database import DatabaseManager
from src.context.compressor import MemoryCompressor, CompressorConfig
from src.context.user_profile_updater import UserProfileUpdater
from src.context.pet_profile_updater import PetProfileUpdater
from src.context.context_builder import ContextBuilder


class ContextManager:
    """上下文管理器 - 管理完整的记忆系统"""

    def __init__(
        self,
        db_path: str = "./data/context.db",
        max_screen_history: int = 50,
        max_dialog_history: int = 20,
        memory_config: Dict[str, Any] = None,
        user_profile_config: Dict[str, Any] = None,
        pet_profile_config: Dict[str, Any] = None,
        llm_compress_func: Optional[Callable[[str, str], str]] = None
    ):
        """
        初始化上下文管理器

        Args:
            db_path: 数据库路径
            max_screen_history: 最大屏幕历史数（兼容旧参数）
            max_dialog_history: 最大对话历史数（兼容旧参数）
            memory_config: 记忆系统配置
            user_profile_config: 用户画像配置
            pet_profile_config: 桌宠画像配置
            llm_compress_func: LLM压缩函数
        """
        # 配置
        self.memory_config = memory_config or {}
        self.user_profile_config = user_profile_config or {}
        self.pet_profile_config = pet_profile_config or {}

        # 数据库管理器
        self.db_manager = DatabaseManager(db_path)

        # 缓冲区
        self._dialog_buffer = DialogBuffer(
            max_turns=self.memory_config.get("max_recent_dialogs", 100)
        )
        self._screen_buffer = ScreenBuffer(
            max_events=self.memory_config.get("max_recent_screens", 100)
        )

        # 画像
        self._user_profile: Optional[UserProfile] = None
        self._pet_profile: Optional[PetProfile] = None

        # 压缩器
        compressor_config = CompressorConfig(
            recent_window_minutes=0,  # 时间压缩策略已废弃，设为0
            keep_recent_dialogs=self.memory_config.get("keep_recent_dialogs", 10),
            keep_recent_screens=self.memory_config.get("keep_recent_screens", 3),
            compress_trigger_count=self.memory_config.get("compress_trigger_count", 50),
            compress_interval_minutes=0,  # 时间压缩策略已废弃，设为0
            # 每次添加数据都触发压缩
            compress_on_each_event=self.memory_config.get("compress_on_each_event", True)
        )
        self.compressor = MemoryCompressor(
            db_manager=self.db_manager,
            config=compressor_config,
            llm_compress_func=llm_compress_func
        )

        # 画像更新器
        self.user_updater = UserProfileUpdater(self.user_profile_config)
        self.pet_updater = PetProfileUpdater(self.pet_profile_config)

        # 上下文构建器（延迟初始化）
        self._context_builder: Optional[ContextBuilder] = None

        # 压缩历史缓存
        self._compressed_history: List[TimeSlotSummary] = []

        # 回调函数
        self._on_compress_complete: Optional[Callable[[TimeSlotSummary], None]] = None
        self._on_profile_update: Optional[Callable[[str], None]] = None  # 画像更新回调

        # 保存配置用于重置
        self.user_profile_config = user_profile_config
        self.pet_profile_config = pet_profile_config

        # 初始化
        self._load_from_db()
        self._init_profiles()

    def _load_from_db(self):
        """从数据库加载数据"""
        # 加载最近30个对话记录
        all_dialogs = self.db_manager.get_recent_dialogs(30)

        # 分类：前20条压缩，后10条完整保留
        compressed_dialogs = all_dialogs[:20]
        recent_dialogs = all_dialogs[20:]

        # 将压缩的概括添加到压缩历史
        if compressed_dialogs:
            summary = TimeSlotSummary(
                time_slot="startup",
                start_time=compressed_dialogs[0].timestamp,
                end_time=compressed_dialogs[-1].timestamp,
                dialog_summary=self.compressor._compress_dialogs(compressed_dialogs),
                recent_dialogs=[],
                screen_summary="",
                recent_screens=[],
                topics=[]
            )
            self._compressed_history.append(summary)

        # 将完整的对话添加到缓冲区
        for dialog in recent_dialogs:
            self._dialog_buffer.add(dialog)

        # 不加载屏幕事件（不存入数据库）

        # 立即触发一次压缩，确保历史活动及时更新
        self._do_compress()

    def _init_profiles(self):
        """初始化画像"""
        # 加载或创建用户画像
        self._user_profile = self.db_manager.load_user_profile("default")
        if self._user_profile is None:
            self._user_profile = UserProfile()
            self.db_manager.save_user_profile(self._user_profile)

        # 加载或创建桌宠画像
        preset = self.pet_profile_config.get("preset", "penguin_curious")
        self._pet_profile = self.db_manager.load_pet_profile("default", preset)
        if self._pet_profile is None:
            self._pet_profile = get_preset_profile(preset)
            self.db_manager.save_pet_profile(self._pet_profile)

        # 初始化上下文构建器
        self._context_builder = ContextBuilder(
            pet_profile=self._pet_profile,
            user_profile=self._user_profile,
            recent_window_minutes=0  # 时间压缩策略已废弃，设为0
        )

    def set_llm_compress_func(self, func: Callable[[str, str], str]):
        """设置LLM压缩函数"""
        self.compressor.llm_compress_func = func

    def set_compress_callback(self, callback: Callable[[TimeSlotSummary], None]):
        """设置压缩完成回调"""
        self._on_compress_complete = callback
        self.compressor.set_compress_callback(callback)

    def set_profile_update_callback(self, callback: Callable[[str], None]):
        """设置画像更新回调"""
        self._on_profile_update = callback

    # ============ 屏幕事件管理 ============

    def add_screen_event(
        self,
        description: str,
        app_name: Optional[str] = None,
        activity_type: str = "other",
        importance: float = 0.5
    ):
        """
        添加屏幕理解事件

        Args:
            description: 屏幕内容描述
            app_name: 应用名称
            activity_type: 活动类型
            importance: 重要性
        """
        event = ScreenEvent(
            description=description,
            app_name=app_name,
            activity_type=activity_type,
            importance=importance
        )

        # 添加到缓冲区（不存入数据库）
        self._screen_buffer.add(event)

        # 检查是否需要压缩（每添加一条屏幕事件都检查）
        self._check_compress()

    def get_recent_screen_events(self, count: int = 5) -> List[ScreenEvent]:
        """获取最近的屏幕理解事件"""
        return self._screen_buffer.get_recent(count)

    def get_last_screen_description(self) -> Optional[str]:
        """获取最后一次屏幕理解描述"""
        events = self._screen_buffer.get_recent(1)
        return events[0].description if events else None

    # ============ 对话管理 ============

    def add_dialog(
        self,
        role: str,
        content: str,
        emotion: Optional[str] = None,
        importance: float = 1.0
    ):
        """
        添加对话记录

        Args:
            role: 角色 ("user" 或 "assistant")
            content: 对话内容
            emotion: 情绪标签
            importance: 重要性
        """
        turn = DialogTurn(
            role=role,
            content=content,
            emotion=emotion,
            importance=importance
        )

        # 添加到缓冲区
        self._dialog_buffer.add(turn)

        # 保存到数据库
        self.db_manager.add_dialog(turn)

        # 检查是否需要压缩（每添加一条对话都检查）
        self._check_compress()

    def get_dialog_history(self) -> List[Dict[str, str]]:
        """
        获取对话历史，格式化为语言模型需要的格式

        Returns:
            List[Dict]: [{"role": "user/assistant", "content": "..."}]
        """
        return self._dialog_buffer.to_dict_list()

    def get_recent_dialogs(self, count: int = 5) -> List[DialogTurn]:
        """获取最近的对话记录"""
        return self._dialog_buffer.get_recent(count)

    # ============ 压缩管理 ============

    def _check_compress(self):
        """检查是否需要压缩"""
        # 获取压缩配置
        compress_on_each = self.memory_config.get("compress_on_each_event", True)

        if compress_on_each:
            # 每次添加数据都触发压缩
            self._do_compress()
        else:
            # 检查是否超过数量限制
            if len(self._dialog_buffer.turns) >= self.memory_config.get("compress_trigger_count", 15):
                self._do_compress()

    def _do_compress(self):
        """执行压缩"""
        def on_compress_complete(
            kept_dialogs: List[DialogTurn],
            kept_screens: List[ScreenEvent],
            summary: Optional[TimeSlotSummary]
        ):
            if summary:
                # 更新缓冲区
                self._dialog_buffer.turns = kept_dialogs
                self._screen_buffer.events = kept_screens

                # 更新压缩历史缓存
                self._compressed_history.append(summary)
                if len(self._compressed_history) > self.memory_config.get("max_history_slots", 100):
                    self._compressed_history.pop(0)

                # 触发压缩完成回调（在更新画像之前）
                if self._on_compress_complete:
                    try:
                        self._on_compress_complete(summary)
                    except Exception as e:
                        print(f"[ContextManager] 压缩回调错误: {e}")

                # 更新画像
                self._update_profiles_after_compress(summary)

        # 异步压缩
        self.compressor.compress_async(
            self._dialog_buffer.turns,
            self._screen_buffer.events,
            on_compress_complete
        )

    def _update_profiles_after_compress(self, summary: TimeSlotSummary):
        """压缩后更新画像"""
        # 获取被压缩的对话和屏幕事件
        old_dialogs = [
            DialogTurn.from_dict(d) for d in summary.recent_dialogs
        ]
        old_screens = [
            ScreenEvent.from_dict(s) for s in summary.recent_screens
        ]

        # 更新用户画像
        self._user_profile = self.user_updater.update(
            self._user_profile,
            old_dialogs,
            old_screens
        )
        self.db_manager.save_user_profile(self._user_profile)

        # 触发用户画像更新回调
        if self._on_profile_update:
            try:
                self._on_profile_update("用户")
            except Exception as e:
                print(f"[ContextManager] 用户画像回调错误: {e}")

        # 更新桌宠画像
        self._pet_profile = self.pet_updater.update(
            self._pet_profile,
            old_dialogs,
            old_screens
        )
        self.db_manager.save_pet_profile(self._pet_profile)

        # 触发桌宠画像更新回调
        if self._on_profile_update:
            try:
                self._on_profile_update("桌宠")
            except Exception as e:
                print(f"[ContextManager] 桌宠画像回调错误: {e}")

        # 更新上下文构建器
        self._context_builder = ContextBuilder(
            pet_profile=self._pet_profile,
            user_profile=self._user_profile,
            recent_window_minutes=self.memory_config.get("recent_window_minutes", 10)
        )

    def manual_compress(self):
        """手动触发压缩"""
        self._do_compress()

    # ============ 上下文构建 ============

    def get_context_for_prompt(self, include_screen: bool = True) -> str:
        """
        生成上下文提示词（兼容旧API）

        Args:
            include_screen: 是否包含屏幕理解上下文

        Returns:
            str: 上下文提示词
        """
        context_parts = []

        # 添加最近的屏幕理解
        if include_screen and self._screen_buffer.events:
            recent_events = self._screen_buffer.get_recent(3)
            if recent_events:
                context_parts.append("【最近的屏幕内容】")
                for event in recent_events:
                    time_str = event.timestamp.split("T")[1][:8] if "T" in event.timestamp else event.timestamp
                    context_parts.append(f"[{time_str}] {event.description}")

        return "\n".join(context_parts)

    def build_full_prompt(self, user_input: str) -> str:
        """
        构建完整的6层上下文提示词

        Args:
            user_input: 用户输入

        Returns:
            完整的系统提示词
        """
        if self._context_builder is None:
            return self.get_context_for_prompt() + f"\n\n【用户输入】\n{user_input}"

        return self._context_builder.build_prompt(
            recent_dialogs=self._dialog_buffer.turns,
            recent_screens=self._screen_buffer.events,
            compressed_history=self._compressed_history,
            user_input=user_input
        )

    def build_proactive_prompt(self) -> str:
        """
        构建主动交互提示词

        Returns:
            主动交互提示词
        """
        if self._context_builder is None:
            return ""

        last_screen = self.get_last_screen_description()
        return self._context_builder.build_proactive_prompt(
            last_screen=last_screen,
            compressed_history=self._compressed_history
        )

    # ============ 画像访问 ============

    @property
    def user_profile(self) -> UserProfile:
        """获取用户画像"""
        return self._user_profile

    @property
    def pet_profile(self) -> PetProfile:
        """获取桌宠画像"""
        return self._pet_profile

    def update_pet_emotion(self, emotion: str):
        """更新桌宠情绪"""
        self._pet_profile.emotion = emotion
        self._pet_profile.last_mood_update = datetime.now().isoformat()
        self.db_manager.save_pet_profile(self._pet_profile)

    def update_pet_after_dialog(self, user_feedback: Optional[str] = None):
        """对话后更新桌宠画像"""
        # 获取最近的对话
        recent_dialogs = self._dialog_buffer.get_recent(10)

        self._pet_profile = self.pet_updater.update(
            self._pet_profile,
            recent_dialogs,
            [],  # 屏幕事件在压缩时更新
            user_feedback
        )
        self.db_manager.save_pet_profile(self._pet_profile)

        # 更新上下文构建器
        self._context_builder = ContextBuilder(
            pet_profile=self._pet_profile,
            user_profile=self._user_profile,
            recent_window_minutes=self.memory_config.get("recent_window_minutes", 10)
        )

    # ============ 历史管理 ============

    def get_compressed_history(self, limit: int = 5) -> List[TimeSlotSummary]:
        """获取压缩历史"""
        return self._compressed_history[-limit:]

    def clear_history(self):
        """清空所有历史记录"""
        self._dialog_buffer.turns.clear()
        self._screen_buffer.events.clear()
        self._compressed_history.clear()
        self.db_manager.clear_all()

    def clear_profiles(self):
        """清除画像，下次启动将使用预设配置"""
        self.db_manager.clear_profiles()
        # 重新从预设加载画像
        preset = self.pet_profile_config.get("preset", "penguin_curious")
        self._pet_profile = get_preset_profile(preset)
        # 更新上下文构建器
        self._context_builder = ContextBuilder(
            pet_profile=self._pet_profile,
            user_profile=self._user_profile,
            recent_window_minutes=self.memory_config.get("recent_window_minutes", 10)
        )
        print("[ContextManager] 画像已重置为预设")

    # ============ 统计信息 ============

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 计算实际对话总数（包括压缩历史中的）
        total_dialogs = len(self._dialog_buffer.turns)
        for slot in self._compressed_history:
            total_dialogs += len(slot.recent_dialogs)

        return {
            "dialog_count": total_dialogs,
            "recent_dialog_count": len(self._dialog_buffer.turns),
            "screen_count": len(self._screen_buffer.events),
            "compressed_slots": len(self._compressed_history),
            "pet_familiarity": self._pet_profile.familiarity_level,
            "pet_energy": self._pet_profile.energy_level,
            "user_interaction_days": self._user_profile.total_interaction_days
        }
