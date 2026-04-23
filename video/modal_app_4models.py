"""
Video Studio - 4 Models on Modal (H100)
Each model: max 1 container, 30s scaledown, no keep_warm
"""
import modal

app = modal.App("video-studio-ltx-prod")
vol = modal.Volume.from_name("ltx-video-weights", create_if_missing=True)
MODEL_DIR = "/models"

image = (
    modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12")
    .apt_install("ffmpeg")
    .pip_install(
        "torch==2.7.0",
        "diffusers>=0.34.0",
        "transformers>=4.50.0",
        "accelerate>=1.4.0",
        "sentencepiece>=0.2.0",
        "pillow>=11.1.0",
        "imageio>=2.37.0",
        "imageio-ffmpeg>=0.6.0",
        "huggingface_hub>=0.29.0",
        "av>=14.0.0",
        "ftfy>=6.2.0",
    )
    .env({"HF_HOME": MODEL_DIR, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
)

# All models: same GPU, 1 container max, 30s idle timeout, no keep_warm
CLS_CFG = dict(image=image, gpu="H100", volumes={MODEL_DIR: vol}, timeout=1800, scaledown_window=30, max_containers=1)


def to_mp4(frames_np, fps):
    import imageio, numpy as np
    from io import BytesIO
    buf = BytesIO()
    w = imageio.get_writer(buf, format="mp4", fps=fps, codec="libx264", quality=8)
    for f in frames_np:
        if f.dtype != np.uint8:
            f = (np.clip(f, 0, 1) * 255).astype(np.uint8)
        w.append_data(f)
    w.close()
    return buf.getvalue()


def frames_to_np(frames):
    import numpy as np
    result = []
    for f in frames:
        arr = np.array(f)
        if arr.dtype != np.uint8:
            arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        result.append(arr)
    return result


@app.cls(**CLS_CFG)
class LTX2Distilled:
    """Fast I2V - start frame only, 8 steps"""
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers.pipelines.ltx2 import LTX2ConditionPipeline
        print("[Distilled] Loading...")
        self.pipe = LTX2ConditionPipeline.from_pretrained(
            "rootonchair/LTX-2-19b-distilled", torch_dtype=torch.bfloat16,
        )
        self.pipe.enable_sequential_cpu_offload()
        self.pipe.vae.enable_tiling()
        print("[Distilled] Ready!")

    @modal.method()
    def generate_video(self, start_image_bytes=None, end_image_bytes=None,
                       prompt="", duration_sec=5, fps=24, with_audio=False, test_mode=False,
                       aspect_ratio="auto", guidance_scale=1.0, num_steps=8, seed=42,
                       negative_prompt=""):
        import torch
        from PIL import Image
        from io import BytesIO
        from diffusers.pipelines.ltx2.pipeline_ltx2_condition import LTX2VideoCondition
        from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES

        width, height = 768, 512
        generator = torch.Generator("cuda").manual_seed(seed)

        conditions = []
        if start_image_bytes:
            img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
            conditions.append(LTX2VideoCondition(frames=img, index=0, strength=1.0))

        full_prompt = prompt.strip() if prompt and prompt.strip() else "Smooth cinematic video with natural motion"
        print(f"[Distilled] 121 frames, prompt={full_prompt[:60]}")

        result = self.pipe(
            conditions=conditions or None,
            prompt=full_prompt,
            negative_prompt="worst quality, low quality, deformed",
            width=width, height=height,
            num_frames=121, frame_rate=float(fps),
            num_inference_steps=8,
            sigmas=DISTILLED_SIGMA_VALUES,
            guidance_scale=1.0,
            generator=generator,
            output_type="np",
        )
        video = to_mp4(result.frames[0], fps)
        print(f"[Distilled] {len(video)/1024/1024:.1f} MB")
        return video


@app.cls(**CLS_CFG)
class LTX2Full:
    """FLF2V with full model - 40 steps, guidance 4.0"""
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers.pipelines.ltx2 import LTX2ConditionPipeline
        print("[Full] Loading Lightricks/LTX-2...")
        self.pipe = LTX2ConditionPipeline.from_pretrained(
            "Lightricks/LTX-2", torch_dtype=torch.bfloat16,
        )
        self.pipe.enable_sequential_cpu_offload()
        self.pipe.vae.enable_tiling()
        print("[Full] Ready!")

    @modal.method()
    def generate_video(self, start_image_bytes=None, end_image_bytes=None,
                       prompt="", duration_sec=5, fps=24, with_audio=False, test_mode=False,
                       aspect_ratio="auto", guidance_scale=4.0, num_steps=40, seed=42,
                       negative_prompt=""):
        import torch
        from PIL import Image
        from io import BytesIO
        from diffusers.pipelines.ltx2.pipeline_ltx2_condition import LTX2VideoCondition

        width, height = 768, 512
        generator = torch.Generator("cuda").manual_seed(seed)

        conditions = []
        if start_image_bytes:
            img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
            conditions.append(LTX2VideoCondition(frames=img, index=0, strength=1.0))
        if end_image_bytes:
            img = Image.open(BytesIO(end_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
            conditions.append(LTX2VideoCondition(frames=img, index=-1, strength=1.0))

        full_prompt = prompt.strip() if prompt and prompt.strip() else "Smooth cinematic video with natural motion"
        neg = negative_prompt or "worst quality, low quality, deformed, static, frozen"

        print(f"[Full] 121 frames, {num_steps} steps, guidance={guidance_scale}, conditions={len(conditions)}")
        result = self.pipe(
            conditions=conditions if conditions else None,
            prompt=full_prompt,
            negative_prompt=neg,
            width=width, height=height,
            num_frames=121, frame_rate=float(fps),
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            output_type="np",
        )

        frames = result.frames[0]
        video_bytes = to_mp4(frames, fps)
        print(f"[Full] {len(video_bytes)/1024/1024:.1f} MB")
        return video_bytes


@app.cls(**CLS_CFG)
class CogVideoX:
    """CogVideoX 1.5 I2V"""
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers import CogVideoXImageToVideoPipeline
        print("[CogVideoX] Loading...")
        self.pipe = CogVideoXImageToVideoPipeline.from_pretrained(
            "THUDM/CogVideoX1.5-5B-I2V", torch_dtype=torch.bfloat16,
        )
        self.pipe.enable_sequential_cpu_offload()
        self.pipe.vae.enable_slicing()
        self.pipe.vae.enable_tiling()
        print("[CogVideoX] Ready!")

    @modal.method()
    def generate_video(self, start_image_bytes=None, end_image_bytes=None,
                       prompt="", duration_sec=5, fps=24, with_audio=False, test_mode=False,
                       aspect_ratio="auto", guidance_scale=6.0, num_steps=30, seed=42,
                       negative_prompt=""):
        import torch
        from PIL import Image
        from io import BytesIO
        import numpy as np

        if not start_image_bytes:
            raise ValueError("CogVideoX requires a start image")

        img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((768, 512))
        full_prompt = prompt.strip() if prompt and prompt.strip() else "Smooth cinematic video with natural motion"
        generator = torch.Generator("cuda").manual_seed(seed)

        print(f"[CogVideoX] 49 frames, {num_steps} steps")
        video = self.pipe(
            image=img, prompt=full_prompt,
            num_videos_per_prompt=1,
            num_inference_steps=num_steps,
            num_frames=49,
            guidance_scale=guidance_scale,
            generator=generator,
        ).frames[0]

        return to_mp4(frames_to_np(video), 16)


@app.cls(**CLS_CFG)
class WanFLF2V:
    """Wan 2.2 I2V A14B - First+Last Frame to Video"""
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers import WanImageToVideoPipeline

        model_id = "Wan-AI/Wan2.2-I2V-A14B-Diffusers"
        print("[WanFLF2V] Loading Wan 2.2...")
        self.pipe = WanImageToVideoPipeline.from_pretrained(
            model_id, torch_dtype=torch.bfloat16,
        )
        self.pipe.to("cuda")
        print("[WanFLF2V] Ready!")

    @modal.method()
    def generate_video(self, start_image_bytes=None, end_image_bytes=None,
                       prompt="", duration_sec=5, fps=24, with_audio=False, test_mode=False,
                       aspect_ratio="auto", guidance_scale=5.0, num_steps=30, seed=42,
                       negative_prompt=""):
        import torch
        import numpy as np
        from PIL import Image
        from io import BytesIO

        max_area = 480 * 832
        max_dim = 832

        if test_mode:
            num_frames = 17
            inference_steps = 8
        else:
            num_frames = 81
            inference_steps = num_steps

        full_prompt = prompt.strip() if prompt and prompt.strip() else "Smooth cinematic video with natural motion"
        neg = negative_prompt or "Bright tones, overexposed, static, blurred details, worst quality, low quality, deformed, still picture"

        ar_map = {"16:9": (480, 832), "9:16": (832, 480), "1:1": (640, 640)}
        if aspect_ratio in ar_map:
            height, width = ar_map[aspect_ratio]
        else:
            height, width = 480, 832

        first_frame = None
        if start_image_bytes:
            first_frame = Image.open(BytesIO(start_image_bytes)).convert("RGB")
            aspect_ratio_val = first_frame.height / first_frame.width
            mod_value = self.pipe.vae_scale_factor_spatial * self.pipe.transformer.config.patch_size[1]
            height = round(np.sqrt(max_area * aspect_ratio_val)) // mod_value * mod_value
            width = round(np.sqrt(max_area / aspect_ratio_val)) // mod_value * mod_value
            if height > max_dim:
                height = max_dim // mod_value * mod_value
            if width > max_dim:
                width = max_dim // mod_value * mod_value
            first_frame = first_frame.resize((width, height), Image.LANCZOS)
            print(f"[WanFLF2V] First frame: {width}x{height}")

        last_frame = None
        if end_image_bytes:
            last_frame = Image.open(BytesIO(end_image_bytes)).convert("RGB")
            resize_ratio = max(width / last_frame.width, height / last_frame.height)
            new_w = round(last_frame.width * resize_ratio)
            new_h = round(last_frame.height * resize_ratio)
            last_frame = last_frame.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - width) // 2
            top = (new_h - height) // 2
            last_frame = last_frame.crop((left, top, left + width, top + height))
            print(f"[WanFLF2V] Last frame: {last_frame.size}")

        generator = torch.Generator("cuda").manual_seed(seed)

        print(f"[WanFLF2V] {num_frames} frames, {inference_steps} steps, {width}x{height}, test={test_mode}")
        output = self.pipe(
            prompt=full_prompt,
            negative_prompt=neg,
            image=first_frame,
            last_image=last_frame,
            height=height,
            width=width,
            num_frames=num_frames,
            num_inference_steps=inference_steps,
            guidance_scale=guidance_scale,
            generator=generator,
        )

        frames = output.frames[0]
        print(f"[WanFLF2V] Generated {len(frames)} frames")
        video_bytes = to_mp4(frames_to_np(frames), fps)
        print(f"[WanFLF2V] {len(video_bytes)/1024/1024:.1f} MB")
        return video_bytes
