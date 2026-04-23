"""
ComfyUI workflow builder — v4 for current ComfyUI (April 2026).
Tested models: Wan 2.2 ✅, HunyuanVideo 1.5 ✅, LTX-Video 2B ✅, LTX-2 19B ✅
"""
import json


def build_workflow(model_choice, prompt, negative_prompt="", width=832, height=480,
                   duration=5, fps=16, seed=42, start_image=None, end_image=None, steps=None,
                   cfg=None, flow_shift=None):
    num_frames = min(duration * fps, 129)
    num_frames = max(1, num_frames)

    # Normalize old model names
    model_aliases = {"wan-flf2v": "wan-2.2", "hunyuan": "hunyuanvideo", "ltx-2-distilled": "ltx-video", "ltx-video-rp": "ltx-video", "wan-2.2-14b-rp": "wan-2.2", "hunyuanvideo-rp": "hunyuanvideo-rp"}
    model_choice = model_aliases.get(model_choice, model_choice)

    if model_choice in ("wan-2.2", "wan-2.1"):
        wf = _build_wan(prompt, negative_prompt, width, height, num_frames, seed, start_image, end_image)
    elif model_choice == "hunyuanvideo":
        wf = _build_hunyuan(prompt, negative_prompt, width, height, num_frames, seed, start_image, steps=steps, cfg=cfg)
    elif model_choice == "ltx-video":
        wf = _build_ltx(prompt, width, height, duration, seed, start_image)
    elif model_choice == "ltx-2":
        wf = _build_ltx2(prompt, width, height, duration, seed, start_image)
    elif model_choice == "wan-2.2-5b":
        wf = _build_wan_5b(prompt, negative_prompt, width, height, num_frames, seed, start_image)
    elif model_choice == "hunyuanvideo-rp":
        wf = _build_hunyuan_i2v(prompt, negative_prompt, width, height, num_frames, seed, start_image, steps=steps, cfg=cfg)
    else:
        raise ValueError(f"Unknown model: {model_choice}")

    # Override steps in KSampler/SamplerCustomAdvanced nodes if explicitly provided
    if steps is not None:
        for node_id, node in wf.items():
            ct = node.get("class_type", "")
            if ct == "KSampler" and "steps" in node.get("inputs", {}):
                node["inputs"]["steps"] = steps
            elif ct == "LTXVScheduler" and "steps" in node.get("inputs", {}):
                node["inputs"]["steps"] = steps

    return wf


def _vhs(prefix, images_ref, fps=16):
    return {"class_type": "VHS_VideoCombine", "inputs": {
        "frame_rate": fps, "loop_count": 0, "filename_prefix": prefix,
        "format": "video/h264-mp4", "save_output": True, "pingpong": False,
        "images": images_ref}}


