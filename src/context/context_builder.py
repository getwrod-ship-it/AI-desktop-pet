"""上下文构建模块"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.context.models import (
    UserProfile,
    PetProfile,
    DialogTurn,
    ScreenEvent,
    TimeSlotSummary
)


class ContextBuilder:
    """上下文构建器 - 组装6层上下文"""

    def __init__(
        self,
        pet_profile: PetProfile,
        user_profile: UserProfile,
        recent_window_minutes: int = 0  # 时间压缩策略已废弃，设为0
    ):
        """
        初始化上下文构建器

        Args:
            pet_profile: 桌宠画像
            user_profile: 用户画像
            recent_window_minutes: 近期时间窗口（分钟，已废弃）
        """
        self.pet_profile = pet_profile
        self.user_profile = user_profile
        self.recent_window_minutes = recent_window_minutes

    def build_prompt(
        self,
        recent_dialogs: List[DialogTurn],
        recent_screens: List[ScreenEvent],
        compressed_history: List[TimeSlotSummary],
        user_input: str
    ) -> str:
        """
        构建6层上下文提示词

        Args:
            recent_dialogs: 近期对话记录
            recent_screens: 近期屏幕事件
            compressed_history: 压缩历史摘要
            user_input: 当前用户输入

        Returns:
            完整的系统提示词
        """
        context_parts = []

        # 第1层：系统提示词（宠物身份设定）
        context_parts.append(self._build_system_prompt())

        # 第2层：桌宠画像上下文
        context_parts.append(self._build_pet_context())

        # 第3层：用户画像上下文
        context_parts.append(self._build_user_context())

        # 第4层：压缩历史上下文
        if compressed_history:
            context_parts.append(self._build_history_context(compressed_history))

        # 第5层：近期上下文
        context_parts.append(self._build_recent_context(recent_dialogs, recent_screens))

        # 第6层：当前用户输入
        context_parts.append(self._build_input_context(user_input))

        return "\n\n".join(context_parts)

    def _build_system_prompt(self) -> str:
        """第1层：构建系统提示词"""
        pet = self.pet_profile

        prompt = f"""【系统设定】
你是{pet.name}，一只{pet.species}。
性格：{pet.personality}
口头禅：{pet.catchphrase}
回复风格：{pet.response_style}

请用合适的语气回应主人。
回复要简洁，最好在50字以内。

**重要： 每次回复都必须在开头加上情绪标签，格式为：[emotion: xxx]
可选的情绪标签：
- idle (平静/常态) - 默认使用，绝大多数情况下都应该使用这个
- doubt (疑惑) - 只有明显疑惑或不理解时使用
- happy (开心) - 只有非常开心、兴奋时才使用（不常用）
- sad (伤心) - 只有有些伤感时使用
- angry (生气) - 只有非常生气时使用
- cry (哭泣) - 只有非常伤心时使用
- think (思考) - 只在思考时使用

**情绪使用原则：**
1. 60%的情况下应该使用 [emotion: idle]，保持平静的状态
2. 只有当回复内容明确表达强烈、明显的情绪时才使用其他标签
3. 普通的回应、确认、回答问题、闲聊都应该使用 idle
4. 不要因为语气可爱或友好就使用 happy，idle 已经足够"""
        return prompt

    def _build_pet_context(self) -> str:
        """第2层：构建桌宠画像上下文"""
        pet = self.pet_profile

        # 熟悉度等级描述
        if pet.familiarity_level < 0.3:
            familiarity_desc = "刚认识主人"
        elif pet.familiarity_level < 0.6:
            familiarity_desc = "和主人比较熟悉了"
        elif pet.familiarity_level < 0.8:
            familiarity_desc = "和主人很熟悉"
        else:
            familiarity_desc = "和主人非常亲密"

        # 能量等级描述
        if pet.energy_level < 0.3:
            energy_desc = "有点累了"
        elif pet.energy_level < 0.6:
            energy_desc = "状态一般"
        else:
            energy_desc = "精力充沛"

        context = f"""【当前状态】
