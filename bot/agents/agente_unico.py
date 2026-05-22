import io
import time
from pathlib import Path
from typing import Callable, Coroutine

from PIL import Image

from config.settings import settings

if settings.ai_client == "browser":
    from bot.clients.browser_client import client as opencode_client
elif settings.ai_client == "openrouter":
    from bot.clients.openrouter import client as opencode_client
else:
    from bot.clients.opencode import client as opencode_client

from bot.services.cache import get_cached, set_cache
from bot.utils.image_converter import convert_pdf_to_png
from bot.utils.image_enhancer import enhance_image_for_ocr
from bot.utils.logger import logger
from bot.utils.pdf_splitter import split_pdf
from config.settings import settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

MODE_MAP = {
    "detalhado": "detalhado.txt",
    "medio": "medio.txt",
    "normal": "medio.txt",
    "baixo": "baixo.txt",
    "ocr": "ocr.txt",
}


def _load_system_prompt(mode: str = "medio") -> str:
    filename = MODE_MAP.get(mode, "medio.txt")
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    logger.warning("Prompt file not found at {}, falling back to medio", prompt_path)
    fallback = PROMPTS_DIR / "medio.txt"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")
    return (
        "Voce e um sistema de acessibilidade digital. Converta as imagens recebidas "
        "em texto acessivel para leitores de tela em portugues brasileiro. "
        "Descreva elementos visuais e extraia todo o texto presente."
    )


def _compress_to_jpg(image_bytes: bytes, max_width: int = None, quality: int = None) -> bytes:
    max_width = max_width or settings.max_page_width
    quality = quality or settings.jpg_quality

    img = Image.open(io.BytesIO(image_bytes))

    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        new_h = int(h * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


def _image_to_jpg(file_path: Path, tmpdir: Path) -> Path:
    with open(file_path, "rb") as f:
        img_bytes = f.read()

    jpg_bytes = _compress_to_jpg(img_bytes)
    jpg_path = tmpdir / "imagem.jpg"
    jpg_path.write_bytes(jpg_bytes)
    logger.info("Imagem convertida para JPG: {} -> {} bytes", len(img_bytes), len(jpg_bytes))
    return jpg_path


class AgenteUnico:
    """Agente unico que processa PDF/imagem pagina por pagina via OpenCode."""

    def __init__(self, mode: str = "medio"):
        self.mode = mode
        self.system_prompt = _load_system_prompt(mode)

    async def executar(
        self,
        file_path: Path,
        tmpdir: Path,
        status_callback: Callable[[str], Coroutine] | None = None,
        mode: str | None = None,
    ) -> str:
        effective_mode = mode or self.mode
        system_prompt = _load_system_prompt(effective_mode)
        ext = file_path.suffix.lower()
        is_pdf = ext == ".pdf"

        if is_pdf:
            if status_callback:
                await status_callback("📄 Separando PDF em paginas...")
            page_pdfs = split_pdf(file_path, tmpdir, settings.max_pages)
        else:
            if status_callback:
                await status_callback("🖼️ Preparando imagem...")
            page_pdfs = [file_path]

        total_pages = len(page_pdfs)
        if total_pages == 0:
            raise RuntimeError("Nenhuma pagina gerada a partir do arquivo")

        logger.info("Processando {} pagina(s) para {}", total_pages, file_path.name)

        results = []
        for i, page_path in enumerate(page_pdfs):
            page_num = i + 1
            
            # Novo: Sistema de cache por pagina para evitar re-processamento
            page_cache_key = f"page_{page_num}_{effective_mode}"
            cached_page = await get_cached(page_path, page_cache_key, ttl=86400) # Cache de 24h para paginas
            if cached_page:
                logger.info("[pag {}] Cache hit (pulando IA)", page_num)
                results.append(cached_page)
                continue

            if status_callback:
                label = f"📷 Processando pagina {page_num} de {total_pages}..."
                await status_callback(label)

            try:
                if is_pdf:
                    logger.debug("[pag {}] convert_pdf_to_png: {}", page_num, page_path)
                    png_bytes = convert_pdf_to_png(page_path, settings.pdf_split_dpi)
                    logger.debug("[pag {}] PNG gerado: {} bytes", page_num, len(png_bytes))
                else:
                    logger.debug("[pag {}] lendo imagem: {}", page_num, page_path)
                    with open(page_path, "rb") as f:
                        raw_bytes = f.read()
                    logger.debug("[pag {}] imagem lida: {} bytes", page_num, len(raw_bytes))
                    png_bytes = raw_bytes

                logger.debug("[pag {}] comprimindo para JPG...", page_num)
                jpg_bytes = _compress_to_jpg(png_bytes)
                
                # Novo: Melhoria de imagem (Contraste, Brilho, Rotação)
                logger.debug("[pag {}] aplicando melhoria de imagem (OpenCV)...", page_num)
                jpg_bytes = enhance_image_for_ocr(jpg_bytes)
                
                logger.debug("[pag {}] JPG final: {} bytes", page_num, len(jpg_bytes))

                logger.info("Enviando pagina {} para OpenRouter ({} bytes)", page_num, len(jpg_bytes))

                # Instruções avançadas para Semântica e Acessibilidade
                advanced_instructions = (
                    "\n\nREGRAS DE FORMATAÇÃO E SEMÂNTICA:\n"
                    "1. Se houver imagens, gráficos ou diagramas, forneça a audiodescrição entre colchetes assim: "
                    "'[DESCRIÇÃO: sua descrição detalhada aqui]'.\n"
                    "2. Preserve a ênfase do texto original usando Markdown: **negrito** para termos importantes e *itálico* para ênfase ou nomes estrangeiros.\n"
                    "3. Para MATEMÁTICA: linearize fórmulas simples (ex: 'a/b') e use LaTeX entre '$' para complexas (ex: '$x^2$').\n"
                    "4. Se um parágrafo termina com hífen ou parece continuar na próxima página, apenas transcreva-o; o sistema cuidará da união."
                )
                
                page_prompt = system_prompt + advanced_instructions
                if is_pdf:
                    page_prompt += f"\n\nEste e o documento de {total_pages} paginas. Voce esta processando a pagina {page_num} de {total_pages}."

                logger.debug("[pag {}] chamando opencode_client.send_message()", page_num)
                response = await opencode_client.send_message(text=page_prompt, images=[jpg_bytes])
                logger.debug("[pag {}] resposta recebida: {} chars", page_num, len(response))
                
                # Salva a pagina no cache assim que recebe a resposta
                await set_cache(page_path, response, page_cache_key)
                
            except UnicodeDecodeError as e:
                import traceback
                tb = traceback.format_exc()
                logger.critical(
                    "[pag {}] UnicodeDecodeError: {} | Traceback:\n{}",
                    page_num, e, tb
                )
                raise
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.critical(
                    "[pag {}] Erro inesperado: tipo={} | msg={} | Traceback:\n{}",
                    page_num, type(e).__name__, e, tb
                )
                raise

            if not response.strip():
                logger.warning("Resposta vazia para pagina {}", page_num)
                response = f"[Pagina {page_num}: resposta vazia do modelo]"

            output_file = tmpdir / f"imagen{page_num:03d}.txt"
            output_file.write_text(response, encoding="utf-8")
            logger.info("Resposta da pagina {} salva em {}", page_num, output_file.name)

            results.append(response)

        texto_final = "\n\n".join(
            f"=== Pagina {i + 1} ===\n{r}" for i, r in enumerate(results)
        )

        logger.info(
            "AgenteUnico: {} paginas processadas, {} chars no total",
            total_pages,
            len(texto_final),
        )

        return texto_final
