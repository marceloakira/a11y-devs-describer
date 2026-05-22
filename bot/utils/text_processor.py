import re
from bot.utils.logger import logger

def merge_broken_paragraphs(text: str) -> str:
    """
    Une parágrafos que foram quebrados entre páginas do PDF.
    - Remove hífens de quebra de linha (ex: "compara- \nção" -> "comparação").
    - Une frases que terminam sem pontuação final e continuam na linha seguinte.
    """
    # 1. Remove marcadores de página (=== Pagina X ===) para a análise de fusão
    # Mas vamos mantê-los temporariamente para saber onde as páginas mudam
    
    lines = text.split("\n")
    processed_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Se for um marcador de página, apenas pula
        if re.match(r"^=== Pagina \d+ ===$", line):
            processed_lines.append(line)
            i += 1
            continue

        # Se a linha termina com um hífen de quebra de palavra
        if line.endswith("-") and i + 1 < len(lines):
            next_line = lines[i+1].lstrip()
            # Se a próxima linha começa com letra minúscula, provavelmente é continuação
            if next_line and next_line[0].islower():
                # Remove o hífen e o espaço, une com a próxima
                line = line[:-1] + next_line
                i += 1 # Pula a próxima linha já consumida
        
        # Se a linha não termina com pontuação terminal e a próxima começa com minúscula
        elif line and line[-1] not in ".!?:;\"" and i + 1 < len(lines):
            next_line = lines[i+1].lstrip()
            if next_line and not re.match(r"^=== Pagina \d+ ===$", next_line) and next_line[0].islower():
                line = line + " " + next_line
                i += 1
                
        processed_lines.append(line)
        i += 1
        
    return "\n".join(processed_lines)

def parse_markdown_and_descriptions(text: str):
    """
    Analisa o texto em busca de descrições e estilos Markdown.
    Retorna uma lista de tuplas (tipo, conteúdo).
    Tipos: 'text', 'h1', 'h2', 'h3', 'bullet', 'number', 'description'
    """
    # Regex para extrair descrições: [DESCRIÇÃO: ...]
    desc_pattern = r"\[DESCRIÇÃO:\s*(.*?)\]"
    
    paragraphs = text.split("\n\n")
    structured_content = []
    
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        
        # Verifica se o parágrafo inteiro é uma descrição
        desc_match = re.fullmatch(desc_pattern, para, re.DOTALL | re.IGNORECASE)
        if desc_match:
            structured_content.append(('description', desc_match.group(1).strip()))
            continue
            
        # Verifica cabeçalhos
        if para.startswith("### "):
            structured_content.append(('h3', para[4:].strip()))
        elif para.startswith("## "):
            structured_content.append(('h2', para[3:].strip()))
        elif para.startswith("# "):
            structured_content.append(('h1', para[2:].strip()))
        else:
            # Processa linha a linha para detectar listas e descrições embutidas
            lines = para.split("\n")
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Descrição embutida na linha
                if re.search(desc_pattern, line, re.IGNORECASE):
                    # Divide o texto antes, a descrição, e o texto depois
                    parts = re.split(desc_pattern, line, flags=re.IGNORECASE)
                    for idx, part in enumerate(parts):
                        part = part.strip()
                        if not part: continue
                        if idx % 2 == 1: # É o grupo capturado pela regex (a descrição)
                            structured_content.append(('description', part))
                        else:
                            structured_content.append(('text', part))
                    continue

                if line.startswith(("- ", "* ")):
                    structured_content.append(('bullet', line[2:].strip()))
                elif re.match(r"^\d+\.\s", line):
                    parts = line.split(". ", 1)
                    structured_content.append(('number', parts[1].strip()))
                else:
                    structured_content.append(('text', line))
                    
    return structured_content

def apply_formatting(paragraph_obj, text, bold_font=None, italic_font=None):
    """
    Aplica negrito e itálico Markdown a um objeto de parágrafo (Word ou PDF).
    Esta é uma função genérica de auxílio.
    """
    # Padrão para **bold** e *italic*
    pattern = r"(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)"
    parts = re.split(pattern, text)
    
    return parts # Retorna as partes para o exportador lidar com o objeto específico
