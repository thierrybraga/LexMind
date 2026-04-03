import requests
import os
import time

# Tenta pegar variáveis de ambiente ou usa padrões do Docker
EVOLUTION_API_URL = os.getenv("WHATSAPP_API_URL", "http://evo-api-2:8080")
INSTANCE_NAME = os.getenv("WHATSAPP_INSTANCE_NAME", "ia-juridica")
API_KEY = os.getenv("WHATSAPP_API_KEY", "429683C4C977415CAAFCCE10F7D57E11")

# URL do Webhook na rede interna do Docker
# O backend é acessível via nome do serviço 'backend' na porta 8000
WEBHOOK_URL = "http://backend:8000/api/whatsapp/webhook"

def setup_webhook():
    print(f"=== Configuração de Webhook Evolution API ===")
    print(f"Evolution URL: {EVOLUTION_API_URL}")
    print(f"Instância: {INSTANCE_NAME}")
    print(f"Target Webhook: {WEBHOOK_URL}")
    
    url = f"{EVOLUTION_API_URL}/webhook/set/{INSTANCE_NAME}"
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }
    # Ajuste para Evolution API v2: Payload deve ser aninhado em "webhook"
    payload = {
        "webhook": {
            "enabled": True,
            "url": WEBHOOK_URL,
            "byEvents": True,
            "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"],
            "http": {
                "headers": {
                    "Content-Type": "application/json"
                }
            }
        }
    }
    
    try:
        print(f"\nEnviando requisição para {url}...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            print("\n✅ Webhook configurado com sucesso!")
            print("As mensagens recebidas pelo WhatsApp agora serão enviadas para o backend.")
        else:
            print("\n❌ Falha ao configurar webhook.")
            
    except Exception as e:
        print(f"\n❌ Erro de conexão com Evolution API: {e}")
        print("DICA: Execute este script de DENTRO do container backend para acessar a rede interna.")

if __name__ == "__main__":
    setup_webhook()