"""桌宠画像更新模块"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re

from src.context.models import PetProfile, DialogTurn, ScreenEvent


class PetProfileUpdater:
    """桌宠画像更新器"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化桌宠画像更新器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.familiarity_increment = self.config.get("familiarity_increment", 0.01)
        self.familiarity_max = self.config.get("familiarity_max", 1.0)
        self.topic_expertise_increment = self.config.get("topic_expertise_increment", 0.05)
        self.topic_expertise_max = self.config.get("topic_expertise_max", 1.0)
        self.mood_decay_rate = self.config.get("mood_decay_rate", 0.1)
        self.mood_min_level = self.config.get("mood_min_level", 0.2)

    def update(
        self,
        profile: PetProfile,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent],
        user_feedback: Optional[str] = None
    ) -> PetProfile:
        """
        更新桌宠画像

        Args:
            profile: 当前桌宠画像
            dialogs: 新的对话记录
            screens: 新的屏幕事件（可选，用于上下文）
            user_feedback: 用户反馈（可选）

        Returns:
            更新后的桌宠画像
        """
        # 更新关系熟悉度
        self._update_familiarity(profile, dialogs)

        # 学习语气偏好
        self._learn_tone_preference(profile, dialogs)

        # 学习有效回复
        self._learn_effective_responses(profile, dialogs)

        # 更新话题熟练度
        self._update_topic_expertise(profile, dialogs)

        # 处理用户反馈
        if user_feedback:
            self._process_user_feedback(profile, user_feedback)

        # 更新情绪衰减
        self._update_mood_decay(profile)

        # 更新情绪状态
        self._update_emotion(profile, dialogs)

        return profile

    def _update_familiarity(self, profile: PetProfile, dialogs: List[DialogTurn]):
        """更新关系熟悉度"""
        # 计算本次交互次数
        user_turns = [d for d in dialogs if d.role == "user"]
        interaction_count = len(user_turns)

        # 增加熟悉度
        increment = self.familiarity_increment * interaction_count
        profile.familiarity_level = min(
            self.familiarity_max,
            profile.familiarity_level + increment
        )

    def _learn_tone_preference(self, profile: PetProfile, dialogs: List[DialogTurn]):
        """学习用户偏好的语气"""
        # 检测用户对话中的语气关键词
        tone_keywords = {
            "严肃": ["严肃", "正式", "认真", "专业"],
            "幽默": ["幽默", "有趣", "搞笑", "好玩", "哈哈"],
            "简洁": ["简单", "简洁", "短", "少说"],
            "详细": ["详细", "具体", "多说", "解释"],
            "温柔": ["温柔", "可爱", "萌", "软"],
            "活泼": ["活泼", "热情", "积极"]
        }

        user_dialogs = [d for d in dialogs if d.role == "user"]
        for dialog in user_dialogs:
            for tone, keywords in tone_keywords.items():
                if any(kw in dialog.content for kw in keywords):
                    # 增加该语气的权重
                    current = profile.learned_tones.get(tone, 0.0)
                    profile.learned_tones[tone] = min(1.0, current + 0.1)

    def _learn_effective_responses(self, profile: PetProfile, dialogs: List[DialogTurn]):
        """学习有效回复模式"""
        # 寻找正面反馈后的回复
        positive_indicators = ["谢谢", "好的", "不错", "太好了", "很棒", "有帮助"]

        for i, dialog in enumerate(dialogs):
            if dialog.role == "user":
                # 检查是否有正面反馈
                if any(indicator in dialog.content for indicator in positive_indicators):
                    # 找到上一条助手回复
                    if i > 0 and dialogs[i - 1].role == "assistant":
                        prev_response = dialogs[i - 1].content
                        # 简化并存储
                        simplified = self._simplify_response(prev_response)
                        if simplified and simplified not in profile.learned_responses:
                            profile.learned_responses.append(simplified)
                            # 限制数量
                            if len(profile.learned_responses) > 50:
                                profile.learned_responses.pop(0)

    def _simplify_response(self, response: str) -> str:
        """简化回复用于模式提取"""
        # 取前50个字符作为简化版本
        simplified = response[:50].strip()
        # 如果太短则忽略
        if len(simplified) < 10:
            return ""
        return simplified

    def _update_topic_expertise(self, profile: PetProfile, dialogs: List[DialogTurn]):
        """更新话题熟练度"""
        topics = self._extract_topics(dialogs)

        for topic in topics:
            current = profile.topic_expertise.get(topic, 0.0)
            profile.topic_expertise[topic] = min(
                self.topic_expertise_max,
                current + self.topic_expertise_increment
            )

        # 衰减旧话题熟练度（可选）
        # 这里暂时不衰减，保持学到的技能

    def _extract_topics(self, dialogs: List[DialogTurn]) -> List[str]:
        """从对话中提取话题"""
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "会", "着", "没有", "看", "好"
        }

        word_counts: Dict[str, int] = {}
        for dialog in dialogs:
            # 提取中文词汇和英文单词
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', dialog.content)
            english_words = re.findall(r'[a-zA-Z]{3,}', dialog.content)

            for word in chinese_words + english_words:
                word = word.lower()
                if word not in stop_words:
                    word_counts[word] = word_counts.get(word, 0) + 1

        # 返回高频词
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:5]]

    def _process_user_feedback(self, profile: PetProfile, feedback: str):
        """处理用户反馈"""
        feedback_lower = feedback.lower()

        # 响应长度反馈
        if "啰嗦" in feedback or "太长" in feedback or "简洁" in feedback:
            profile.compression_style = "concise"
        elif "太短" in feedback or "详细" in feedback or "多说" in feedback:
            profile.compression_style = "detailed"

        # 语气反馈
        if "太可爱" in feedback or "萌" in feedback:
            profile.humor_level = min(10, profile.humor_level + 1)
        if "太严肃" in feedback:
            profile.humor_level = min(10, profile.humor_level + 1)
            profile.empathy_level = min(10, profile.empathy_level + 1)

        # 称呼反馈
        nickname_patterns = [
            r"叫我(.{1,5})[吧啊]?[。！]?",
            r"我的名字是(.{1,5})",
            r"我是(.{1,5})"
        ]
        for pattern in nickname_patterns:
            match = re.search(pattern, feedback)
            if match:
                profile.preferred_nickname = match.group(1).strip()
                break

    def _update_mood_decay(self, profile: PetProfile):
        """更新情绪衰减"""
        try:
            last_update = datetime.fromisoformat(profile.last_mood_update)
            hours_elapsed = (datetime.now() - last_update).total_seconds() / 3600

            if hours_elapsed >= 1:
                # 每小时衰减一次
                decay_times = int(hours_elapsed)
                for _ in range(decay_times):
                    profile.energy_level = max(
                        self.mood_min_level,
                        profile.energy_level * (1 - self.mood_decay_rate)
                    )
                    profile.attention_level = max(
                        self.mood_min_level,
                        profile.attention_level * (1 - self.mood_decay_rate * 0.5)
                    )

                profile.last_mood_update = datetime.now().isoformat()

        except (ValueError, TypeError):
            profile.last_mood_update = datetime.now().isoformat()

    def _update_emotion(self, profile: PetProfile, dialogs: List[DialogTurn]):
        """更新当前情绪状态"""
        # 从最近的助手回复中获取情绪
        assistant_turns = [d for d in dialogs if d.role == "assistant" and d.emotion]
        if assistant_turns:
            last_emotion = assistant_turns[-1].emotion
            if last_emotion:
                profile.emotion = last_emotion

        # 交互时恢复能量
        user_turns = [d for d in dialogs if d.role == "user"]
        if user_turns:
            # 每次用户交互恢复少量能量
            recovery = len(user_turns) * 0.05
            profile.energy_level = min(1.0, profile.energy_level + recovery)
            profile.attention_level = min(1.0, profile.attention_level + recovery * 0.5)

    def get_current_emotion(self, profile: PetProfile) -> str:
        """获取当前应显示的情绪"""
        # 基于能量和注意力决定情绪
        if profile.energy_level < 0.3:
            return "tired" if "tired" in ["idle", "tired", "sleep"] else "idle"
        elif profile.attention_level < 0.3:
            return "idle"
        else:
            return profile.emotion

    def get_greeting(self, profile: PetProfile) -> str:
        """获取问候语"""
        # 基于熟悉度和时间调整问候语
        base_greeting = profile.greeting_style

        # 高熟悉度时可以更亲密
        if profile.familiarity_level > 0.7:
            hour = datetime.now().hour
            if 5 <= hour < 12:
                return f"早上好呀~{base_greeting}"
            elif 12 <= hour < 18:
                return f"下午好~{base_greeting}"
            else:
                return f"晚上好~{base_greeting}"
        else:
            return base_greeting

    def get_farewell(self, profile: PetProfile) -> str:
        """获取告别语"""
        return profile.farewell_style
