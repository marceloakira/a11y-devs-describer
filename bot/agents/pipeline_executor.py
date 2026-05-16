import asyncio
import time
from pathlib import Path
from typing import Callable, Coroutine

from bot.agents.descritor_visual import DescritorVisual
from bot.agents.ocr_agent import OCRAgent
from bot.agents.revisor_ocr import RevisorOCR
from bot.agents.summarizer import Summarizer
from bot.agents.tradutor import Tradutor
from bot.agents.state_manager import state_manager
from bot.utils.image_utils import compress_image
from bot.utils.logger import logger
from config.settings import settings


class PipelineExecutor:
    def __init__(self):
        self.descritor = DescritorVisual()
        self.tradutor = Tradutor()
        self.summarizer = Summarizer()
        self.ocr_agent = OCRAgent()
        self.revisor = RevisorOCR()

    async def executar(
        self,
        plan: dict,
        file_path: Path,
        metadata: dict,
        status_callback: Callable[[str], Coroutine] | None = None,
        task_id: str | None = None,
    ) -> str:
        steps = plan.get("steps", [])
        detail = plan.get("detail_level", "medio")

        logger.info(
            "Executando pipeline: {} ({} etapas, detalhe: {})",
            plan.get("pipeline", "?"),
            len(steps),
            detail,
        )

        result = await self._executar_steps(steps, file_path, metadata, detail, status_callback, task_id)
        return result

    async def _executar_steps(
        self,
        steps: list,
        file_path: Path,
        metadata: dict,
        detail: str,
        status_callback: Callable[[str], Coroutine] | None = None,
        task_id: str | None = None,
    ) -> str:
        ext = file_path.suffix.lower()
        is_pdf = ext == ".pdf"

        if ext in (".docx", ".html"):
            from bot.utils.file_parsers import extract_text_from_file
            texto_extraido = extract_text_from_file(file_path) or ""
            combined = f"**Texto extraido:**\n\n{texto_extraido}" if texto_extraido else ""
            if "translation" in steps and combined:
                if status_callback:
                    await status_callback("🌐 Traduzindo para portugues...")
                combined = await self.tradutor.executar(combined)
            return combined

        descricao_visual = ""
        texto_extraido = ""

        if "image_description" in steps:
            if task_id:
                state_manager.verificar_cancelamento(task_id)
            if status_callback:
                await status_callback("👁️ Descrevendo elementos visuais...")
            try:
                if is_pdf:
                    descricao_visual = await asyncio.wait_for(
                        self._descrever_pdf(file_path, status_callback, task_id), timeout=3600
                    )
                else:
                    descricao_visual = await asyncio.wait_for(
                        self._descrever_imagem(file_path, task_id), timeout=3600
                    )
            except asyncio.TimeoutError:
                logger.warning("Timeout na descricao visual para {}", file_path.name)
                descricao_visual = ""

        if "text_extraction" in steps:
            if task_id:
                state_manager.verificar_cancelamento(task_id)
            if status_callback:
                await status_callback("📖 Extraindo texto...")
            try:
                if is_pdf:
                    texto_extraido = await asyncio.wait_for(
                        self._extrair_texto_pdf(file_path, metadata, status_callback, task_id), timeout=600
                    )
                else:
                    texto_extraido = await asyncio.wait_for(
                        self._extrair_texto_imagem(file_path, status_callback, task_id), timeout=600
                    )
            except asyncio.TimeoutError:
                logger.warning("Timeout na extracao de texto para {}", file_path.name)
                texto_extraido = ""

        if texto_extraido and "ocr_revision" in steps and task_id:
            revisado = await self._revisar_por_pagina(task_id, status_callback)
            if revisado:
                texto_extraido = revisado

        if not descricao_visual.strip() and not texto_extraido.strip():
            return ""

        if task_id:
            state_manager.verificar_cancelamento(task_id)

        combined = self._combinar_resultados(descricao_visual, texto_extraido, metadata, steps)

        summary = ""
        if "summarize" in steps:
            if status_callback:
                await status_callback("📝 Sumarizando...")
            try:
                summary = await self.summarizer.executar(combined) or ""
            except Exception:
                logger.warning("Falha na sumarizacao para {}", file_path.name)

        if "translation" in steps and task_id and "ocr_revision" not in steps:
            translated = await asyncio.wait_for(
                self._traduzir_por_pagina(task_id, status_callback), timeout=600
            )
            if translated:
                texto_extraido = translated
                combined = self._combinar_resultados(descricao_visual, texto_extraido, metadata, steps)

        if "translation" in steps and not task_id:
            combined = await self.tradutor.executar(combined)

        if summary:
            combined = f"## Sumario\n\n{summary}\n\n---\n\n{combined}"

        return combined

    def _combinar_resultados(
        self, descricao: str, texto: str, metadata: dict, steps: list | None = None,
    ) -> str:
        parts = []
        if descricao.strip():
            parts.append(descricao.strip())
        if texto.strip():
            parts.append(f"\n---\n\n**Texto extraido:**\n{texto.strip()}")
        if not parts:
            if metadata.get("texto_embutido"):
                parts.append(metadata.get("texto_extraido", ""))
        result = "\n\n".join(parts)
        if steps and "table_extraction" in steps:
            tables = self._extrair_tabelas(metadata, result)
            if tables:
                result += f"\n\n{tables}"
        return result

    def _extrair_tabelas(self, metadata: dict, text: str) -> str:
        lines = text.splitlines()
        tables = []
        current_table = []
        for line in lines:
            stripped = line.strip()
            if stripped.count("|") >= 2:
                current_table.append(stripped)
            else:
                if len(current_table) >= 2:
                    tables.append("\n".join(current_table))
                current_table = []
        if len(current_table) >= 2:
            tables.append("\n".join(current_table))
        if tables:
            formatted = "\n\n".join(tables)
            return f"## Tabelas Extraídas\n\n{formatted}"
        return ""

    async def _descrever_pdf(self, file_path: Path, status_callback=None, task_id=None) -> str:
        import fitz

        doc = fitz.open(file_path)
        try:
            total = len(doc)
            pages_to_process = min(total, settings.max_pages)
            texts = []
            desc_start = time.monotonic()
            for i in range(pages_to_process):
                if task_id:
                    state_manager.verificar_cancelamento(task_id)
                page = doc[i]
                pix = page.get_pixmap(dpi=150)
                img_bytes = compress_image(pix.tobytes("png"))
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                if status_callback:
                    eta = ""
                    if i > 0:
                        elapsed = time.monotonic() - desc_start
                        avg = elapsed / (i + 1)
                        remaining = avg * (total - i - 1)
                        if remaining > 3:
                            eta = f" (ETA: ~{remaining:.0f}s)"
                    await status_callback(f"👁️ Descrevendo pagina {i+1} de {pages_to_process}...{eta}")
                page_text = await self.descritor.executar(img_b64, is_image=True)
                if page_text:
                    texts.append(f"--- Pagina {i + 1} ---\n{page_text}")
                logger.info("Descricao visual pagina {}/{}", i + 1, pages_to_process)
            return "\n\n".join(texts) if texts else ""
        finally:
            doc.close()

    async def _descrever_imagem(self, file_path: Path, task_id=None) -> str:
        if task_id:
            state_manager.verificar_cancelamento(task_id)
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        img_bytes = compress_image(img_bytes)
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        return await self.descritor.executar(img_b64, is_image=True)

    async def _extrair_texto_pdf(self, file_path: Path, metadata: dict, status_callback=None, task_id=None) -> str:
        import fitz

        doc = fitz.open(file_path)
        try:
            if metadata.get("texto_embutido"):
                texts = []
                for i in range(min(len(doc), settings.max_pages)):
                    page = doc[i]
                    text = page.get_text().strip()
                    if text:
                        texts.append(f"--- Pagina {i + 1} ---\n{text}")
                        if task_id:
                            from bot.services.history_service import salvar_ocr_raw
                            salvar_ocr_raw(task_id, i + 1, text)
                if texts:
                    logger.info("Texto extraido diretamente do PDF: {} chars", sum(len(t) for t in texts))
                    return "\n\n".join(texts)

            total = len(doc)
            pages_to_process = min(total, settings.max_pages)
            texts = []
            ocr_start = time.monotonic()
            for i in range(pages_to_process):
                if task_id:
                    state_manager.verificar_cancelamento(task_id)
                page = doc[i]
                pix = page.get_pixmap(dpi=300)
                img_bytes = compress_image(pix.tobytes("png"))
                if status_callback:
                    eta = ""
                    if i > 0:
                        elapsed = time.monotonic() - ocr_start
                        avg = elapsed / (i + 1)
                        remaining = avg * (total - i - 1)
                        if remaining > 3:
                            eta = f" (ETA: ~{remaining:.0f}s)"
                    await status_callback(f"📖 OCR pagina {i+1} de {pages_to_process}...{eta}")
                page_text = await self.ocr_agent.extrair_bytes(img_bytes)
                if page_text:
                    texts.append(f"--- Pagina {i + 1} ---\n{page_text}")
                    if task_id:
                        from bot.services.history_service import salvar_ocr_raw
                        salvar_ocr_raw(task_id, i + 1, page_text)
                logger.info("OCR Tesseract pagina {}/{}", i + 1, pages_to_process)
            return "\n\n".join(texts) if texts else ""
        finally:
            doc.close()

    async def _extrair_texto_imagem(self, file_path: Path, status_callback=None, task_id=None) -> str:
        if task_id:
            state_manager.verificar_cancelamento(task_id)
        if status_callback:
            await status_callback("🔍 OCR Tesseract...")
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        text = await self.ocr_agent.extrair_bytes(img_bytes)
        if text and task_id:
            from bot.services.history_service import salvar_ocr_raw
            salvar_ocr_raw(task_id, 1, text)
        return text

    async def _revisar_por_pagina(self, task_id: str, status_callback=None) -> str:
        from bot.services.history_service import listar_ocr_raw, salvar_ocr_revised

        raw_pages = listar_ocr_raw(task_id)
        if not raw_pages:
            return ""

        revised_texts = []
        total = len(raw_pages)
        rev_start = time.monotonic()
        for idx, page in enumerate(raw_pages):
            state_manager.verificar_cancelamento(task_id)
            page_num = page["page_number"]

            if status_callback:
                eta = ""
                if idx > 0:
                    elapsed = time.monotonic() - rev_start
                    avg = elapsed / (idx + 1)
                    remaining = avg * (total - idx - 1)
                    if remaining > 3:
                        eta = f" (ETA: ~{remaining:.0f}s)"
                await status_callback(f"✏️ Corrigindo OCR pagina {page_num} de {total}...{eta}")

            try:
                revisado = await self.revisor.executar(page["text"])
                if not revisado or len(revisado) <= len(page["text"]) * 0.5:
                    revisado = page["text"]
            except Exception as e:
                logger.warning("Falha revisao pg {}: {}: {}", page_num, type(e).__name__, e)
                revisado = page["text"]

            salvar_ocr_revised(task_id, page_num, revisado)
            revised_texts.append(f"--- Pagina {page_num} ---\n{revisado}")

            progress = 0.5 + ((idx + 1) / total) * 0.3
            state_manager.atualizar(task_id, progresso=progress, etapa=f"Revisao OCR pagina {page_num}")
            logger.info("OCR revisado pagina {}/{}", page_num, total)

        return "\n\n".join(revised_texts) if revised_texts else ""

    async def _traduzir_por_pagina(self, task_id: str, status_callback=None) -> str:
        from bot.services.history_service import listar_ocr_revised, listar_ocr_raw, salvar_ocr_translated

        rev_pages = {p["page_number"]: p["text"] for p in listar_ocr_revised(task_id)}
        raw_pages = listar_ocr_raw(task_id)
        if not raw_pages:
            return ""

        pages = []
        for p in raw_pages:
            texto = rev_pages.get(p["page_number"], p["text"])
            pages.append({"page_number": p["page_number"], "text": texto})

        translated_texts = []
        total = len(pages)
        trad_start = time.monotonic()
        for idx, page in enumerate(pages):
            state_manager.verificar_cancelamento(task_id)
            page_num = page["page_number"]

            if status_callback:
                eta = ""
                if idx > 0:
                    elapsed = time.monotonic() - trad_start
                    avg = elapsed / (idx + 1)
                    remaining = avg * (total - idx - 1)
                    if remaining > 3:
                        eta = f" (ETA: ~{remaining:.0f}s)"
                await status_callback(f"🌐 Traduzindo pagina {page_num} de {total}...{eta}")

            translated = await self.tradutor.executar(page["text"])
            salvar_ocr_translated(task_id, page_num, translated)
            translated_texts.append(f"--- Pagina {page_num} ---\n{translated}")

            progress = 0.8 + ((idx + 1) / total) * 0.15
            state_manager.atualizar(task_id, progresso=progress, etapa=f"Traducao pagina {page_num}")
            logger.info("Traducao pagina {}/{}", page_num, total)

        return "\n\n".join(translated_texts) if translated_texts else ""