def _build_wan(prompt, neg, w, h, nf, seed, start_image=None, end_image=None):
    # Base nodes shared by T2V and I2V
    wf = {
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": _vhs("wan_output", ["7", 0], 16),
    }

    if start_image and end_image:
        # First + Last Frame to Video
        wf["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "fp8_e4m3fn"}}
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["11"] = {"class_type": "LoadImage", "inputs": {"image": end_image}}
        wf["12"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}}
        wf["13"] = {"class_type": "CLIPVisionEncode", "inputs": {"crop": "center", "clip_vision": ["12", 0], "image": ["10", 0]}}
        wf["14"] = {"class_type": "CLIPVisionEncode", "inputs": {"crop": "center", "clip_vision": ["12", 0], "image": ["11", 0]}}
        wf["5"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": {
            "positive": ["4", 0], "negative": ["4", 0], "vae": ["3", 0],
            "width": w, "height": h, "length": nf, "batch_size": 1,
            "start_image": ["10", 0], "end_image": ["11", 0],
            "clip_vision_start_image": ["13", 0], "clip_vision_end_image": ["14", 0]}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2]}}
    elif start_image:
        # Image to Video — single high_noise model (fits 48GB without offloading)
        wf["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "fp8_e4m3fn"}}
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["12"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}}
        wf["13"] = {"class_type": "CLIPVisionEncode", "inputs": {"crop": "center", "clip_vision": ["12", 0], "image": ["10", 0]}}
        wf["5"] = {"class_type": "WanImageToVideo", "inputs": {
            "positive": ["4", 0], "negative": ["4", 0], "vae": ["3", 0],
            "width": w, "height": h, "length": nf, "batch_size": 1,
            "start_image": ["10", 0], "clip_vision_output": ["13", 0]}}
        # TeaCache for speedup
        wf["tc"] = {"class_type": "WanVideoTeaCacheKJ", "inputs": {
            "model": ["1", 0], "rel_l1_thresh": 0.275, "start_percent": 0.1,
            "end_percent": 1.0, "cache_device": "main_device", "coefficients": "i2v_720"}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2]}}
    else:
        # Text to Video — use T2V model, no image
        wf["1"] = {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "fp8_e4m3fn"}}
        wf["5"] = {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": w, "height": h, "length": nf, "batch_size": 1}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0]}}

    return wf


def _build_wan_5b(prompt, neg, w, h, nf, seed, start_image=None):
    """Wan 2.2 5B TI2V — single model for text+image to video."""
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": _vhs("wan5b_output", ["7", 0], 16),
    }

    if start_image:
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["12"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "clip_vision_h.safetensors"}}
        wf["13"] = {"class_type": "CLIPVisionEncode", "inputs": {"crop": "center", "clip_vision": ["12", 0], "image": ["10", 0]}}
        wf["5"] = {"class_type": "WanImageToVideo", "inputs": {
            "positive": ["4", 0], "negative": ["4", 0], "vae": ["3", 0],
            "width": w, "height": h, "length": nf, "batch_size": 1,
            "start_image": ["10", 0], "clip_vision_output": ["13", 0]}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 30, "cfg": 5.0, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2]}}
    else:
        wf["5"] = {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": w, "height": h, "length": nf, "batch_size": 1}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 30, "cfg": 5.0, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0]}}

    return wf

def _build_hunyuan(prompt, neg, w, h, nf, seed, start_image=None, steps=None, cfg=None):
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "hunyuanvideo1.5_720p_t2v_fp16.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "hunyuanvideo15_vae_fp16.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps if steps else 30, "cfg": cfg if cfg is not None else 6.0, "sampler_name": "uni_pc_bh2", "scheduler": "simple", "denoise": 1.0, "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": _vhs("hunyuan_output", ["7", 0], 16),
    }
    if start_image:
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["5"] = {"class_type": "HunyuanVideo15ImageToVideo", "inputs": {"positive": ["4", 0], "negative": ["4", 0], "vae": ["3", 0], "width": w, "height": h, "length": nf, "batch_size": 1, "start_image": ["10", 0]}}
    else:
        wf["5"] = {"class_type": "EmptyHunyuanVideo15Latent", "inputs": {"width": w, "height": h, "length": nf, "batch_size": 1}}
    return wf


def _build_ltx(prompt, w, h, duration, seed, start_image=None):
    fps = 25
    num_frames = min(duration * fps, 257)  # LTX supports longer videos
    num_frames = max(1, num_frames)
    
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-video-2b-v0.9.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "ltxv"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "4": {"class_type": "LTXVConditioning", "inputs": {"positive": ["3", 0], "negative": ["3", 0], "frame_rate": fps}},
        "5": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": w, "height": h, "length": num_frames, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 20, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "ltxv_vae_4x8x8_bf16.safetensors"}},
        "9": _vhs("ltx_output", ["7", 0], fps),
    }
    if start_image:
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["11"] = {"class_type": "LTXVImgToVideo", "inputs": {
            "positive": ["3", 0], "negative": ["3", 0], "vae": ["8", 0],
            "image": ["10", 0], "width": w, "height": h, "length": num_frames,
            "batch_size": 1, "strength": 0.7}}
        wf["4"] = {"class_type": "LTXVConditioning", "inputs": {"positive": ["11", 0], "negative": ["11", 1], "frame_rate": fps}}
        wf["6"]["inputs"]["positive"] = ["4", 0]
        wf["6"]["inputs"]["negative"] = ["4", 1]
        wf["6"]["inputs"]["latent_image"] = ["11", 2]
    return wf



def _build_ltx2(prompt, w, h, duration, seed, start_image=None):
    fps = 25
    num_frames = min(duration * fps, 121)
    num_frames = max(1, num_frames)

    wf = {
        # Load LTX-2 19B model
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx-2.3-22b-distilled.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        # T5 text encoder
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "ltxv"}},
        # Encode text
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        # VAE
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "ltxv_vae_4x8x8_bf16.safetensors"}},
        # LTXVScheduler for proper sigma schedule
        "10": {"class_type": "LTXVScheduler", "inputs": {"steps": 20, "max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1}},
        # Guider (CFG)
        "11": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["3", 0], "negative": ["3", 0], "cfg": 3.0}},
        # Sampler
        "12": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        # Noise
        "13": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        # VAE Decode
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        # Video output
        "9": _vhs("ltx2_output", ["7", 0], fps),
    }

    if start_image:
        wf["14"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["5"] = {"class_type": "LTXVImgToVideo", "inputs": {
            "positive": ["3", 0], "negative": ["3", 0], "vae": ["8", 0],
            "image": ["14", 0], "width": w, "height": h, "length": num_frames,
            "batch_size": 1, "strength": 0.7}}
        # Use conditioning from I2V node
        wf["4"] = {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["5", 0], "negative": ["5", 1], "frame_rate": fps}}
        wf["11"]["inputs"]["positive"] = ["4", 0]
        wf["11"]["inputs"]["negative"] = ["4", 1]
        # Latent from I2V
        wf["6"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["13", 0], "guider": ["11", 0], "sampler": ["12", 0],
            "sigmas": ["10", 0], "latent_image": ["5", 2]}}
    else:
        wf["5"] = {"class_type": "EmptyLTXVLatentVideo", "inputs": {
            "width": w, "height": h, "length": num_frames, "batch_size": 1}}
        wf["4"] = {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["3", 0], "negative": ["3", 0], "frame_rate": fps}}
        wf["11"]["inputs"]["positive"] = ["4", 0]
        wf["11"]["inputs"]["negative"] = ["4", 1]
        wf["6"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["13", 0], "guider": ["11", 0], "sampler": ["12", 0],
            "sigmas": ["10", 0], "latent_image": ["5", 0]}}

    return wf


