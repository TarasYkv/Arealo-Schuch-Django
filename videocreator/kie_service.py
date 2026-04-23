"""
KIE.ai Service - Simplified
 
BILDER: Getestet und funktionierend
VIDEOS: Platzhalter (Modellnamen müssen noch verifiziert werden)
"""
import requests
from typing import Optional, List, Dict, Any
import json


# ============================================================================
# IMAGE MODELS - ALLE GETESTET UND FUNKTIONIEREND
# ============================================================================
IMAGE_MODELS = {
    # === GÜNSTIG + GUT ===
    "z-image": {
        "api_model": "z-image",
        "name": "Z-Image",
        "price": "$0.004",
        "desc": "Günstigstes, gute Qualität",
        "params": ["aspect_ratio"],
        "supports_reference": False,
    },
    "grok-imagine": {
        "api_model": "grok-imagine/text-to-image",
        "name": "Grok Imagine",
        "price": "$0.02",
        "desc": "xAI, 6 Bilder/Request",
        "params": ["aspect_ratio"],
        "supports_reference": False,
    },
    "ideogram-v3": {
        "api_model": "ideogram/v3-text-to-image",
        "name": "Ideogram V3",
        "price": "$0.02",
        "desc": "Beste Text-in-Bild",
        "params": [],
        "supports_reference": False,
    },
    
    # === CHARAKTER-KONSISTENZ (Referenzbild-Upload) ===
    "flux-kontext-pro": {
        "api_model": "flux-kontext-pro",
        "endpoint": "kontext",
        "name": "Flux Kontext Pro",
        "price": "$0.025",
        "desc": "Beste Konsistenz mit Referenzbild",
        "params": ["aspect_ratio"],
        "supports_reference": True,
        "max_references": 1,
    },
    "flux-kontext-max": {
        "api_model": "flux-kontext-max",
        "endpoint": "kontext",
        "name": "Flux Kontext Max",
        "price": "$0.05",
        "desc": "Premium Konsistenz",
        "params": ["aspect_ratio"],
        "supports_reference": True,
        "max_references": 1,
    },
    "qwen-edit": {
        "api_model": "qwen/image-to-image",
        "name": "Qwen Edit",
        "price": "$0.028",
        "desc": "Bild bearbeiten mit Referenz",
        "params": ["aspect_ratio"],
        "supports_reference": True,
        "max_references": 1,
        "image_param": "image_url",
    },
    
    # === HOHE QUALITÄT ===
    "flux-pro": {
        "api_model": "flux-2/pro-text-to-image",
        "name": "Flux 2 Pro",
        "price": "$0.025",
        "desc": "Photorealistisch",
        "params": ["aspect_ratio", "resolution"],
        "supports_reference": False,
    },
    "nano-banana": {
        "api_model": "google/nano-banana",
        "name": "Nano Banana",
        "price": "$0.04",
        "desc": "Google Standard",
        "params": ["aspect_ratio"],
        "supports_reference": False,
    },
    "nano-banana-pro": {
        "api_model": "nano-banana-pro",
        "name": "Nano Banana Pro",
        "price": "$0.09",
        "desc": "Google Pro Qualität",
        "params": ["aspect_ratio", "resolution"],
        "supports_reference": False,
    },
    "imagen4": {
        "api_model": "google/imagen4",
        "name": "Imagen 4",
        "price": "Credits",
        "desc": "Google Premium",
        "params": ["aspect_ratio"],
        "supports_reference": False,
    },
    
    # === GRATIS ===
    "pollinations": {
        "api_model": "pollinations",
        "endpoint": "free",
        "name": "Pollinations",
        "price": "KOSTENLOS",
        "desc": "Gratis, langsamer",
        "params": ["aspect_ratio"],
        "supports_reference": False,
    },
}


