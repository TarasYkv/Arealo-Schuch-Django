
import modal

app = modal.App("video-studio-ltx-prod-a100-40")
vol = modal.Volume.from_name("ltx-video-weights", create_if_missing=True)
MODEL_DIR = "/models"

image = (
    modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12")
    .apt_install("ffmpeg", "procps")
    .pip_install(
        "torch==2.7.0", "diffusers>=0.34.0", "transformers>=4.50.0",
        "accelerate>=1.4.0", "sentencepiece>=0.2.0", "pillow>=11.1.0",
        "imageio>=2.37.0", "imageio-ffmpeg>=0.6.0", "huggingface_hub>=0.29.0",
        "av>=14.0.0", "ftfy>=6.2.0",
    )
    .env({"HF_HOME": MODEL_DIR, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
)

CLS_CFG = dict(image=image, gpu="A100", volumes={MODEL_DIR: vol}, timeout=3600, scaledown_window=30, max_containers=1)


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
    return [(np.clip(np.array(f), 0, 1) * 255).astype(np.uint8) if np.array(f).dtype != np.uint8 else np.array(f) for f in frames]


@app.cls(**CLS_CFG)
class LTX2Distilled:
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers.pipelines.ltx2 import LTX2ImageToVideoPipeline
        self.pipe = LTX2ImageToVideoPipeline.from_pretrained("rootonchair/LTX-2-19b-distilled", torch_dtype=torch.bfloat16)
        self.pipe.to('cuda')
        self.pipe.vae.enable_tiling()

    @modal.method()
    def generate_video(self, **kw):
        import torch
        from PIL import Image
        from io import BytesIO
        from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES
        start_image_bytes = kw.get("start_image_bytes")
        prompt = kw.get("prompt", "")
        fps = kw.get("fps", 24)
        seed = kw.get("seed", 42)
        test_mode = kw.get("test_mode", False)
        width, height = 768, 512
        num_frames = 17 if test_mode else 121
        generator = torch.Generator("cuda").manual_seed(seed)
        img = None
        if start_image_bytes:
            img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
        full_prompt = prompt.strip() if prompt.strip() else "Smooth cinematic video"
        neg = negative_prompt or "shaky, glitchy, low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, fused fingers, bad anatomy, ugly, static"
        result = self.pipe(image=img, prompt=full_prompt,
            negative_prompt=neg,
            width=width, height=height, num_frames=num_frames, frame_rate=float(fps),
            num_inference_steps=8, sigmas=DISTILLED_SIGMA_VALUES,
            guidance_scale=1.0, generator=generator, output_type="np")
        return to_mp4(result.frames[0], fps)

@app.cls(**CLS_CFG)
class LTX2Full:
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers.pipelines.ltx2 import LTX2ConditionPipeline
        self.pipe = LTX2ConditionPipeline.from_pretrained("Lightricks/LTX-2", torch_dtype=torch.bfloat16)
        self.pipe.to('cuda')
        self.pipe.vae.enable_tiling()

    @modal.method()
    def generate_video(self, **kw):
        import torch
        from PIL import Image
        from io import BytesIO
        from diffusers.pipelines.ltx2.pipeline_ltx2_condition import LTX2VideoCondition
        start_image_bytes = kw.get("start_image_bytes")
        end_image_bytes = kw.get("end_image_bytes")
        prompt = kw.get("prompt", "")
        fps = kw.get("fps", 24)
        seed = kw.get("seed", 42)
        num_steps = kw.get("num_steps", 40)
        guidance_scale = kw.get("guidance_scale", 4.0)
        negative_prompt = kw.get("negative_prompt", "")
        test_mode = kw.get("test_mode", False)
        width, height = 768, 512
        num_frames = 17 if test_mode else 121
        generator = torch.Generator("cuda").manual_seed(seed)
        conditions = []
        if start_image_bytes:
            img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
            conditions.append(LTX2VideoCondition(frames=img, index=0, strength=1.0))
        if end_image_bytes:
            img = Image.open(BytesIO(end_image_bytes)).convert("RGB").resize((width, height), Image.LANCZOS)
            conditions.append(LTX2VideoCondition(frames=img, index=-1, strength=1.0))
        full_prompt = prompt.strip() if prompt.strip() else "Smooth cinematic video"
        neg = negative_prompt or "shaky, glitchy, low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, fused fingers, bad anatomy, ugly, transition, static"
        result = self.pipe(conditions=conditions or None, prompt=full_prompt,
            negative_prompt=neg, width=width, height=height, num_frames=num_frames,
            frame_rate=float(fps), num_inference_steps=num_steps,
            guidance_scale=guidance_scale, generator=generator, output_type="np")
        return to_mp4(result.frames[0], fps)

@app.cls(**CLS_CFG)
class CogVideoX:
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers import CogVideoXImageToVideoPipeline
        self.pipe = CogVideoXImageToVideoPipeline.from_pretrained("THUDM/CogVideoX1.5-5B-I2V", torch_dtype=torch.bfloat16)
        self.pipe.to('cuda')
        self.pipe.vae.enable_slicing()
        self.pipe.vae.enable_tiling()

    @modal.method()
    def generate_video(self, **kw):
        import torch
        from PIL import Image
        from io import BytesIO
        start_image_bytes = kw.get("start_image_bytes")
        if not start_image_bytes:
            raise ValueError("CogVideoX requires a start image")
        prompt = kw.get("prompt", "")
        seed = kw.get("seed", 42)
        test_mode = kw.get("test_mode", False)
        num_steps = kw.get("num_steps", 50)
        guidance_scale = kw.get("guidance_scale", 6.0)
        img = Image.open(BytesIO(start_image_bytes)).convert("RGB").resize((768, 512))
        full_prompt = prompt.strip() if prompt.strip() else "Smooth cinematic video"
        generator = torch.Generator("cuda").manual_seed(seed)
        num_frames = 17 if test_mode else 81
        video = self.pipe(image=img, prompt=full_prompt, num_videos_per_prompt=1,
            num_inference_steps=num_steps, num_frames=num_frames,
            guidance_scale=guidance_scale, generator=generator, output_type="np").frames[0]
        return to_mp4(frames_to_np(video), 16)

@app.cls(**CLS_CFG)
class WanFLF2V:
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers import WanImageToVideoPipeline
        self.pipe = WanImageToVideoPipeline.from_pretrained("Wan-AI/Wan2.2-I2V-A14B-Diffusers", torch_dtype=torch.bfloat16)
        self.pipe.to('cuda')

    @modal.method()
    def generate_video(self, **kw):
        import torch, numpy as np
        from PIL import Image
        from io import BytesIO
        start_image_bytes = kw.get("start_image_bytes")
        end_image_bytes = kw.get("end_image_bytes")
        prompt = kw.get("prompt", "")
        fps = kw.get("fps", 24)
        test_mode = kw.get("test_mode", False)
        aspect_ratio = kw.get("aspect_ratio", "auto")
        guidance_scale = kw.get("guidance_scale", 5.0)
        num_steps = kw.get("num_steps", 30)
        seed = kw.get("seed", 42)
        negative_prompt = kw.get("negative_prompt", "")
        max_area = 480 * 832
        max_dim = 832
        num_frames = 17 if test_mode else 81
        inference_steps = 8 if test_mode else num_steps
        full_prompt = prompt.strip() if prompt.strip() else "Smooth cinematic video"
        neg = negative_prompt or "Bright tones, overexposed, static, worst quality, low quality, deformed, still picture"
        ar_map = {"16:9": (480, 832), "9:16": (832, 480), "1:1": (640, 640)}
        if aspect_ratio in ar_map:
            height, width = ar_map[aspect_ratio]
        else:
            height, width = 480, 832
        first_frame = None
        if start_image_bytes:
            first_frame = Image.open(BytesIO(start_image_bytes)).convert("RGB")
            ar_v = first_frame.height / first_frame.width
            mv = self.pipe.vae_scale_factor_spatial * self.pipe.transformer.config.patch_size[1]
            height = round(np.sqrt(max_area * ar_v)) // mv * mv
            width = round(np.sqrt(max_area / ar_v)) // mv * mv
            if height > max_dim: height = max_dim // mv * mv
            if width > max_dim: width = max_dim // mv * mv
            first_frame = first_frame.resize((width, height), Image.LANCZOS)
        last_frame = None
        if end_image_bytes:
            last_frame = Image.open(BytesIO(end_image_bytes)).convert("RGB")
            rr = max(width / last_frame.width, height / last_frame.height)
            nw, nh = round(last_frame.width * rr), round(last_frame.height * rr)
            last_frame = last_frame.resize((nw, nh), Image.LANCZOS)
            l, t = (nw - width) // 2, (nh - height) // 2
            last_frame = last_frame.crop((l, t, l + width, t + height))
        generator = torch.Generator("cuda").manual_seed(seed)
        output = self.pipe(prompt=full_prompt, negative_prompt=neg, image=first_frame,
            last_image=last_frame, height=height, width=width, num_frames=num_frames,
            num_inference_steps=inference_steps, guidance_scale=guidance_scale, generator=generator)
        return to_mp4(frames_to_np(output.frames[0]), fps)



@app.cls(**CLS_CFG)
class HunyuanVideoI2V:
    @modal.enter()
    def load_model(self):
        import torch
        from diffusers import HunyuanVideoImageToVideoPipeline, HunyuanVideoTransformer3DModel
        model_id = "hunyuanvideo-community/HunyuanVideo-I2V"
        transformer = HunyuanVideoTransformer3DModel.from_pretrained(
            model_id, subfolder="transformer", torch_dtype=torch.bfloat16
        )
        self.pipe = HunyuanVideoImageToVideoPipeline.from_pretrained(
            model_id, transformer=transformer, torch_dtype=torch.bfloat16
        )
        self.pipe.vae.enable_tiling()
        self.pipe.to('cuda')

    @modal.method()
    def generate_video(self, **kw):
        import torch
        from PIL import Image
        from io import BytesIO
        import numpy as np
        start_image_bytes = kw.get("start_image_bytes")
        prompt = kw.get("prompt", "")
        fps = kw.get("fps", 15)
        seed = kw.get("seed", 42)
        num_steps = kw.get("num_steps", 30)
        guidance_scale = kw.get("guidance_scale", 6.0)
        test_mode = kw.get("test_mode", False)
        num_frames = 33 if test_mode else 33
        generator = torch.Generator("cuda").manual_seed(seed)
        if start_image_bytes:
            img = Image.open(BytesIO(start_image_bytes)).convert("RGB")
        else:
            img = Image.new("RGB", (768, 512), (128, 128, 128))
        full_prompt = prompt.strip() if prompt.strip() else "A smooth cinematic video"
        result = self.pipe(image=img, prompt=full_prompt,
            num_frames=num_frames, num_inference_steps=num_steps,
            guidance_scale=guidance_scale, generator=generator)
        frames = result.frames[0]
        return to_mp4(np.array(frames) if not isinstance(frames[0], np.ndarray) else frames, fps)
