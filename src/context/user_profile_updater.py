"""用户画像更新模块"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter

from src.context.models import (
    UserProfile,
    ScreenEvent,
    DialogTurn
)


class UserProfileUpdater:
    """用户画像更新器"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化用户画像更新器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.work_pattern_min_samples = self.config.get("work_pattern_min_samples", 5)
        self.app_importance_threshold = self.config.get("app_importance_threshold", 10)
        self.dialog_style_update_rate = self.config.get("dialog_style_update_rate", 0.1)
        self.topic_interest_decay = self.config.get("topic_interest_decay", 0.05)

    def update(
        self,
        profile: UserProfile,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent]
    ) -> UserProfile:
        """
        更新用户画像

        Args:
            profile: 当前用户画像
            dialogs: 新的对话记录
            screens: 新的屏幕事件

        Returns:
            更新后的用户画像
        """
        # 更新基础信息
        self._update_basic_info(profile)

        # 更新工作模式
        if screens:
            self._update_work_pattern(profile, screens)

        # 更新对话偏好
        if dialogs:
            self._update_dialog_preferences(profile, dialogs)

        # 更新情绪模式
        self._update_emotion_patterns(profile, dialogs, screens)

        # 更新关系记忆
        self._update_relationship(profile, dialogs)

        # 更新能力画像
        self._update_capabilities(profile, screens, dialogs)

        return profile

    def _update_basic_info(self, profile: UserProfile):
        """更新基础信息"""
        now = datetime.now()

        # 更新最后活跃时间
        profile.last_active = now.isoformat()

        # 计算交互天数
        try:
            first_seen = datetime.fromisoformat(profile.first_seen)
            days = (now - first_seen).days + 1
            profile.total_interaction_days = days
        except (ValueError, TypeError):
            pass

    def _update_work_pattern(self, profile: UserProfile, screens: List[ScreenEvent]):
        """更新工作模式"""
        if len(screens) < self.work_pattern_min_samples:
            return

        # 统计应用使用频率
        app_counter = Counter()
        for screen in screens:
            if screen.app_name:
                app_counter[screen.app_name] += 1

        # 合并到主应用统计
        for app, count in app_counter.items():
            profile.primary_apps[app] = profile.primary_apps.get(app, 0) + count

        # 更新主要应用（过滤掉不重要的）
        profile.primary_apps = {
            k: v for k, v in profile.primary_apps.items()
            if v >= self.app_importance_threshold
        }

        # 识别工作时间模式
        hours = []
        for screen in screens:
            try:
                ts = datetime.fromisoformat(screen.timestamp)
                hours.append(ts.hour)
            except (ValueError, TypeError):
                continue

        if hours:
            # 找出最活跃的时间段
            hour_counter = Counter(hours)
            peak_hours = [h for h, _ in hour_counter.most_common(3)]

            # 判断生产力风格
            if len(set(hours)) <= 3:
                # 集中在少数时间段 -> 专注型
                profile.productivity_style = "专注型"
            else:
                # 分散在多个时间段 -> 多任务型
                profile.productivity_style = "多任务型"

        # 活动类型统计
        activity_counter = Counter(s.activity_type for s in screens)
        if activity_counter:
            # 记录主要活动类型
            main_activity = activity_counter.most_common(1)[0][0]

            # 根据活动类型更新工作模式
            if "work" in [s.activity_type for s in screens if "work" in s.activity_type.lower()]:
                pass  # 保持现有工作模式

    def _update_dialog_preferences(self, profile: UserProfile, dialogs: List[DialogTurn]):
        """更新对话偏好"""
        user_dialogs = [d for d in dialogs if d.role == "user"]
        if not user_dialogs:
            return

        # 分析输入长度，判断沟通风格
        avg_length = sum(len(d.content) for d in user_dialogs) / len(user_dialogs)

        if avg_length < 20:
            new_style = "简洁"
        elif avg_length > 100:
            new_style = "详细"
        else:
            new_style = "适中"

        # 平滑更新风格
        if profile.communication_style == "unknown":
            profile.communication_style = new_style
        else:
            # 不突然改变，保持稳定
            pass

        # 提取话题并更新兴趣度
        topics = self._extract_topics_from_dialogs(user_dialogs)
        for topic in topics:
            current = profile.topic_interests.get(topic, 0.5)
            # 增加兴趣度
            profile.topic_interests[topic] = min(1.0, current + 0.1)

        # 衰减旧话题的兴趣度
        decayed_topics = {}
        for topic, interest in profile.topic_interests.items():
            if topic not in topics:
                # 未在本次对话中出现的话题，衰减
                new_interest = interest * (1 - self.topic_interest_decay)
                if new_interest > 0.1:  # 保留一定底值
                    decayed_topics[topic] = new_interest
            else:
                decayed_topics[topic] = interest
        profile.topic_interests = decayed_topics

        # 分析提问风格
        questions = [d for d in user_dialogs if "?" in d.content or "？" in d.content]
        if questions:
            # 检查是否直接提问
            direct_patterns = ["是什么", "怎么", "为什么", "如何", "能不能", "可以"]
            direct_count = sum(
                1 for q in questions
                if any(p in q.content for p in direct_patterns)
            )
            if direct_count > len(questions) * 0.5:
                profile.question_style = "直接"
            else:
                profile.question_style = "委婉"

    def _update_emotion_patterns(
        self,
        profile: UserProfile,
        dialogs: List[DialogTurn],
        screens: List[ScreenEvent]
    ):
        """更新情绪模式"""
        # 从对话情绪标签统计
        emotions = [d.emotion for d in dialogs if d.emotion]
        if emotions:
            emotion_counter = Counter(emotions)
            main_emotion = emotion_counter.most_common(1)[0][0]

            # 映射到日常情绪
            positive_emotions = {"happy", "joy", "excited", "pleased"}
            negative_emotions = {"sad", "angry", "frustrated", "anxious"}

            if main_emotion in positive_emotions:
                profile.avg_daily_mood = "积极"
            elif main_emotion in negative_emotions:
                profile.avg_daily_mood = "低落"
            else:
                profile.avg_daily_mood = "平静"

        # 识别压力指标
        if screens:
            # 频繁切换应用可能是压力指标
            if len(screens) > 20:
                recent_apps = [s.app_name for s in screens[-20:] if s.app_name]
                if len(set(recent_apps)) > 10:  # 20条记录中超过10个不同应用
                    if "频繁切换应用" not in profile.stress_indicators:
                        profile.stress_indicators.append("频繁切换应用")

        # 识别快乐触发点
        happy_keywords = ["开心", "高兴", "太棒了", "成功了", "完成", "谢谢"]
        for d in dialogs:
            if d.role == "user" and any(kw in d.content for kw in happy_keywords):
                # 记录导致快乐的上下文
                context = d.content[:50]
                if context not in profile.joy_triggers:
                    profile.joy_triggers.append(context)
                    # 限制数量
                    if len(profile.joy_triggers) > 10:
                        profile.joy_triggers.pop(0)

    def _update_relationship(self, profile: UserProfile, dialogs: List[DialogTurn]):
        """更新关系记忆"""
        # 更新交互频率
        profile.interaction_frequency += len([d for d in dialogs if d.role == "user"])

        # 更新信任度（基于交互频率）
        if profile.interaction_frequency > 100:
            profile.trust_level = min(1.0, profile.trust_level + 0.05)

        # 检测深度对话（长对话）
        long_dialogs = [d for d in dialogs if d.role == "user" and len(d.content) > 100]
        if long_dialogs:
            profile.last_deep_conversation = datetime.now().isoformat()

        # 提取共同话题
        topics = self._extract_topics_from_dialogs(dialogs)
        for topic in topics:
            if topic not in profile.shared_contexts:
                profile.shared_contexts.append(topic)
                # 限制数量
                if len(profile.shared_contexts) > 20:
                    profile.shared_contexts.pop(0)

    def _update_capabilities(
        self,
        profile: UserProfile,
        screens: List[ScreenEvent],
        dialogs: List[DialogTurn]
    ):
        """更新能力画像"""
        # 从屏幕应用推断技术技能
        tech_apps = {
            "vscode": "编程",
            "pycharm": "Python编程",
            "intellij": "Java编程",
            "visual studio": "软件开发",
            "eclipse": "Java编程",
            "terminal": "命令行操作",
            "cmd": "命令行操作",
            "powershell": "命令行操作",
            "git": "版本控制",
            "docker": "容器技术",
            "figma": "UI设计",
            "photoshop": "图像处理",
            "excel": "数据分析",
            "word": "文档处理",
            "powerpoint": "演示文稿"
        }

        for screen in screens:
            if screen.app_name:
                app_lower = screen.app_name.lower()
                for app_pattern, skill in tech_apps.items():
                    if app_pattern in app_lower:
                        if skill not in profile.technical_skills:
                            profile.technical_skills.append(skill)

        # 限制技能数量
        if len(profile.technical_skills) > 15:
            profile.technical_skills = profile.technical_skills[-15:]

        # 从对话提取关注领域
        topics = self._extract_topics_from_dialogs(dialogs)
        domain_keywords = {
            "编程": ["代码", "程序", "函数", "变量", "算法"],
            "设计": ["设计", "颜色", "布局", "界面", "UI"],
            "数据": ["数据", "分析", "统计", "报表"],
            "写作": ["写作", "文章", "文档", "内容"],
            "学习": ["学习", "教程", "课程", "知识"],
            "工作": ["工作", "项目", "任务", "进度"]
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in " ".join(topics) for kw in keywords):
                if domain not in profile.domains_of_interest:
                    profile.domains_of_interest.append(domain)

    def _extract_topics_from_dialogs(self, dialogs: List[DialogTurn]) -> List[str]:
        """从对话中提取话题"""
        import re

        # 停用词
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "会", "着", "没有", "看", "好",
            "自己", "这", "那", "什么", "怎么", "这个", "那个", "可以", "能", "做"
        }

        word_counts: Dict[str, int] = {}
        for d in dialogs:
            # 提取中文词汇和英文单词
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', d.content)
            english_words = re.findall(r'[a-zA-Z]{3,}', d.content)

            for word in chinese_words + english_words:
                word = word.lower()
                if word not in stop_words:
                    word_counts[word] = word_counts.get(word, 0) + 1

        # 返回高频词
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]