# ============================================================================
# VIDEO MODELS - Aus Original übernommen (müssen noch verifiziert werden)
# NUR Image-to-Video Modelle
# ============================================================================
VIDEO_MODELS = {
    # Kling
    "kling-2.6-5s": {
        "api_model": "kling/2.6-i2v-5s",
        "name": "Kling 2.6 (5s)",
        "price": "$0.275",
        "desc": "Kuaishou, 5 Sekunden",
        "duration": 5,
        "supports_end_frame": False,
    },
    "kling-2.6-10s": {
        "api_model": "kling/2.6-i2v-10s", 
        "name": "Kling 2.6 (10s)",
        "price": "$0.55",
        "desc": "Kuaishou, 10 Sekunden",
        "duration": 10,
        "supports_end_frame": False,
    },
    
    # Veo (Google) - mit Audio
    "veo3-fast": {
        "api_model": "veo/3.1-fast",
        "endpoint": "veo",
        "name": "Veo 3 Fast",
        "price": "$0.40",
        "desc": "Google schnell + Audio",
        "duration": 8,
        "supports_end_frame": False,
        "has_audio": True,
    },
    "veo3-quality": {
        "api_model": "veo/3.1-quality",
        "endpoint": "veo",
        "name": "Veo 3 Quality",
        "price": "$0.80+",
        "desc": "Google Premium + Audio",
        "duration": 8,
        "supports_end_frame": False,
        "has_audio": True,
    },
    
    # Hailuo
    "hailuo-2.3": {
        "api_model": "hailuo/2.3-i2v",
        "name": "Hailuo 2.3",
        "price": "$0.20",
        "desc": "MiniMax, gute Bewegung",
        "duration": 6,
        "supports_end_frame": False,
    },
    
    # Wan
    "wan-2.6": {
        "api_model": "wan/2.6-i2v",
        "name": "Wan 2.6",
        "price": "$0.35",
        "desc": "Alibaba",
        "duration": 5,
        "supports_end_frame": True,
    },
}