def _build_hunyuan_i2v(prompt, neg, w, h, nf, seed, start_image=None, steps=None, cfg=None):
    """HunyuanVideo 1.5 I2V on RunPod — FP8, mit separater Negative-Conditioning."""
    _steps = steps if steps else 20
    _cfg = cfg if cfg is not None else 6.0
    # Use caller negative if provided, otherwise default robust realistic negative
    DEFAULT_NEG = "anime, cartoon, drawing, illustration, 2d, painted, rendered, cel-shaded, low quality, blurry, distorted, deformed, warped, flickering, jitter, low contrast, oversaturated, pixelated, compression artifacts, watermark, text, logo, bad anatomy, extra limbs, mutated face, disfigured"
    user_neg = (neg or "").strip()
    neg_text = f"{DEFAULT_NEG}, {user_neg}" if user_neg else DEFAULT_NEG

    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "hunyuanvideo1.5_480p_i2v_fp8_e4m3fn.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "clip_name2": "clip_l.safetensors", "type": "hunyuan_video_15"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "hunyuanvideo15_vae_fp16.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "4b": {"class_type": "CLIPTextEncode", "inputs": {"text": neg_text, "clip": ["2", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": _vhs("hunyuan_i2v_output", ["7", 0], 16),
    }

    if start_image:
        wf["10"] = {"class_type": "LoadImage", "inputs": {"image": start_image}}
        wf["5"] = {"class_type": "HunyuanVideo15ImageToVideo", "inputs": {
            "positive": ["4", 0], "negative": ["4b", 0], "vae": ["3", 0],
            "width": w, "height": h, "length": nf, "batch_size": 1,
            "start_image": ["10", 0]}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": _steps, "cfg": _cfg, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2]}}
    else:
        wf["5"] = {"class_type": "EmptyHunyuanVideo15Latent", "inputs": {"width": w, "height": h, "length": nf, "batch_size": 1}}
        wf["6"] = {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": _steps, "cfg": _cfg, "sampler_name": "uni_pc_bh2",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["4", 0], "negative": ["4b", 0], "latent_image": ["5", 0]}}

    return wf


def get_model_info():
    return {
        "wan-2.2": {"name": "Wan 2.2", "start_frame": True, "end_frame": True, "default_steps": 20, "default_cfg": 5.0, "max_frames": 81, "render_time_s": 145, "cost_per_render": 0.03},
        "hunyuanvideo": {"name": "HunyuanVideo 1.5", "start_frame": True, "end_frame": False, "default_steps": 30, "default_cfg": 6.0, "max_frames": 81, "render_time_s": 97, "cost_per_render": 0.02},
        "ltx-2": {"name": "LTX-2 19B", "start_frame": True, "end_frame": False, "default_steps": 25, "default_cfg": 3.0, "max_frames": 257, "render_time_s": 120, "cost_per_render": 0.05},
        "wan-2.2-5b": {"name": "Wan 2.2 5B", "start_frame": True, "end_frame": False, "default_steps": 30, "default_cfg": 5.0, "max_frames": 81, "render_time_s": 300, "cost_per_render": 0.03},
        "hunyuanvideo-rp": {"name": "HunyuanVideo 1.5 I2V (RunPod)", "start_frame": True, "end_frame": False, "default_steps": 20, "default_cfg": 6.0, "max_frames": 81, "render_time_s": 200, "cost_per_render": 0.03},
        "ltx-video": {"name": "LTX-Video 2B", "start_frame": True, "end_frame": False, "default_steps": 20, "default_cfg": 3.0, "max_frames": 257, "render_time_s": 60, "cost_per_render": 0.01},
    }
