from datetime import datetime, timedelta
import uuid
import os.path
import logging

# Bibliotecas do Google (opcionais - instalar com: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)

# Caminhos dos arquivos de credenciais (relativos à raiz do projeto)
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
CREDENTIALS_FILE = os.path.join(_BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(_BASE_DIR, "token.json")


class GoogleIntegrationService:
    """
    Integração com Google Calendar e Gmail via OAuth2.

    Pré-requisitos:
    1. Instalar dependências: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
    2. Baixar credentials.json do Google Cloud Console (OAuth2 Client ID) e colocar na raiz do projeto.
    3. Na primeira execução, o método _autenticar() abrirá o navegador para autorização.
       O token gerado é salvo em token.json e reutilizado nas execuções seguintes.
    """

    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/gmail.send',
        ]
        self.creds = None
        self._autenticar()

    def _autenticar(self):
        """Autenticação OAuth2 com Google. Reutiliza token salvo se válido."""
        if not GOOGLE_LIBS_AVAILABLE:
            logger.warning(
                "Bibliotecas Google não instaladas. Google Calendar/Gmail indisponível. "
                "Instale com: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
            return

        if not os.path.exists(CREDENTIALS_FILE):
            logger.warning(
                f"Arquivo credentials.json não encontrado em {CREDENTIALS_FILE}. "
                "Baixe-o do Google Cloud Console e coloque na raiz do projeto."
            )
            return

        try:
            if os.path.exists(TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, self.SCOPES)

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                    logger.info("Token Google renovado com sucesso.")
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, self.SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    logger.info("Autenticação Google concluída via navegador.")

                with open(TOKEN_FILE, 'w') as token_file:
                    token_file.write(self.creds.to_json())
                    logger.info(f"Token salvo em {TOKEN_FILE}")

        except Exception as e:
            logger.error(f"Erro na autenticação Google: {e}")
            self.creds = None

    @property
    def _google_disponivel(self) -> bool:
        return GOOGLE_LIBS_AVAILABLE and self.creds is not None and self.creds.valid

    async def criar_evento_agenda(self, titulo: str, data_inicio: str, emails_convidados: list) -> dict:
        """
        Cria um evento no Google Calendar com link do Google Meet.

        Args:
            titulo: Título do evento.
            data_inicio: Data/hora no formato ISO 8601 (ex: "2026-03-15T14:00:00").
            emails_convidados: Lista de e-mails dos convidados.

        Returns:
            Dict com id do evento, link Meet e status.

        Raises:
            RuntimeError: Se Google não estiver configurado ou ocorrer erro na API.
        """
        if not self._google_disponivel:
            raise RuntimeError(
                "Google Calendar não está configurado. "
                "Verifique credentials.json e as dependências Google."
            )

        try:
            service = build('calendar', 'v3', credentials=self.creds)

            start_time = datetime.fromisoformat(data_inicio)
            end_time = start_time + timedelta(hours=1)

            evento = {
                'summary': titulo,
                'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/Sao_Paulo'},
                'attendees': [{'email': email} for email in emails_convidados],
                'conferenceData': {
                    'createRequest': {
                        'requestId': str(uuid.uuid4()),
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                    }
                },
            }

            event = service.events().insert(
                calendarId='primary',
                body=evento,
                conferenceDataVersion=1,
            ).execute()

            meet_link = None
            entry_points = event.get('conferenceData', {}).get('entryPoints', [])
            if entry_points:
                meet_link = entry_points[0].get('uri')

            logger.info(f"Evento Google Calendar criado: {event.get('id')} - {titulo}")

            return {
                "id": event.get('id'),
                "link": meet_link,
                "status": event.get('status', 'confirmed'),
                "html_link": event.get('htmlLink'),
            }

        except Exception as e:
            logger.error(f"Erro ao criar evento no Google Calendar: {e}")
            raise RuntimeError(f"Falha ao criar evento no Google Calendar: {e}") from e

    async def enviar_email_confirmacao(self, para: str, assunto: str, corpo: str) -> bool:
        """
        Envia e-mail via Gmail API.

        Args:
            para: Endereço de destino.
            assunto: Assunto do e-mail.
            corpo: Corpo do e-mail (texto simples).

        Returns:
            True se enviado com sucesso.

        Raises:
            RuntimeError: Se Gmail não estiver configurado ou ocorrer erro.
        """
        if not self._google_disponivel:
            raise RuntimeError(
                "Gmail não está configurado. "
                "Verifique credentials.json e as dependências Google."
            )

        try:
            import base64
            from email.mime.text import MIMEText

            service = build('gmail', 'v1', credentials=self.creds)

            mensagem = MIMEText(corpo, 'plain', 'utf-8')
            mensagem['to'] = para
            mensagem['subject'] = assunto

            raw = base64.urlsafe_b64encode(mensagem.as_bytes()).decode('utf-8')

            service.users().messages().send(
                userId='me',
                body={'raw': raw},
            ).execute()

            logger.info(f"E-mail enviado via Gmail para {para} | Assunto: {assunto}")
            return True

        except Exception as e:
            logger.error(f"Erro ao enviar e-mail via Gmail: {e}")
            raise RuntimeError(f"Falha ao enviar e-mail via Gmail: {e}") from e