class KieService:
    """KIE.ai API Service"""
    
    BASE_URL = "https://api.kie.ai"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, endpoint: str, data: dict, timeout: int = 30) -> dict:
        """Make API request"""
        try:
            response = requests.post(
                f"{self.BASE_URL}{endpoint}",
                headers=self.headers,
                json=data,
                timeout=timeout
            )
            return response.json()
        except requests.exceptions.Timeout:
            return {"code": 408, "msg": "Request timeout"}
        except Exception as e:
            return {"code": 500, "msg": str(e)}
    
    # ========================================================================
    # IMAGE GENERATION
    # ========================================================================
    def generate_image(
        self,
        prompt: str,
        model: str = "z-image",
        aspect_ratio: str = "16:9",
        resolution: str = "1K",
        image_inputs: Optional[List[str]] = None,  # For backwards compatibility
        reference_images: Optional[List[str]] = None,
        callback_url: Optional[str] = None
    ) -> dict:
        """
        Generate an image.
        
        Args:
            prompt: Text description
            model: Model ID from IMAGE_MODELS
            aspect_ratio: 1:1, 16:9, 9:16, 4:3, 3:4
            resolution: 1K, 2K, 4K (for models that support it)
            reference_images: List of image URLs for character consistency
            callback_url: Webhook for completion notification
        """
        # Merge image_inputs and reference_images for backwards compatibility
        refs = reference_images or image_inputs or []
        
        config = IMAGE_MODELS.get(model, {})
        api_model = config.get("api_model", model)
        endpoint_type = config.get("endpoint", "standard")
        
        # Free Pollinations
        if endpoint_type == "free":
            dims = {
                "16:9": (1024, 576),
                "9:16": (576, 1024),
                "1:1": (512, 512),
                "4:3": (640, 480),
                "3:4": (480, 640),
            }.get(aspect_ratio, (512, 512))
            
            import urllib.parse
            encoded_prompt = urllib.parse.quote(prompt)
            
            return {
                "code": 200,
                "msg": "success",
                "data": {
                    "taskId": f"pollinations-{hash(prompt) % 999999}",
                    "direct_url": f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={dims[0]}&height={dims[1]}&model=flux"
                }
            }
        
        # Flux Kontext - special endpoint for consistency
        if endpoint_type == "kontext":
            data = {
                "prompt": prompt,
                "model": api_model,
                "aspectRatio": aspect_ratio,
                "outputFormat": "png",
            }
            if refs:
                data["inputImage"] = refs[0]
            if callback_url:
                data["callBackUrl"] = callback_url
            return self._request("/api/v1/flux/kontext/generate", data)
        
        # Standard models
        input_data = {"prompt": prompt}
        
        # Add aspect_ratio
        if "aspect_ratio" in config.get("params", []):
            input_data["aspect_ratio"] = aspect_ratio
        
        # Add resolution
        if "resolution" in config.get("params", []):
            input_data["resolution"] = resolution
        
        # Add reference image
        if config.get("supports_reference") and refs:
            image_param = config.get("image_param", "image_url")
            input_data[image_param] = refs[0]
        
        # Output format for nano-banana
        if "nano-banana" in api_model:
            input_data["output_format"] = "png"
        
        data = {
            "model": api_model,
            "input": input_data,
        }
        
        if callback_url:
            data["callBackUrl"] = callback_url
        
        return self._request("/api/v1/jobs/createTask", data)
    
    # ========================================================================
    # VIDEO GENERATION - Image-to-Video only
    # ========================================================================
    def generate_video(
        self,
        prompt: str,
        model: str,
        image_urls: List[str],  # Start frame(s)
        end_frame_url: Optional[str] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = "16:9",
        sound: bool = False,
        callback_url: Optional[str] = None
    ) -> dict:
        """
        Generate a video from start frame.
        
        Args:
            prompt: Motion/action description
            model: Model ID from VIDEO_MODELS
            image_urls: List with start frame URL (first element used)
            end_frame_url: URL of ending image (only some models)
            duration: Video length in seconds
            aspect_ratio: 16:9, 9:16, 1:1
            callback_url: Webhook for completion notification
        """
        if not image_urls or not image_urls[0]:
            return {"code": 400, "msg": "Start frame image is required"}
        
        start_frame = image_urls[0]
        
        config = VIDEO_MODELS.get(model, {})
        api_model = config.get("api_model", model)
        endpoint_type = config.get("endpoint", "standard")
        default_duration = config.get("duration", 5)
        
        # Veo special endpoint
        if endpoint_type == "veo":
            data = {
                "model": api_model,
                "prompt": prompt,
                "image": start_frame,
                "duration": duration or default_duration,
                "aspect_ratio": aspect_ratio,
            }
            if callback_url:
                data["callBackUrl"] = callback_url
            return self._request("/api/v1/veo/generate", data)
        
        # Standard I2V models
        input_data = {
            "prompt": prompt,
            "image_url": start_frame,
            "duration": duration or default_duration,
            "aspect_ratio": aspect_ratio,
        }
        
        # Add end frame if supported
        if config.get("supports_end_frame") and end_frame_url:
            input_data["end_frame_url"] = end_frame_url
        
        data = {
            "model": api_model,
            "input": input_data,
        }
        
        if callback_url:
            data["callBackUrl"] = callback_url
        
        return self._request("/api/v1/jobs/createTask", data)
    
    # ========================================================================
    # TASK STATUS
    # ========================================================================
    def check_task(self, task_id: str, model: str = None) -> dict:
        """Check task status"""
        # Pollinations - return as completed with direct URL
        if task_id.startswith("pollinations-"):
            return {
                "code": 200,
                "data": {
                    "state": "success",
                    "resultJson": json.dumps({"resultUrls": []})
                }
            }
        
        # Veo special endpoint
        if model and "veo" in model.lower():
            response = requests.get(
                f"{self.BASE_URL}/api/v1/veo/record-info?taskId={task_id}",
                headers=self.headers,
                timeout=10
            )
            return response.json()
        
        # Standard endpoint
        response = requests.get(
            f"{self.BASE_URL}/api/v1/jobs/recordInfo?taskId={task_id}",
            headers=self.headers,
            timeout=10
        )
        return response.json()
    
    # ========================================================================
    # MODEL INFO
    # ========================================================================
    @staticmethod
    def get_image_models() -> dict:
        return IMAGE_MODELS
    
    @staticmethod
    def get_video_models() -> dict:
        return VIDEO_MODELS
    
    @staticmethod
    def get_consistency_models() -> list:
        """Models that support character consistency with reference images"""
        return [
            model_id for model_id, config in IMAGE_MODELS.items()
            if config.get("supports_reference")
        ]
    
    @staticmethod
    def get_end_frame_models() -> list:
        """Video models that support end frame"""
        return [
            model_id for model_id, config in VIDEO_MODELS.items()
            if config.get("supports_end_frame")
        ]
