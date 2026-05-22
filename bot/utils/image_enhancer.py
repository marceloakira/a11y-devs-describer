import cv2
import numpy as np
from PIL import Image
import io
from bot.utils.logger import logger

def enhance_image_for_ocr(image_bytes: bytes) -> bytes:
    """
    Melhora a qualidade da imagem para IA/OCR:
    1. Corrige rotação baseada em detecção de bordas/linhas.
    2. Ajusta contraste e brilho (CLAHE).
    3. Reduz ruído preservando bordas.
    """
    try:
        # Converte bytes para formato OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return image_bytes

        # 1. Redução de ruído inicial
        img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

        # 2. Conversão para escala de cinza para processamento técnico
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 3. Correção de Rotação (Deskew)
        # Usa transformada de Hough para detectar o ângulo predominante das linhas
        coords = np.column_stack(np.where(gray > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        # Ajuste do ângulo retornado pelo OpenCV
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        if abs(angle) > 0.5: # Só rotaciona se houver inclinação real
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            logger.debug("Imagem rotacionada em {:.2f} graus", angle)

        # 4. Melhoria de Contraste Adaptativa (CLAHE)
        # Converte para LAB para processar apenas a luminosidade
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        img = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        # Converte de volta para bytes (JPEG)
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()

    except Exception as e:
        logger.error("Erro no pré-processamento de imagem: {}", e)
        return image_bytes # Retorna original em caso de erro

def is_math_likely(text: str) -> bool:
    """Verifica se o texto contém padrões que sugerem fórmulas matemáticas."""
    math_indicators = ['=', '+', '-', '*', '/', '^', '√', '∫', '∑', 'π', 'θ', '²', '³', 'log', 'sin', 'cos', 'tan']
    count = sum(1 for indicator in math_indicators if indicator in text)
    return count > 2
