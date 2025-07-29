import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from django.core.files.base import ContentFile
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def generate_video_thumbnail(video_instance):
    """
    Generate thumbnail for video file.
    First tries to extract frame with ffmpeg, falls back to placeholder if unavailable.
    """
    try:
        # Try to generate thumbnail using ffmpeg
        if has_ffmpeg():
            return generate_thumbnail_with_ffmpeg(video_instance)
    except Exception as e:
        logger.warning(f"Failed to generate thumbnail with ffmpeg: {e}")
    
    # Fallback to placeholder thumbnail
    return generate_placeholder_thumbnail(video_instance)


def has_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def generate_thumbnail_with_ffmpeg(video_instance):
    """Extract thumbnail from video using ffmpeg"""
    video_path = video_instance.video_file.path
    
    # Create temporary file for thumbnail
    temp_thumbnail_path = f"/tmp/thumb_{video_instance.unique_id}.jpg"
    
    try:
        # Extract frame at 1 second mark
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01.000',
            '-vframes', '1',
            '-vf', 'scale=640:360',
            '-y',
            temp_thumbnail_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Read the generated thumbnail
        with open(temp_thumbnail_path, 'rb') as f:
            thumbnail_data = f.read()
        
        # Save to model
        video_instance.thumbnail.save(
            f"thumb_{video_instance.unique_id}.jpg",
            ContentFile(thumbnail_data),
            save=False
        )
        
        # Clean up
        os.remove(temp_thumbnail_path)
        
        return True
        
    except Exception as e:
        logger.error(f"Error generating thumbnail with ffmpeg: {e}")
        # Clean up on error
        if os.path.exists(temp_thumbnail_path):
            os.remove(temp_thumbnail_path)
        raise


def generate_placeholder_thumbnail(video_instance):
    """Generate a placeholder thumbnail with video title"""
    # Create image
    width, height = 640, 360
    background_color = (45, 45, 45)  # Dark gray
    text_color = (255, 255, 255)  # White
    
    # Create image
    img = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(img)
    
    # Draw video icon
    icon_size = 80
    icon_x = (width - icon_size) // 2
    icon_y = (height - icon_size) // 2 - 20
    
    # Draw play button triangle
    points = [
        (icon_x, icon_y),
        (icon_x, icon_y + icon_size),
        (icon_x + icon_size, icon_y + icon_size // 2)
    ]
    draw.polygon(points, fill=(100, 100, 100))
    
    # Add title text
    try:
        # Try to use a better font if available
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        # Fall back to default font
        font = ImageFont.load_default()
    
    # Truncate title if too long
    title = video_instance.title
    if len(title) > 30:
        title = title[:27] + "..."
    
    # Calculate text position
    text_bbox = draw.textbbox((0, 0), title, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (width - text_width) // 2
    text_y = icon_y + icon_size + 30
    
    # Draw text
    draw.text((text_x, text_y), title, fill=text_color, font=font)
    
    # Save to BytesIO
    output = BytesIO()
    img.save(output, format='JPEG', quality=85)
    output.seek(0)
    
    # Save to model
    video_instance.thumbnail.save(
        f"thumb_{video_instance.unique_id}.jpg",
        ContentFile(output.read()),
        save=False
    )
    
    return True


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return int(duration)
    except:
        return 0