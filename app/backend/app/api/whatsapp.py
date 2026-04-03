from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.whatsapp_service import whatsapp_service
from app.core.llm import LLMEngine
from app.core.database import get_db
from app.models.mensagem import RemetenteEnum
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
llm_engine = LLMEngine()

SYSTEM_PROMPT_WHATSAPP = """
Você é a IA Jurídica, uma assistente virtual de triagem de um escritório de advocacia no WhatsApp.

SEU OBJETIVO:
Coletar informações essenciais do cliente para repassar a um advogado humano.

ETAPAS DA CONVERSA:
1. Se for a primeira mensagem, cumprimente e pergunte o nome do cliente e um breve relato do problema.
2. Se o cliente já relatou o problema, analise se há indícios de um caso jurídico (direito violado).
3. Se houver um caso, responda confirmando o entendimento e avise que está repassando para o advogado especialista.

FORMATO DE RESPOSTA (IMPORTANTE):
- Mantenha um tom profissional e empático.
- Se identificar um caso claro, inclua no final da sua resposta (invisível para o usuário, mas usado pelo sistema) a tag: [ENCAMINHAR_ADVOGADO]
- Resuma o caso no formato:
  Cliente: [Nome]
  Problema: [Resumo]
  Direito Potencial: [Direito Violado]

EXEMPLO:
"Entendi, Sr. João. Pelo seu relato, parece haver uma violação do Código de Defesa do Consumidor referente à garantia. Vou encaminhar seu caso para nosso especialista em Direito do Consumidor agora mesmo."
[ENCAMINHAR_ADVOGADO]
"""

@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Recebe eventos da Evolution API.
    """
    try:
        payload = await request.json()
        
        # Log básico para debug (ajustar nível em produção)
        event_type = payload.get("event")
        instance = payload.get("instance")
        
        # Verificar se é da nossa instância
        if instance != whatsapp_service.instance_name:
            return {"status": "ignored", "reason": "wrong instance"}

        logger.info(f"WhatsApp Webhook Event: {event_type}")
        
        if event_type == "messages.upsert":
            # Lógica para processar mensagens
            data = payload.get("data", {})
            key = data.get("key", {})
            from_me = key.get("fromMe", False)
            remote_jid = key.get("remoteJid")
            
            if not from_me and remote_jid:
                # Extrair mensagem de texto
                message_content = data.get("message", {})
                text = message_content.get("conversation") or \
                       message_content.get("extendedTextMessage", {}).get("text")
                
                if text:
                    logger.info(f"Mensagem recebida de {remote_jid}: {text}")
                    
                    # Ignorar mensagens muito curtas (exceto saudações) para evitar loop
                    if len(text.strip()) < 2:
                        return {"status": "ignored", "reason": "too short"}

                    # Enviar feedback visual (opcional, se a API suportar 'composing')
                    # await whatsapp_service.send_presence(remote_jid, "composing")

                    # 1. Identificar ou criar cliente
                    cliente = await whatsapp_service.get_or_create_client(db, remote_jid)
                    
                    # 2. Salvar mensagem do cliente
                    await whatsapp_service.save_message(
                        db, 
                        cliente_id=cliente.id, 
                        content=text, 
                        sender=RemetenteEnum.CLIENTE,
                        whatsapp_id=key.get("id")
                    )

                    try:
                        # 3. Recuperar histórico para contexto
                        historico = await whatsapp_service.get_chat_history(db, cliente.id, limit=10)
                        
                        # Gerar resposta com LLM (incluindo histórico no prompt)
                        prompt_com_historico = f"Histórico de Conversa:\n{historico}\n\nNova Mensagem do Cliente: {text}"
                        
                        resposta_llm, _ = await llm_engine._call_openai(
                            prompt=prompt_com_historico,
                            system_prompt=SYSTEM_PROMPT_WHATSAPP
                        )
                        
                        # 4. Enviar resposta
                        await whatsapp_service.send_text(remote_jid, resposta_llm)
                        logger.info(f"Resposta enviada para {remote_jid}")

                        # 5. Salvar resposta da IA
                        await whatsapp_service.save_message(
                            db,
                            cliente_id=cliente.id,
                            content=resposta_llm,
                            sender=RemetenteEnum.IA
                        )

                        # Verificar se deve encaminhar para advogado
                        if "[ENCAMINHAR_ADVOGADO]" in resposta_llm:
                            logger.info(f"!!! CASO DETECTADO - ENCAMINHANDO PARA ADVOGADO !!!")
                            logger.info(f"Cliente: {remote_jid}")
                            logger.info(f"Resumo do Caso: {resposta_llm}")
                            # Aqui futuramente pode-se adicionar lógica para notificar via email/sistema
                            
                            # Opcional: Notificar o próprio advogado no WhatsApp se houver um número configurado
                            # await whatsapp_service.send_text(ADVOCATE_NUMBER, f"Novo caso detectado:\n{resposta_llm}")
                        
                    except Exception as e:
                        logger.error(f"Erro ao gerar/enviar resposta LLM: {e}")
                        await whatsapp_service.send_text(remote_jid, "Desculpe, estou enfrentando uma instabilidade momentânea. Tente novamente em instantes.")
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Erro no webhook WhatsApp: {e}")
        # Retornar 200 para a API não ficar tentando reenviar indefinidamente se for erro de lógica
        return {"status": "error", "message": str(e)}

@router.get("/status")
async def get_status():
    return await whatsapp_service.get_connection_state()

@router.get("/connect")
async def connect():
    return await whatsapp_service.connect_instance()

@router.post("/create")
async def create_instance():
    return await whatsapp_service.create_instance()
