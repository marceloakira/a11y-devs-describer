from bot.agents.base import BaseAgent
from config.settings import settings

REVISION_PROMPT = """\
Voce e um corretor especializado em OCR. Sua unica funcao e corrigir erros
obvios de reconhecimento optico de caracteres (OCR) no texto abaixo.

REGRAS ABSOLUTAS:
1. Corrija APENAS erros evidentes de OCR:
   - Caracteres trocados (ex: "c" por "e", "rn" por "m", "0" por "O")
   - Palavras coladas ou separadas incorretamente
   - Acentuacao do portugues (ex: "nao" -> "nao", "e" -> "e", "so" -> "so")
   - Pontuacao mal interpretada
   - Letras maiusculas/minusculas trocadas em contexto obvio
2. NUNCA mude palavras que ja estao corretas
3. NUNCA parafraseie ou reescreva frases
4. NUNCA adicione ou remova informacao
5. Preserve nomes proprios, numeros, codigos, URLs exatamente como estao
6. Preserve quebras de linha e paragrafos originais
7. Se nao houver erros, retorne o texto IDENTICO
8. NAO responda com explicacoes, apenas o texto corrigido

Texto para correcao:
{text}
"""


class RevisorOCR(BaseAgent):
    def __init__(self):
        super().__init__(
            model=settings.ocr_model,
            prompt=REVISION_PROMPT,
            temperature=0.0,
            max_tokens=8192,
            keep_alive=0,
        )

    async def executar(self, entrada: str, is_image: bool = False) -> str:
        prompt = self.prompt.format(text=entrada)
        logger_prefix = self.__class__.__name__
        try:
            result = await super().executar(prompt, is_image=False)
            if result and len(result) > len(entrada) * 0.5:
                return result
            return entrada
        except Exception:
            return entrada