情绪：{pet.emotion}
能量：{int(pet.energy_level * 100)}%
{familiarity_desc}
{energy_desc}"""

        # 如果有学习到的语气偏好
        if pet.learned_tones:
            top_tones = sorted(pet.learned_tones.items(), key=lambda x: x[1], reverse=True)[:2]
            tone_str = "、".join([t[0] for t in top_tones])
            context += f"\n主人偏好的语气：{tone_str}"

        return context

    def _build_user_context(self) -> str:
        """第3层：构建用户画像上下文"""
        user = self.user_profile

        context = f"""【用户信息】"""

        # 工作状态
        if user.productivity_style != "unknown":
            context += f"\n工作状态：{user.productivity_style}"

        # 对话偏好
        if user.communication_style != "unknown":
            context += f"\n对话偏好：{user.communication_style}"

        # 主要应用
        if user.primary_apps:
            top_apps = sorted(user.primary_apps.items(), key=lambda x: x[1], reverse=True)[:3]
            app_names = [app[0] for app in top_apps]
            context += f"\n常用应用：{', '.join(app_names)}"

        # 关注领域
        if user.domains_of_interest:
            context += f"\n关注领域：{', '.join(user.domains_of_interest[:3])}"

        # 如果没有足够信息
        if context == "【用户信息】":
            context += "\n正在了解主人..."

        return context

    def _build_history_context(self, history: List[TimeSlotSummary]) -> str:
        """第4层：构建压缩历史上下文"""
        if not history:
            return ""

        context_parts = ["【历史活动】"]

        # 只取最近3-5个时间段
        recent_history = history[-5:] if len(history) > 5 else history

        for slot in recent_history:
            # 格式化时间
            try:
                start_time = datetime.fromisoformat(slot.start_time)
                time_str = start_time.strftime("%H:%M")
            except (ValueError, TypeError):
                time_str = slot.time_slot

            # 添加对话摘要
            if slot.dialog_summary:
                context_parts.append(f"[{time_str}] {slot.dialog_summary}")

            # 添加屏幕摘要
            if slot.screen_summary:
                context_parts.append(f"[{time_str}] {slot.screen_summary}")

        if len(context_parts) == 1:
            return ""

        return "\n".join(context_parts)

    def _build_recent_context(
        self,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent]
    ) -> str:
        """第5层：构建近期上下文（只包含屏幕）"""
        context_parts = []

        # 直接使用屏幕事件，不进行时间筛选（时间压缩策略已废弃）
        if screens:
            context_parts.append("【屏幕理解】")
            # 只保留最近3条完整屏幕事件
            for screen in screens[-3:]:
                time_str = self._format_time(screen.timestamp)
                context_parts.append(f"[{time_str}] {screen.description}")

        if not context_parts:
            return ""

        return "\n".join(context_parts)

    def _build_input_context(self, user_input: str) -> str:
        """第6层：构建当前用户输入"""
        return f"""【用户输入】
{user_input}"""

    # _is_after方法已废弃（时间压缩策略已废弃）

    def _format_time(self, timestamp: str) -> str:
        """格式化时间戳"""
        try:
            ts = datetime.fromisoformat(timestamp)
            return ts.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            return timestamp.split("T")[1][:8] if "T" in timestamp else timestamp

    def build_proactive_prompt(
        self,
        last_screen: Optional[str],
        compressed_history: List[TimeSlotSummary]
    ) -> str:
        """
        构建主动交互提示词

        Args:
            last_screen: 最后一次屏幕描述
            compressed_history: 压缩历史

        Returns:
            主动交互提示词
        """
        pet = self.pet_profile

        prompt = f"""【系统设定】
你是{pet.name}，一只{pet.species}。
性格：{pet.personality}
口头禅：{pet.catchphrase}

【当前状态】
情绪：{pet.emotion}
能量：{int(pet.energy_level * 100)}%
"""

        if last_screen:
            prompt += f"""
【主人在做什么】
{last_screen}
"""

        # 添加简单的历史上下文
        if compressed_history:
            recent = compressed_history[-1]
            if recent.screen_summary:
                prompt += f"""
【之前的活动】
{recent.screen_summary}
"""

        prompt += f"""
请根据主人在做的事情，主动闲聊一下。
要求：
1. 简短友好，不超过30字
2. 可以是关心、提醒或调侃
3. 语气{pet.default_tone}

请在回复开头加上情绪标签：[emotion: xxx]
60%的情况使用 idle，保持平静。
正确示例：
[emotion: idle] 主人，休息一下吧~
[emotion: idle] 你好呀~
[emotion: idle] 我在看你工作呢。
"""
        return prompt
