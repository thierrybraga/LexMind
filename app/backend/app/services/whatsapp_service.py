import httpx
from app.core.config import Settings
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.cliente import Cliente
from app.models.mensagem import Mensagem, RemetenteEnum

logger = logging.getLogger(__name__)

class WhatsappService:
    def __init__(self):
        self.settings = Settings()
        self.base_url = self.settings.WHATSAPP_API_URL
        self.api_key = self.settings.WHATSAPP_API_KEY
        self.instance_name = self.settings.WHATSAPP_INSTANCE_NAME
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=self.headers, json=data, timeout=30.0)
                # Evolution API returns 200/201 usually, but check status
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Erro na API WhatsApp ({endpoint}): {e.response.text}")
                # Não propagar erro para evitar crash do backend se o WhatsApp estiver offline
                return {"error": str(e), "details": e.response.text}
            except Exception as e:
                logger.error(f"Erro de conexão com WhatsApp: {e}")
                return {"error": str(e)}

    async def create_instance(self):
        """Cria a instância se não existir"""
        endpoint = "instance/create"
        data = {
            "instanceName": self.instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        return await self._request("POST", endpoint, data)

    async def get_connection_state(self):
        endpoint = f"instance/connectionState/{self.instance_name}"
        return await self._request("GET", endpoint)
    
    async def connect_instance(self):
        """Retorna o QR Code para conexão"""
        endpoint = f"instance/connect/{self.instance_name}"
        return await self._request("GET", endpoint)

    async def send_text(self, number: str, text: str):
        endpoint = f"message/sendText/{self.instance_name}"
        # Formatar número se necessário (remover caracteres especiais)
        clean_number = "".join(filter(str.isdigit, number))
        if not clean_number.startswith("55") and len(clean_number) < 12: # Check simples
            clean_number = "55" + clean_number # Assumindo Brasil se não tiver DDI
            
        data = {
            "number": clean_number,
            "options": {
                "delay": 1200,
                "presence": "composing",
                "linkPreview": False
            },
            "text": text
        }
        return await self._request("POST", endpoint, data)

    async def get_or_create_client(self, db: AsyncSession, remote_jid: str, name: str = None) -> Cliente:
        """Busca cliente pelo remote_jid (telefone) ou cria novo"""
        # remote_jid vem como '5511999999999@s.whatsapp.net', extrair apenas números
        telefone = remote_jid.split('@')[0]
        
        query = select(Cliente).where(Cliente.telefone == telefone)
        result = await db.execute(query)
        cliente = result.scalar_one_or_none()
        
        if not cliente:
            cliente = Cliente(
                nome=name or f"Cliente {telefone}",
                telefone=telefone,
                celular=telefone, # Assumindo que WhatsApp é celular
                origem="whatsapp" # Campo novo ou usar observacoes se nao existir
            )
            db.add(cliente)
            await db.commit()
            await db.refresh(cliente)
            logger.info(f"Novo cliente criado via WhatsApp: {cliente.id}")
            
        return cliente

    async def save_message(self, db: AsyncSession, cliente_id: int, content: str, sender: RemetenteEnum, whatsapp_id: str = None):
        """Salva mensagem no histórico"""
        msg = Mensagem(
            cliente_id=cliente_id,
            remetente=sender.value,
            conteudo=content,
            whatsapp_id=whatsapp_id,
            status="enviada" if sender == RemetenteEnum.IA else "recebida"
        )
        db.add(msg)
        await db.commit()
        return msg

    async def get_chat_history(self, db: AsyncSession, cliente_id: int, limit: int = 10) -> str:
        """Recupera histórico formatado para prompt"""
        query = select(Mensagem).where(Mensagem.cliente_id == cliente_id).order_by(desc(Mensagem.created_at)).limit(limit)
        result = await db.execute(query)
        msgs = result.scalars().all()
        
        history = []
        for m in reversed(msgs): # Reverter para ordem cronológica
            role = "Cliente" if m.remetente == "cliente" else "Assistente"
            history.append(f"{role}: {m.conteudo}")
            
        return "\n".join(history)

whatsapp_service = WhatsappService()