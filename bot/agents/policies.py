from config.settings import settings


def aplicar_politicas(plan: dict, metadata: dict) -> dict:
    steps = plan.get("steps", [])
    detail = plan.get("detail_level", "medio")
    pipeline = plan.get("pipeline", "simple")

    steps_to_add = []
    tipo = metadata.get("tipo")

    has_text_extraction = "text_extraction" in steps

    if tipo in ("pdf", "imagem"):
        if not has_text_extraction:
            steps_to_add.append("text_extraction")
            has_text_extraction = True

    if has_text_extraction and "ocr_revision" not in steps:
        steps_to_add.append("ocr_revision")

    if "translation" not in steps:
        steps_to_add.append("translation")

    if tipo == "pdf":
        densidade = metadata.get("densidade_visual", "baixa")
        texto_embutido = metadata.get("texto_embutido", False)
        if densidade in ("alta", "media") or texto_embutido:
            if "table_extraction" not in steps and "table_extraction" not in steps_to_add:
                steps_to_add.append("table_extraction")

    if steps_to_add:
        steps = steps_to_add + steps
        if pipeline == "simple":
            pipeline = "detailed"

    detail_levels = ["baixo", "medio", "alto"]
    if detail not in detail_levels:
        detail = "medio"

    return {
        "pipeline": pipeline,
        "steps": steps,
        "detail_level": detail,
        "priority": plan.get("priority", "speed"),
    }
