"""视觉模型模块"""
import base64
import requests
from io import BytesIO
from PIL import Image
from typing import Optional
from dataclasses import dataclass


@dataclass
class VisionModelConfig:
    """视觉模型配置"""
    name: str = "minicpm-v:latest"
    base_url: str = "http://localhost:11434"
    num_predict: int = 200
    temperature: float = 0.3


class VisionModel:
    """视觉模型类，调用 Ollama API 进行图像理解"""

    def __init__(self, config: VisionModelConfig):
        self.config = config
        self.api_url = f"{config.base_url}/api/generate"

    def _image_to_base64(self, image: Image.Image) -> str:
        """将 PIL Image 转换为 base64 字符串"""
        buffer = BytesIO()
        # 如果图像太大，进行缩放以提高处理速度
        max_size = 1024
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        image.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def understand(self, image: Image.Image, prompt: str = "请简要描述这张图片的内容。") -> Optional[str]:
        """
        理解图像内容

        Args:
            image: PIL Image 对象
            prompt: 提示词

        Returns:
            str: 图像描述，失败返回 None
        """
        try:
            image_base64 = self._image_to_base64(image)

            payload = {
                "model": self.config.name,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "num_predict": self.config.num_predict,
                    "temperature": self.config.temperature
                }
            }

            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "").strip()

        except requests.exceptions.Timeout:
            print("视觉模型请求超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"视觉模型请求失败: {e}")
            return None
        except Exception as e:
            print(f"视觉理解失败: {e}")
            return None

    def understand_screen(self, image: Image.Image) -> Optional[str]:
        """
        专门用于屏幕理解的接口

        Args:
            image: 屏幕截图

        Returns:
            str: 屏幕内容描述
        """
        prompt = """请描述当前屏幕上显示的内容。
关注以下几点：
1. 用户正在使用什么应用程序或软件
2. 屏幕上的主要内容和文字
3. 用户可能正在做什么操作

请用简洁的中文回答，不超过100字。"""

        return self.understand(image, prompt)

    def check_connection(self) -> bool:
        """检查与 Ollama 服务的连接"""
        try:
            response = requests.get(f"{self.config.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
