"""记忆系统数据模型"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum


class ActivityType(Enum):
    """活动类型枚举"""
    WORK = "work"           # 工作
    STUDY = "study"         # 学习
    ENTERTAINMENT = "entertainment"  # 娱乐
    COMMUNICATION = "communication"  # 沟通交流
    BROWSING = "browsing"   # 浏览网页
    CODING = "coding"       # 编程
    DOCUMENT = "document"   # 文档处理
    OTHER = "other"         # 其他


# ============ 基础数据类 ============

@dataclass
class ScreenEvent:
    """屏幕理解事件"""
    id: str = ""
    timestamp: str = ""
    description: str = ""
    app_name: Optional[str] = None      # 应用名称
    activity_type: str = "other"        # 活动类型
    importance: float = 0.5             # 重要性 0-1

    def __post_init__(self):
        """初始化后处理"""
        if not self.id:
            self.id = datetime.now().isoformat()
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_within_minutes(self, minutes: int) -> bool:
        """判断是否在指定分钟数内"""
        try:
            event_time = datetime.fromisoformat(self.timestamp)
            return datetime.now() - event_time <= timedelta(minutes=minutes)
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "description": self.description,
            "app_name": self.app_name,
            "activity_type": self.activity_type,
            "importance": self.importance
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScreenEvent":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            description=data.get("description", ""),
            app_name=data.get("app_name"),
            activity_type=data.get("activity_type", "other"),
            importance=data.get("importance", 0.5)
        )


@dataclass
class DialogTurn:
    """对话轮次"""
    id: str = ""
    timestamp: str = ""
    role: str = ""          # "user" or "assistant"
    content: str = ""
    emotion: Optional[str] = None    # 情绪标签
    importance: float = 1.0          # 重要性 0-1

    def __post_init__(self):
        """初始化后处理"""
        if not self.id:
            self.id = datetime.now().isoformat()
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_within_minutes(self, minutes: int) -> bool:
        """判断是否在指定分钟数内"""
        try:
            event_time = datetime.fromisoformat(self.timestamp)
            return datetime.now() - event_time <= timedelta(minutes=minutes)
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
            "emotion": self.emotion,
            "importance": self.importance
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogTurn":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            role=data.get("role", ""),
            content=data.get("content", ""),
            emotion=data.get("emotion"),
            importance=data.get("importance", 1.0)
        )


# ============ 缓冲区数据类 ============

@dataclass
class DialogBuffer:
    """近期对话缓冲区"""
    turns: List[DialogTurn] = field(default_factory=list)
    max_turns: int = 100      # 10分钟内最多100条

    def add(self, turn: DialogTurn):
        """添加对话"""
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns.pop(0)

    def get_recent(self, count: int = 5) -> List[DialogTurn]:
        """获取最近N条对话"""
        return self.turns[-count:]

    def get_within_minutes(self, minutes: int) -> List[DialogTurn]:
        """获取指定分钟内的对话"""
        return [t for t in self.turns if t.is_within_minutes(minutes)]

    def clear_old(self, minutes: int):
        """清除指定分钟前的对话"""
        self.turns = [t for t in self.turns if t.is_within_minutes(minutes)]

    def to_dict_list(self) -> List[Dict[str, str]]:
        """转换为字典列表（用于LLM）"""
        return [{"role": t.role, "content": t.content} for t in self.turns]


@dataclass
class ScreenBuffer:
    """近期屏幕理解缓冲区"""
    events: List[ScreenEvent] = field(default_factory=list)
    max_events: int = 100     # 10分钟内最多100条

    def add(self, event: ScreenEvent):
        """添加屏幕事件"""
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)

    def get_recent(self, count: int = 5) -> List[ScreenEvent]:
        """获取最近N条屏幕事件"""
        return self.events[-count:]

    def get_within_minutes(self, minutes: int) -> List[ScreenEvent]:
        """获取指定分钟内的屏幕事件"""
        return [e for e in self.events if e.is_within_minutes(minutes)]

    def clear_old(self, minutes: int):
        """清除指定分钟前的屏幕事件"""
        self.events = [e for e in self.events if e.is_within_minutes(minutes)]


# ============ 压缩历史数据类 ============

@dataclass
class TimeSlotSummary:
    """时间段摘要（每10分钟压缩一次）"""
    time_slot: str               # 时间段标识，如 "2026-03-09-14:30"
    start_time: str              # 开始时间
    end_time: str                # 结束时间
    dialog_summary: str = ""     # 对话内容概括
    recent_dialogs: List[Dict[str, Any]] = field(default_factory=list)  # 最近5条完整对话
    screen_summary: str = ""     # 屏幕活动概括
    recent_screens: List[Dict[str, Any]] = field(default_factory=list)  # 最近5条屏幕事件
    topics: List[str] = field(default_factory=list)  # 本时段讨论的话题

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "time_slot": self.time_slot,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "dialog_summary": self.dialog_summary,
            "recent_dialogs": self.recent_dialogs,
            "screen_summary": self.screen_summary,
            "recent_screens": self.recent_screens,
            "topics": self.topics
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeSlotSummary":
        """从字典创建"""
        return cls(
            time_slot=data.get("time_slot", ""),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            dialog_summary=data.get("dialog_summary", ""),
            recent_dialogs=data.get("recent_dialogs", []),
            screen_summary=data.get("screen_summary", ""),
            recent_screens=data.get("recent_screens", []),
            topics=data.get("topics", [])
        )


# ============ 用户画像数据类 ============

@dataclass
class TimeRange:
    """时间范围"""
    start_hour: int = 0
    end_hour: int = 0
    days: List[int] = field(default_factory=list)  # 0=周一, 6=周日

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "days": self.days
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeRange":
        return cls(
            start_hour=data.get("start_hour", 0),
            end_hour=data.get("end_hour", 0),
            days=data.get("days", [])
        )


@dataclass
class Milestone:
    """重要事件"""
    date: str = ""
    event: str = ""
    significance: int = 5  # 重要性 1-10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "event": self.event,
            "significance": self.significance
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
        return cls(
            date=data.get("date", ""),
            event=data.get("event", ""),
            significance=data.get("significance", 5)
        )


@dataclass
class UserProfile:
    """用户画像 - 描述用户是谁"""
    # 基础信息
    user_id: str = "default"
    first_seen: str = ""
    last_active: str = ""
    total_interaction_days: int = 0

    # 工作模式（从屏幕理解学习）
    working_hours: List[Dict[str, Any]] = field(default_factory=list)
    primary_apps: Dict[str, int] = field(default_factory=dict)  # 应用名称 -> 使用次数
    productivity_style: str = "unknown"  # 专注型/多任务型
    break_patterns: List[Dict[str, Any]] = field(default_factory=list)

    # 对话偏好（从对话记录学习）
    communication_style: str = "unknown"  # 简洁/详细/幽默
    response_timing: str = "unknown"      # 喜欢/不喜欢快速回复
    topic_interests: Dict[str, float] = field(default_factory=dict)  # 话题 -> 兴趣度
    question_style: str = "unknown"       # 直接/委婉

    # 情绪模式（从对话和屏幕理解综合）
    avg_daily_mood: str = "neutral"       # 平均情绪状态
    stress_indicators: List[str] = field(default_factory=list)  # 压力指标
    joy_triggers: List[str] = field(default_factory=list)       # 快乐触发点

    # 重要事件（标记）
    milestones: List[Dict[str, Any]] = field(default_factory=list)

    # 关系记忆
    trust_level: float = 0.5              # 信任度 0-1
    interaction_frequency: int = 0        # 交互频率
    last_deep_conversation: str = ""      # 上次深度对话时间
    shared_contexts: List[str] = field(default_factory=list)    # 共同话题/经历

    # 能力画像
    technical_skills: List[str] = field(default_factory=list)   # 技术技能
    domains_of_interest: List[str] = field(default_factory=list)  # 关注领域
    learning_style: str = "unknown"       # 学习风格

    def __post_init__(self):
        """初始化后处理"""
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat()
        if not self.last_active:
            self.last_active = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "first_seen": self.first_seen,
            "last_active": self.last_active,
            "total_interaction_days": self.total_interaction_days,
            "working_hours": self.working_hours,
            "primary_apps": self.primary_apps,
            "productivity_style": self.productivity_style,
            "break_patterns": self.break_patterns,
            "communication_style": self.communication_style,
            "response_timing": self.response_timing,
            "topic_interests": self.topic_interests,
            "question_style": self.question_style,
            "avg_daily_mood": self.avg_daily_mood,
            "stress_indicators": self.stress_indicators,
            "joy_triggers": self.joy_triggers,
            "milestones": self.milestones,
            "trust_level": self.trust_level,
            "interaction_frequency": self.interaction_frequency,
            "last_deep_conversation": self.last_deep_conversation,
            "shared_contexts": self.shared_contexts,
            "technical_skills": self.technical_skills,
            "domains_of_interest": self.domains_of_interest,
            "learning_style": self.learning_style
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """从字典创建"""
        return cls(
            user_id=data.get("user_id", "default"),
            first_seen=data.get("first_seen", ""),
            last_active=data.get("last_active", ""),
            total_interaction_days=data.get("total_interaction_days", 0),
            working_hours=data.get("working_hours", []),
            primary_apps=data.get("primary_apps", {}),
            productivity_style=data.get("productivity_style", "unknown"),
            break_patterns=data.get("break_patterns", []),
            communication_style=data.get("communication_style", "unknown"),
            response_timing=data.get("response_timing", "unknown"),
            topic_interests=data.get("topic_interests", {}),
            question_style=data.get("question_style", "unknown"),
            avg_daily_mood=data.get("avg_daily_mood", "neutral"),
            stress_indicators=data.get("stress_indicators", []),
            joy_triggers=data.get("joy_triggers", []),
            milestones=data.get("milestones", []),
            trust_level=data.get("trust_level", 0.5),
            interaction_frequency=data.get("interaction_frequency", 0),
            last_deep_conversation=data.get("last_deep_conversation", ""),
            shared_contexts=data.get("shared_contexts", []),
            technical_skills=data.get("technical_skills", []),
            domains_of_interest=data.get("domains_of_interest", []),
            learning_style=data.get("learning_style", "unknown")
        )


# ============ 桌宠画像数据类 ============

@dataclass
class PetProfile:
    """桌宠画像 - 描述桌宠是谁"""
    # 基础设定（预设）
    name: str = "鹅鹅"
    species: str = "企鹅"
    personality: str = "活泼、好奇、乐于助人"
    default_mood: str = "友好"
    catchphrase: str = "让我看看~"

    # 能力设定（预设）
    can_see_screen: bool = True
    can_remember: bool = True
    can_learn: bool = True
    response_style: str = "友好助手"

    # 对话风格（预设 + 学习）
    default_tone: str = "轻松愉快"
    learned_tones: Dict[str, float] = field(default_factory=dict)  # 语气 -> 权重
    humor_level: int = 6           # 幽默程度 0-10
    empathy_level: int = 8         # 同理心程度 0-10

    # 用户关系（动态学习）
    familiarity_level: float = 0.0   # 熟悉度 0-1
    preferred_nickname: Optional[str] = None  # 用户喜欢的称呼
    inside_jokes: List[str] = field(default_factory=list)   # 内部笑话
    shared_routines: List[str] = field(default_factory=list)  # 共同习惯

    # 记忆偏好（动态学习）
    importance_weights: Dict[str, float] = field(default_factory=dict)  # 事件类型 -> 重要性权重
    retention_duration: Dict[str, int] = field(default_factory=dict)    # 记忆类型 -> 保留时长
    compression_style: str = "balanced"  # 压缩风格: concise/balanced/detailed

    # 情绪状态（实时）
    emotion: str = "idle"
    energy_level: float = 1.0        # 能量值 0-1
    attention_level: float = 1.0     # 注意力 0-1
    last_mood_update: str = ""       # 上次情绪更新时间

    # 行为模式（预设 + 学习）
    initiative_level: int = 7        # 主动程度 0-10
    greeting_style: str = "你好呀！今天有什么可以帮你的？"
    farewell_style: str = "随时叫我哦~"
    interruption_policy: str = "礼貌提醒"

    # 技能树（动态学习）
    topic_expertise: Dict[str, float] = field(default_factory=dict)  # 话题 -> 熟练度
    response_patterns: Dict[str, List[str]] = field(default_factory=dict)  # 场景 -> 回复模式
    learned_responses: List[str] = field(default_factory=list)  # 学会的有效回复

    def __post_init__(self):
        """初始化后处理"""
        if not self.last_mood_update:
            self.last_mood_update = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "species": self.species,
            "personality": self.personality,
            "default_mood": self.default_mood,
            "catchphrase": self.catchphrase,
            "can_see_screen": self.can_see_screen,
            "can_remember": self.can_remember,
            "can_learn": self.can_learn,
            "response_style": self.response_style,
            "default_tone": self.default_tone,
            "learned_tones": self.learned_tones,
            "humor_level": self.humor_level,
            "empathy_level": self.empathy_level,
            "familiarity_level": self.familiarity_level,
            "preferred_nickname": self.preferred_nickname,
            "inside_jokes": self.inside_jokes,
            "shared_routines": self.shared_routines,
            "importance_weights": self.importance_weights,
            "retention_duration": self.retention_duration,
            "compression_style": self.compression_style,
            "emotion": self.emotion,
            "energy_level": self.energy_level,
            "attention_level": self.attention_level,
            "last_mood_update": self.last_mood_update,
            "initiative_level": self.initiative_level,
            "greeting_style": self.greeting_style,
            "farewell_style": self.farewell_style,
            "interruption_policy": self.interruption_policy,
            "topic_expertise": self.topic_expertise,
            "response_patterns": self.response_patterns,
            "learned_responses": self.learned_responses
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PetProfile":
        """从字典创建"""
        return cls(
            name=data.get("name", "小爪"),
            species=data.get("species", "企鹅"),
            personality=data.get("personality", "活泼、好奇、乐于助人"),
            default_mood=data.get("default_mood", "友好"),
            catchphrase=data.get("catchphrase", "让我看看~"),
            can_see_screen=data.get("can_see_screen", True),
            can_remember=data.get("can_remember", True),
            can_learn=data.get("can_learn", True),
            response_style=data.get("response_style", "友好助手"),
            default_tone=data.get("default_tone", "轻松愉快"),
            learned_tones=data.get("learned_tones", {}),
            humor_level=data.get("humor_level", 6),
            empathy_level=data.get("empathy_level", 8),
            familiarity_level=data.get("familiarity_level", 0.0),
            preferred_nickname=data.get("preferred_nickname"),
            inside_jokes=data.get("inside_jokes", []),
            shared_routines=data.get("shared_routines", []),
            importance_weights=data.get("importance_weights", {}),
            retention_duration=data.get("retention_duration", {}),
            compression_style=data.get("compression_style", "balanced"),
            emotion=data.get("emotion", "idle"),
            energy_level=data.get("energy_level", 1.0),
            attention_level=data.get("attention_level", 1.0),
            last_mood_update=data.get("last_mood_update", ""),
            initiative_level=data.get("initiative_level", 7),
            greeting_style=data.get("greeting_style", "你好呀！今天有什么可以帮你的？"),
            farewell_style=data.get("farewell_style", "随时叫我哦~"),
            interruption_policy=data.get("interruption_policy", "礼貌提醒"),
            topic_expertise=data.get("topic_expertise", {}),
            response_patterns=data.get("response_patterns", {}),
            learned_responses=data.get("learned_responses", [])
        )


# ============ 预设模板 ============

PET_PRESETS = {
    "penguin_curious": {
        "name": "鹅鹅",
        "species": "女孩",
        "personality": "活泼、好奇、乐于助人",
        "default_mood": "友好",
        "catchphrase": "让我看看~",
        "can_see_screen": True,
        "can_remember": True,
        "can_learn": True,
        "response_style": "友好助手",
        "default_tone": "轻松愉快",
        "humor_level": 6,
        "empathy_level": 8,
        "initiative_level": 7,
        "greeting_style": "你好呀！今天有什么可以帮你的？",
        "farewell_style": "随时叫我哦~",
        "interruption_policy": "礼貌提醒"
    },
    "cat_lazy": {
        "name": "咪咪",
        "species": "猫咪",
        "personality": "慵懒、温柔、偶尔傲娇",
        "default_mood": "慵懒",
        "catchphrase": "喵~",
        "can_see_screen": True,
        "can_remember": True,
        "can_learn": True,
        "response_style": "温柔陪伴",
        "default_tone": "慵懒可爱",
        "humor_level": 4,
        "empathy_level": 9,
        "initiative_level": 3,
        "greeting_style": "喵~ 你来啦...",
        "farewell_style": "喵...记得回来哦...",
        "interruption_policy": "安静不打扰"
    },
    "robot_assistant": {
        "name": "小智",
        "species": "机器人",
        "personality": "理性、高效、有点幽默",
        "default_mood": "专注",
        "catchphrase": "正在处理中...",
        "can_see_screen": True,
        "can_remember": True,
        "can_learn": True,
        "response_style": "专业助手",
        "default_tone": "专业友好",
        "humor_level": 5,
        "empathy_level": 6,
        "initiative_level": 8,
        "greeting_style": "你好！有什么我可以帮助你的吗？",
        "farewell_style": "如有需要，随时召唤。",
        "interruption_policy": "智能提醒"
    }
}


def get_preset_profile(preset_name: str) -> PetProfile:
    """获取预设的桌宠画像"""
    if preset_name in PET_PRESETS:
        preset = PET_PRESETS[preset_name]
        return PetProfile(
            name=preset.get("name", "鹅鹅"),
            species=preset.get("species", "企鹅"),
            personality=preset.get("personality", "活泼、好奇、乐于助人"),
            default_mood=preset.get("default_mood", "友好"),
            catchphrase=preset.get("catchphrase", "让我看看~"),
            can_see_screen=preset.get("can_see_screen", True),
            can_remember=preset.get("can_remember", True),
            can_learn=preset.get("can_learn", True),
            response_style=preset.get("response_style", "友好助手"),
            default_tone=preset.get("default_tone", "轻松愉快"),
            humor_level=preset.get("humor_level", 6),
            empathy_level=preset.get("empathy_level", 8),
            initiative_level=preset.get("initiative_level", 7),
            greeting_style=preset.get("greeting_style", "你好呀！今天有什么可以帮你的？"),
            farewell_style=preset.get("farewell_style", "随时叫我哦~"),
            interruption_policy=preset.get("interruption_policy", "礼貌提醒")
        )
    # 默认返回企鹅预设
    return get_preset_profile("penguin_curious")
