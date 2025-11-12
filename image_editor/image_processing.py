"""
Erweiterte Bildverarbeitung für den Image Editor
Implementiert alle fortgeschrittenen Bildbearbeitungsfunktionen
"""

import io
import base64
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw
from PIL.ExifTags import TAGS
import tempfile
import os
import subprocess
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import time

# Optional dependencies with fallbacks
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    cv2 = None

try:
    import rembg
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False
    rembg = None


class ImageProcessor:
    """Hauptklasse für erweiterte Bildverarbeitung"""
    
    def __init__(self, image_path_or_object):
        """Initialisiert den Prozessor mit einem Bild"""
        if hasattr(image_path_or_object, 'read'):
            # Django ImageField
            self.original_image = Image.open(image_path_or_object)
        elif isinstance(image_path_or_object, str):
            # Dateipfad
            self.original_image = Image.open(image_path_or_object)
        else:
            # PIL Image
            self.original_image = image_path_or_object
        
        # Konvertiere zu RGB falls notwendig
        if self.original_image.mode != 'RGB':
            self.original_image = self.original_image.convert('RGB')
        
        self.current_image = self.original_image.copy()
        self.processing_history = []
    
    def invert(self):
        """Invertiert die Farben des Bildes"""
        try:
            if self.current_image.mode == 'RGBA':
                # Für RGBA, invertiere nur RGB-Kanäle
                r, g, b, a = self.current_image.split()
                rgb_inverted = ImageOps.invert(Image.merge('RGB', (r, g, b)))
                r_inv, g_inv, b_inv = rgb_inverted.split()
                self.current_image = Image.merge('RGBA', (r_inv, g_inv, b_inv, a))
            else:
                self.current_image = ImageOps.invert(self.current_image.convert('RGB'))
            
            self._add_to_history('invert', {})
            return True, "Farben erfolgreich invertiert"
        except Exception as e:
            return False, f"Fehler beim Invertieren: {str(e)}"
    
    def convert_to_grayscale(self):
        """Konvertiert das Bild zu Graustufen"""
        try:
            self.current_image = ImageOps.grayscale(self.current_image)
            # Konvertiere zurück zu RGB für Konsistenz
            self.current_image = self.current_image.convert('RGB')
            self._add_to_history('grayscale', {})
            return True, "Erfolgreich zu Graustufen konvertiert"
        except Exception as e:
            return False, f"Fehler bei Graustufen-Konvertierung: {str(e)}"
    
    def adjust_brightness(self, factor=1.0):
        """Passt die Helligkeit des Bildes an"""
        try:
            enhancer = ImageEnhance.Brightness(self.current_image)
            self.current_image = enhancer.enhance(factor)
            self._add_to_history('brightness', {'factor': factor})
            return True, f"Helligkeit angepasst (Faktor: {factor})"
        except Exception as e:
            return False, f"Fehler bei Helligkeitsanpassung: {str(e)}"
    
    def adjust_contrast(self, factor=1.0):
        """Passt den Kontrast des Bildes an"""
        try:
            enhancer = ImageEnhance.Contrast(self.current_image)
            self.current_image = enhancer.enhance(factor)
            self._add_to_history('contrast', {'factor': factor})
            return True, f"Kontrast angepasst (Faktor: {factor})"
        except Exception as e:
            return False, f"Fehler bei Kontrastanpassung: {str(e)}"
    
    def adjust_saturation(self, factor=1.0):
        """Passt die Sättigung des Bildes an"""
        try:
            enhancer = ImageEnhance.Color(self.current_image)
            self.current_image = enhancer.enhance(factor)
            self._add_to_history('saturation', {'factor': factor})
            return True, f"Sättigung angepasst (Faktor: {factor})"
        except Exception as e:
            return False, f"Fehler bei Sättigungsanpassung: {str(e)}"
    
    def remove_background(self, model='u2net'):
        """
        Entfernt den Hintergrund mit rembg
        model: 'u2net', 'silueta', 'isnet-general-use'
        """
        if HAS_REMBG:
            try:
                # Konvertiere PIL zu Bytes
                img_bytes = io.BytesIO()
                self.current_image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                # Hintergrund entfernen
                try:
                    # Versuche neue rembg API
                    from rembg import remove
                    output = remove(img_bytes.getvalue(), model_name=model)
                except TypeError:
                    # Fallback für ältere rembg Versionen
                    from rembg import remove
                    output = remove(img_bytes.getvalue())
                
                # Zurück zu PIL konvertieren
                result_image = Image.open(io.BytesIO(output))
                
                self.current_image = result_image
                self._add_to_history('remove_background', {'model': model})
                
                return True, "Hintergrund erfolgreich entfernt (rembg)"
                
            except Exception as e:
                return False, f"Fehler bei Hintergrundentfernung: {str(e)}"
        else:
            # Fallback: Einfache Bildbearbeitung ohne OpenCV
            return self._remove_background_simple()
    
    def _remove_background_simple(self):
        """Einfache Hintergrundentfernung ohne OpenCV (Fallback)"""
        try:
            if HAS_OPENCV:
                # OpenCV-basierte Methode
                cv_image = cv2.cvtColor(np.array(self.current_image), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                
                kernel = np.ones((3,3), np.uint8)
                mask = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    mask = np.zeros(gray.shape, np.uint8)
                    cv2.fillPoly(mask, [largest_contour], 255)
                    
                    result = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGBA)
                    result[:, :, 3] = mask
                    
                    self.current_image = Image.fromarray(result, 'RGBA')
                    self._add_to_history('remove_background', {'method': 'opencv_edge_detection'})
                    
                    return True, "Hintergrund entfernt (OpenCV-Methode)"
                else:
                    return False, "Konnte kein Hauptobjekt erkennen"
            else:
                # Fallback ohne OpenCV: Einfache PIL-basierte Methode
                return self._remove_background_pil_only()
                
        except Exception as e:
            return False, f"Fehler bei Hintergrundentfernung: {str(e)}"
    
    def _remove_background_pil_only(self):
        """Sehr einfache Hintergrundentfernung nur mit PIL"""
        try:
            # Konvertiere zu Graustufen für Kantendetection
            gray = self.current_image.convert('L')
            
            # Einfache Kantenerkennung mit PIL
            edges = gray.filter(ImageFilter.FIND_EDGES)
            
            # Threshold anwenden
            threshold = 30
            edges = edges.point(lambda x: 255 if x > threshold else 0, mode='1')
            
            # Als Alpha-Maske verwenden
            rgba_image = self.current_image.convert('RGBA')
            
            # Einfache Maske erstellen: Bereiche mit Kanten beibehalten
            mask = edges.convert('L')
            
            # Maske erweitern (Dilatation simulieren)
            for i in range(3):
                mask = mask.filter(ImageFilter.MaxFilter(3))
            
            # Alpha-Kanal setzen
            rgba_image.putalpha(mask)
            
            self.current_image = rgba_image
            self._add_to_history('remove_background', {'method': 'pil_edge_detection'})
            
            return True, "Hintergrund entfernt (vereinfachte PIL-Methode)"
            
        except Exception as e:
            return False, f"Fehler bei PIL-Hintergrundentfernung: {str(e)}"
    
    def prepare_for_engraving(self, beam_width=0.1, line_thickness=0.1, depth_levels=5):
        """
        Bereitet das Bild für Laser-Gravur vor
        beam_width: Laserstrahl-Breite in mm
        line_thickness: Mindest-Linienstärke in mm
        depth_levels: Anzahl der Tiefenstufen
        """
        try:
            # Konvertiere zu Graustufen
            if self.current_image.mode != 'L':
                gray_image = self.current_image.convert('L')
            else:
                gray_image = self.current_image.copy()
            
            # Konvertiere zu NumPy Array
            img_array = np.array(gray_image)
            
            # Quantisierung auf gewünschte Tiefenstufen
            levels = np.linspace(0, 255, depth_levels + 1)
            quantized = np.digitize(img_array, levels) - 1
            quantized = quantized * (255 // (depth_levels - 1))
            quantized = np.clip(quantized, 0, 255).astype(np.uint8)
            
            if HAS_OPENCV:
                # Kantenverstärkung für bessere Gravur-Ergebnisse
                kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
                sharpened = cv2.filter2D(quantized, -1, kernel)
                
                # Minimale Linienstärke sicherstellen
                # Berechne Pixel pro mm (angenommen 300 DPI)
                dpi = 300
                pixels_per_mm = dpi / 25.4
                min_line_pixels = max(1, int(line_thickness * pixels_per_mm))
                
                # Morphologische Operationen um dünne Linien zu verstärken
                kernel = np.ones((min_line_pixels, min_line_pixels), np.uint8)
                enhanced = cv2.morphologyEx(sharpened, cv2.MORPH_CLOSE, kernel)
                
                result_image = Image.fromarray(enhanced, 'L')
                method = "OpenCV-Verarbeitung"
            else:
                # Fallback: Einfache PIL-basierte Kantenverstärkung
                pil_image = Image.fromarray(quantized, 'L')
                
                # Einfache Kantenverstärkung mit PIL
                enhanced = pil_image.filter(ImageFilter.SHARPEN)
                
                # Mehrfache Anwendung für stärkere Wirkung
                for _ in range(2):
                    enhanced = enhanced.filter(ImageFilter.EDGE_ENHANCE_MORE)
                
                result_image = enhanced
                method = "PIL-Fallback"
            
            # Zurück zu PIL
            self.current_image = result_image
            
            self._add_to_history('prepare_engraving', {
                'beam_width': beam_width,
                'line_thickness': line_thickness,
                'depth_levels': depth_levels,
                'method': method
            })
            
            return True, f"Bild für Gravur vorbereitet ({depth_levels} Tiefenstufen, {method})"
            
        except Exception as e:
            return False, f"Fehler bei Gravur-Vorbereitung: {str(e)}"
    
    def vectorize_for_engraving(self, threshold=128, simplify_tolerance=1.0):
        """
        Konvertiert das Bild in Vektorgrafiken für Gravur
        threshold: Schwellwert für Schwarz/Weiß-Konvertierung
        simplify_tolerance: Vereinfachungstoleranz für Pfade
        """
        try:
            # Konvertiere zu Schwarz/Weiß
            if self.current_image.mode != 'L':
                gray_image = self.current_image.convert('L')
            else:
                gray_image = self.current_image.copy()
            
            # Schwellwert anwenden
            threshold_image = gray_image.point(lambda x: 255 if x > threshold else 0, mode='1')
            
            # Temporäre Dateien für potrace erstellen
            with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as temp_bmp:
                threshold_image.save(temp_bmp.name, 'BMP')
                temp_bmp_path = temp_bmp.name
            
            try:
                # Versuche potrace zu verwenden (falls installiert)
                temp_svg_path = temp_bmp_path.replace('.bmp', '.svg')
                
                cmd = [
                    'potrace',
                    '--svg',
                    '--turdsize', '2',  # Unterdrücke kleine Speckles
                    '--alphamax', str(simplify_tolerance),
                    '--output', temp_svg_path,
                    temp_bmp_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(temp_svg_path):
                    # SVG-Datei lesen
                    with open(temp_svg_path, 'r') as f:
                        svg_content = f.read()
                    
                    # Aufräumen
                    os.unlink(temp_svg_path)
                    
                    self._add_to_history('vectorize', {
                        'threshold': threshold,
                        'simplify_tolerance': simplify_tolerance,
                        'method': 'potrace'
                    })
                    
                    return True, "Erfolgreich vektorisiert", svg_content
                else:
                    raise Exception("Potrace fehlgeschlagen")
                    
            except (FileNotFoundError, Exception):
                # Fallback: OpenCV-basierte Konturerkennung
                return self._vectorize_with_opencv(threshold_image, threshold, simplify_tolerance)
            
            finally:
                # Temporäre Datei aufräumen
                if os.path.exists(temp_bmp_path):
                    os.unlink(temp_bmp_path)
                    
        except Exception as e:
            return False, f"Fehler bei Vektorisierung: {str(e)}", None
    
    def _vectorize_with_opencv(self, threshold_image, threshold, simplify_tolerance):
        """Fallback-Vektorisierung mit OpenCV oder PIL"""
        try:
            if HAS_OPENCV:
                # OpenCV-basierte Vektorisierung
                cv_image = np.array(threshold_image)
                
                # Finde Konturen
                contours, _ = cv2.findContours(cv_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Generiere einfache SVG
                height, width = cv_image.shape
                svg_paths = []
                
                for contour in contours:
                    # Vereinfache Kontur
                    epsilon = simplify_tolerance * cv2.arcLength(contour, True)
                    simplified = cv2.approxPolyDP(contour, epsilon, True)
                    
                    if len(simplified) >= 3:  # Mindestens ein Dreieck
                        path_data = f"M {simplified[0][0][0]} {simplified[0][0][1]}"
                        for point in simplified[1:]:
                            path_data += f" L {point[0][0]} {point[0][1]}"
                        path_data += " Z"
                        svg_paths.append(path_data)
                
                svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
{"".join([f'<path d="{path}" fill="black" stroke="black" stroke-width="1"/>' for path in svg_paths])}
</svg>'''
                
                self._add_to_history('vectorize', {
                    'threshold': threshold,
                    'simplify_tolerance': simplify_tolerance,
                    'method': 'opencv_contours',
                    'contours_found': len(contours)
                })
                
                return True, f"Vektorisiert mit OpenCV ({len(contours)} Konturen)", svg_content
            else:
                # PIL-only Fallback: Einfache rechteckige Approximation
                return self._vectorize_with_pil_only(threshold_image, threshold, simplify_tolerance)
            
        except Exception as e:
            return False, f"Fehler bei Vektorisierung: {str(e)}", None
    
    def _vectorize_with_pil_only(self, threshold_image, threshold, simplify_tolerance):
        """Sehr einfache Vektorisierung nur mit PIL"""
        try:
            # Konvertiere zu Array
            img_array = np.array(threshold_image)
            height, width = img_array.shape
            
            # Einfache Rechteck-Approximation: Finde zusammenhängende schwarze Bereiche
            svg_paths = []
            visited = np.zeros_like(img_array, dtype=bool)
            
            for y in range(0, height, 10):  # Reduzierte Auflösung für Performance
                for x in range(0, width, 10):
                    if img_array[y, x] == 0 and not visited[y, x]:  # Schwarzer Pixel
                        # Finde Rechteck um diesen Bereich
                        min_x, max_x = x, min(x + 20, width)
                        min_y, max_y = y, min(y + 20, height)
                        
                        # Markiere als besucht
                        visited[min_y:max_y, min_x:max_x] = True
                        
                        # Erstelle Rechteck-Pfad
                        path_data = f"M {min_x} {min_y} L {max_x} {min_y} L {max_x} {max_y} L {min_x} {max_y} Z"
                        svg_paths.append(path_data)
            
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
{"".join([f'<path d="{path}" fill="black" stroke="black" stroke-width="1"/>' for path in svg_paths])}
</svg>'''
            
            self._add_to_history('vectorize', {
                'threshold': threshold,
                'simplify_tolerance': simplify_tolerance,
                'method': 'pil_rectangles',
                'rectangles_found': len(svg_paths)
            })
            
            return True, f"Vektorisiert mit PIL-Fallback ({len(svg_paths)} Rechtecke)", svg_content
            
        except Exception as e:
            return False, f"Fehler bei PIL-Vektorisierung: {str(e)}", None
    
    def enhance_lines_for_engraving(self, line_width=2, enhancement_factor=1.5):
        """
        Verstärkt Linien für bessere Sichtbarkeit bei der Gravur
        """
        try:
            # Konvertiere zu Graustufen falls notwendig
            if self.current_image.mode != 'L':
                gray_image = self.current_image.convert('L')
            else:
                gray_image = self.current_image.copy()
            
            if HAS_OPENCV:
                # OpenCV-basierte Linienverstärkung
                img_array = np.array(gray_image)
                
                # Kantenerkennung
                edges = cv2.Canny(img_array, 50, 150)
                
                # Linien verstärken
                kernel = np.ones((line_width, line_width), np.uint8)
                thick_edges = cv2.dilate(edges, kernel, iterations=1)
                
                # Kombiniere mit Original
                enhanced = cv2.addWeighted(img_array, 1.0, thick_edges, enhancement_factor, 0)
                enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
                
                result_image = Image.fromarray(enhanced, 'L')
                method = "OpenCV-Kantenverstärkung"
            else:
                # PIL-only Fallback
                # Einfache Kantenerkennung mit PIL
                edges = gray_image.filter(ImageFilter.FIND_EDGES)
                
                # Verstärke die Kanten (ensure minimum size 3)
                filter_size = max(3, line_width)
                enhanced_edges = edges.filter(ImageFilter.MaxFilter(filter_size))
                
                # Kombiniere mit Original (einfaches Alpha-Blending)
                img_array = np.array(gray_image).astype(np.float32)
                edges_array = np.array(enhanced_edges).astype(np.float32)
                
                # Einfache Gewichtung
                combined = img_array + (edges_array * enhancement_factor)
                combined = np.clip(combined, 0, 255).astype(np.uint8)
                
                result_image = Image.fromarray(combined, 'L')
                method = "PIL-Kantenverstärkung"
            
            self.current_image = result_image
            
            self._add_to_history('enhance_lines', {
                'line_width': line_width,
                'enhancement_factor': enhancement_factor,
                'method': method
            })
            
            return True, f"Linien erfolgreich verstärkt ({method})"
            
        except Exception as e:
            return False, f"Fehler bei Linienverstärkung: {str(e)}"
    
    def apply_advanced_filter(self, filter_type, **kwargs):
        """Erweiterte Filter anwenden"""
        try:
            if filter_type == 'emboss':
                return self._apply_emboss_filter(**kwargs)
            elif filter_type == 'edge_detect':
                return self._apply_edge_detection(**kwargs)
            elif filter_type == 'oil_painting':
                return self._apply_oil_painting_filter(**kwargs)
            elif filter_type == 'pencil_sketch':
                return self._apply_pencil_sketch(**kwargs)
            elif filter_type == 'vintage':
                return self._apply_vintage_filter(**kwargs)
            else:
                return False, f"Unbekannter Filter: {filter_type}"
                
        except Exception as e:
            return False, f"Fehler bei Filter '{filter_type}': {str(e)}"
    
    def _apply_emboss_filter(self, strength=1.0):
        """Präge-Effekt"""
        if HAS_OPENCV:
            # OpenCV-basierte Implementierung
            kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]]) * strength
            img_array = np.array(self.current_image)
            
            if len(img_array.shape) == 3:
                result = np.zeros_like(img_array)
                for i in range(3):
                    result[:,:,i] = cv2.filter2D(img_array[:,:,i], -1, kernel)
            else:
                result = cv2.filter2D(img_array, -1, kernel)
            
            result = np.clip(result + 128, 0, 255).astype(np.uint8)
            self.current_image = Image.fromarray(result)
            method = "OpenCV"
        else:
            # PIL-only Fallback: Verwende EMBOSS Filter von PIL
            result = self.current_image.filter(ImageFilter.EMBOSS)
            
            # Verstärke den Effekt basierend auf der Stärke
            if strength != 1.0:
                enhancer = ImageEnhance.Contrast(result)
                result = enhancer.enhance(strength)
            
            self.current_image = result
            method = "PIL-Fallback"
        
        self._add_to_history('emboss', {'strength': strength, 'method': method})
        return True, f"Präge-Effekt angewendet ({method})"
    
    def _apply_edge_detection(self, method='canny', low_threshold=50, high_threshold=150):
        """Kantenerkennung"""
        if HAS_OPENCV:
            # OpenCV-basierte Kantenerkennung
            gray = cv2.cvtColor(np.array(self.current_image), cv2.COLOR_RGB2GRAY)
            
            if method == 'canny':
                edges = cv2.Canny(gray, low_threshold, high_threshold)
            elif method == 'sobel':
                sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                edges = np.sqrt(sobelx**2 + sobely**2)
                edges = np.clip(edges, 0, 255).astype(np.uint8)
            
            result = Image.fromarray(edges, 'L')
            opencv_method = method
        else:
            # PIL-only Fallback
            gray = self.current_image.convert('L')
            edges = gray.filter(ImageFilter.FIND_EDGES)
            result = edges
            opencv_method = "pil_edges"
        
        self.current_image = result
        self._add_to_history('edge_detect', {'method': opencv_method})
        return True, f"Kantenerkennung ({opencv_method}) angewendet"
    
    def _apply_oil_painting_filter(self, size=7, levels=8):
        """Ölgemälde-Effekt"""
        if HAS_OPENCV:
            # OpenCV-basierte Implementierung
            img_array = np.array(self.current_image)
            # Vereinfachter Ölgemälde-Effekt mit Bilateral Filter
            result = cv2.bilateralFilter(img_array, size, 80, 80)
            
            # Quantisierung für Ölgemälde-Look
            result = result // (256 // levels) * (256 // levels)
            
            self.current_image = Image.fromarray(result)
            method = "OpenCV-Bilateral"
        else:
            # PIL-only Fallback: Kombination aus Blur und Quantisierung
            # Weichzeichnen für den Ölgemälde-Look
            blurred = self.current_image.filter(ImageFilter.GaussianBlur(radius=size//2))
            
            # Quantisierung
            img_array = np.array(blurred)
            quantized = img_array // (256 // levels) * (256 // levels)
            
            self.current_image = Image.fromarray(quantized.astype(np.uint8))
            method = "PIL-Fallback"
        
        self._add_to_history('oil_painting', {'size': size, 'levels': levels, 'method': method})
        return True, f"Ölgemälde-Effekt angewendet ({method})"
    
    def _apply_pencil_sketch(self, line_size=7, blur_value=7):
        """Bleistiftskizze-Effekt"""
        if HAS_OPENCV:
            # OpenCV-basierte Implementierung
            img_array = np.array(self.current_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Invertieren
            gray_inv = 255 - gray
            
            # Weichzeichnen
            gray_inv_blur = cv2.GaussianBlur(gray_inv, (blur_value, blur_value), 0)
            
            # Dodge-Blend
            sketch = cv2.divide(gray, 255 - gray_inv_blur, scale=256)
            
            result = Image.fromarray(sketch, 'L')
            method = "OpenCV-Dodge"
        else:
            # PIL-only Fallback
            gray = self.current_image.convert('L')
            
            # Invertieren
            img_array = np.array(gray)
            gray_inv = 255 - img_array
            
            # Weichzeichnen mit PIL
            gray_inv_img = Image.fromarray(gray_inv, 'L')
            gray_inv_blur = gray_inv_img.filter(ImageFilter.GaussianBlur(radius=blur_value//2))
            
            # Vereinfachtes Dodge-Blending
            gray_array = np.array(gray).astype(np.float32)
            blur_array = np.array(gray_inv_blur).astype(np.float32)
            
            # Vermeide Division durch Null
            blur_array = np.maximum(blur_array, 1)
            sketch = (gray_array / (255 - blur_array + 1)) * 255
            sketch = np.clip(sketch, 0, 255).astype(np.uint8)
            
            result = Image.fromarray(sketch, 'L')
            method = "PIL-Fallback"
        
        self.current_image = result
        self._add_to_history('pencil_sketch', {'line_size': line_size, 'blur_value': blur_value, 'method': method})
        return True, f"Bleistiftskizze-Effekt angewendet ({method})"
    
    def _apply_vintage_filter(self, sepia_strength=0.8, vignette_strength=0.3):
        """Vintage/Sepia-Effekt"""
        img_array = np.array(self.current_image).astype(np.float64)
        
        # Sepia-Transformation
        sepia_kernel = np.array([[0.393, 0.769, 0.189],
                                [0.349, 0.686, 0.168],
                                [0.272, 0.534, 0.131]])
        
        sepia_img = img_array @ sepia_kernel.T
        sepia_img = np.clip(sepia_img, 0, 255)
        
        # Mische mit Original basierend auf Stärke
        result = (1 - sepia_strength) * img_array + sepia_strength * sepia_img
        
        # Vignette hinzufügen
        h, w = result.shape[:2]
        Y, X = np.ogrid[:h, :w]
        center_x, center_y = w // 2, h // 2
        dist_from_center = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        vignette = 1 - vignette_strength * (dist_from_center / max_dist)**2
        
        if len(result.shape) == 3:
            vignette = vignette[:, :, np.newaxis]
        
        result = result * vignette
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        self.current_image = Image.fromarray(result)
        self._add_to_history('vintage', {'sepia_strength': sepia_strength, 'vignette_strength': vignette_strength})
        return True, "Vintage-Effekt angewendet"
    
    def get_current_image_base64(self):
        """Gibt das aktuelle Bild als Base64-String zurück für Vorschau"""
        buffer = io.BytesIO()
        self.current_image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def save_to_file(self, format='PNG', quality=95, **kwargs):
        """Speichert das bearbeitete Bild in eine temporäre Datei"""
        buffer = io.BytesIO()
        
        save_kwargs = {'format': format}
        if format.upper() == 'JPEG':
            save_kwargs['quality'] = quality
            # JPEG unterstützt keine Transparenz
            if self.current_image.mode in ('RGBA', 'LA'):
                # Füge weißen Hintergrund hinzu
                white_bg = Image.new('RGB', self.current_image.size, (255, 255, 255))
                white_bg.paste(self.current_image, mask=self.current_image.split()[-1] if self.current_image.mode == 'RGBA' else None)
                self.current_image = white_bg
                save_kwargs['format'] = 'JPEG'
        
        save_kwargs.update(kwargs)
        self.current_image.save(buffer, **save_kwargs)
        
        return ContentFile(buffer.getvalue())
    
    def _add_to_history(self, operation, parameters):
        """Fügt einen Schritt zur Verarbeitungshistorie hinzu"""
        self.processing_history.append({
            'operation': operation,
            'parameters': parameters,
            'timestamp': time.time()
        })
    
    def get_processing_history(self):
        """Gibt die komplette Verarbeitungshistorie zurück"""
        return self.processing_history.copy()
    
    def apply_dithering(self, method='floyd-steinberg', threshold=127):
        """
        Wendet Dithering auf das Bild an für bessere S/W-Konvertierung

        Args:
            method: Dithering-Algorithmus ('floyd-steinberg', 'simple')
            threshold: Schwellwert für S/W-Konvertierung (0-255)

        Returns:
            tuple: (success, message)
        """
        try:
            # Konvertiere zu Graustufen falls notwendig
            if self.current_image.mode != 'L':
                gray_image = self.current_image.convert('L')
            else:
                gray_image = self.current_image.copy()

            if method == 'floyd-steinberg':
                # Floyd-Steinberg Dithering mit NumPy
                img_array = np.array(gray_image, dtype=np.float32)
                height, width = img_array.shape

                # Durchlaufe alle Pixel
                for y in range(height):
                    for x in range(width):
                        old_pixel = img_array[y, x]
                        new_pixel = 255 if old_pixel > threshold else 0
                        img_array[y, x] = new_pixel

                        # Berechne Fehler
                        error = old_pixel - new_pixel

                        # Verteile Fehler auf Nachbarpixel (Floyd-Steinberg Matrix)
                        if x + 1 < width:
                            img_array[y, x + 1] += error * 7/16
                        if y + 1 < height:
                            if x > 0:
                                img_array[y + 1, x - 1] += error * 3/16
                            img_array[y + 1, x] += error * 5/16
                            if x + 1 < width:
                                img_array[y + 1, x + 1] += error * 1/16

                # Clip values to valid range
                img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                result_image = Image.fromarray(img_array, 'L')

            elif method == 'simple':
                # Einfaches Thresholding ohne Dithering
                img_array = np.array(gray_image)
                img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
                result_image = Image.fromarray(img_array, 'L')

            else:
                return False, f"Unbekannte Dithering-Methode: {method}"

            # Konvertiere zurück zu RGB für Konsistenz
            self.current_image = result_image.convert('RGB')

            self._add_to_history('dithering', {
                'method': method,
                'threshold': threshold
            })

            return True, f"Dithering ({method}) erfolgreich angewendet"

        except Exception as e:
            return False, f"Fehler beim Dithering: {str(e)}"

    def apply_threshold(self, threshold=127):
        """
        Wendet einen einfachen Schwellwert an (S/W ohne Dithering)

        Args:
            threshold: Schwellwert (0-255)

        Returns:
            tuple: (success, message)
        """
        try:
            # Konvertiere zu Graustufen falls notwendig
            if self.current_image.mode != 'L':
                gray_image = self.current_image.convert('L')
            else:
                gray_image = self.current_image.copy()

            # Threshold anwenden
            img_array = np.array(gray_image)
            img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
            result_image = Image.fromarray(img_array, 'L')

            # Konvertiere zurück zu RGB für Konsistenz
            self.current_image = result_image.convert('RGB')

            self._add_to_history('threshold', {'threshold': threshold})

            return True, f"Schwellwert ({threshold}) angewendet"

        except Exception as e:
            return False, f"Fehler bei Schwellwert-Anwendung: {str(e)}"

    def reset_to_original(self):
        """Setzt das Bild auf den ursprünglichen Zustand zurück"""
        self.current_image = self.original_image.copy()
        self.processing_history = []
        return True, "Bild auf ursprünglichen Zustand zurückgesetzt"