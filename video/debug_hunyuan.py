import modal

app = modal.App("debug-hunyuan")

@app.function(
    image=modal.Image.debian_slim()
    .apt_install("ffmpeg", "libgl1-mesa-glx", "libglib2.0-0")
    .pip_install(
        "torch", "torchvision", "diffusers>=0.32.1", "transformers", "accelerate",
        "sentencepiece", "opencv-python", "imageio", "imageio-ffmpeg"
    ),
    gpu="a100",
    timeout=600,
)
def debug_hunyuan():
    import torch
    from diffusers import HunyuanVideoImageToVideoPipeline, HunyuanVideoTransformer3DModel
    import diffusers
    
    print(f"Diffusers version: {diffusers.__version__}")
    
    # Test basic tokenizer
    model_id = "hunyuanvideo-community/HunyuanVideo-I2V"
    
    try:
        # Load model
        transformer = HunyuanVideoTransformer3DModel.from_pretrained(
            model_id, subfolder="transformer", torch_dtype=torch.bfloat16
        )
        pipe = HunyuanVideoImageToVideoPipeline.from_pretrained(
            model_id, transformer=transformer, torch_dtype=torch.float16
        )
        print("Model loaded successfully")
        
        # Test prompt encoding
        test_prompts = [
            "A video",
            "A beautiful video",
            "A beautiful cinematic video with smooth motion",
            "A beautiful, high-quality video showcasing smooth and natural motion. The scene features cinematic lighting with detailed textures and realistic movement patterns throughout the sequence."
        ]
        
        for i, prompt in enumerate(test_prompts):
            print(f"\nTesting prompt {i+1}: '{prompt[:50]}...'" if len(prompt) > 50 else f"\nTesting prompt {i+1}: '{prompt}'")
            print(f"Prompt length: {len(prompt)} chars")
            
            try:
                # Try encoding
                prompt_embeds, pooled_prompt_embeds, prompt_attention_mask = pipe.encode_prompt(
                    prompt=prompt,
                    device="cuda",
                    num_videos_per_prompt=1,
                    do_classifier_free_guidance=True
                )
                print(f"✓ Encoding successful!")
                print(f"  - prompt_embeds shape: {prompt_embeds.shape}")
                print(f"  - pooled_prompt_embeds shape: {pooled_prompt_embeds.shape}")
                print(f"  - prompt_attention_mask shape: {prompt_attention_mask.shape}")
                
            except Exception as e:
                print(f"✗ Encoding failed: {e}")
                print(f"  Error type: {type(e).__name__}")
                
                # Try to debug the tokenizer
                try:
                    tokenizer = pipe.tokenizer
                    text_inputs = tokenizer(prompt, return_tensors="pt")
                    print(f"  Tokenizer output: {text_inputs.input_ids.shape}")
                    print(f"  Token IDs: {text_inputs.input_ids[0][:10].tolist()}...")
                except Exception as tok_e:
                    print(f"  Tokenizer error: {tok_e}")
        
        return "Debug complete"
        
    except Exception as e:
        return f"Failed to load model: {e}"

if __name__ == "__main__":
    with app.run():
        result = debug_hunyuan.remote()
        print(result)
