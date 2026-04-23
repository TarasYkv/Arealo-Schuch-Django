"""
Call LTX-Video on Modal.com from Django.
Uses the deployed app 'video-studio-ltx' via Modal Client API.
"""
import modal
from django.core.files.base import ContentFile


def generate_scene_video(scene):
    """Call the deployed LTX-Video Modal function to render a scene."""
    from pathlib import Path

    start_image_bytes = None
    end_image_bytes = None

    if scene.start_frame and scene.start_frame.image:
        start_image_bytes = Path(scene.start_frame.image.path).read_bytes()
    if scene.end_frame and scene.end_frame.image:
        end_image_bytes = Path(scene.end_frame.image.path).read_bytes()

    # Call the deployed Modal function by app name + function name
    generate_fn = modal.Function.from_name("video-studio-ltx", "generate_video")
    video_bytes = generate_fn.remote(
        start_image_bytes=start_image_bytes,
        end_image_bytes=end_image_bytes,
        prompt=scene.prompt or "",
        duration_sec=scene.duration,
    )

    filename = f"scene_{scene.id}.mp4"
    scene.video_file.save(filename, ContentFile(video_bytes), save=True)

    return scene.video_file.path
