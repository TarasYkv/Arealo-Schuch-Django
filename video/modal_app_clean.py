"""
Video Studio - Wan 2.2 I2V on Modal (H100)
Wan 2.2 I2V A14B with FLF2V (start+end frame)
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


@app.cls(image=image, gpu="H100", volumes={MODEL_DIR: vol}, timeout=1800, scaledown_window=300, keep_warm=1, max_containers=1)
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
            aspect_ratio = first_frame.height / first_frame.width
            mod_value = self.pipe.vae_scale_factor_spatial * self.pipe.transformer.config.patch_size[1]
            height = round(np.sqrt(max_area * aspect_ratio)) // mod_value * mod_value
            width = round(np.sqrt(max_area / aspect_ratio)) // mod_value * mod_value
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
