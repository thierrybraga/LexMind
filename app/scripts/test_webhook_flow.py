import requests
import json
import time
import os

# URL do Backend
# Se rodar dentro do container: http://localhost:8000
# Se rodar fora: http://localhost:8000 (assumindo porta exposta)
BACKEND_URL = "http://localhost:8000/api/whatsapp/webhook"

def test_simulation():
    print(f"=== Teste de Simulação de Webhook ===")
    print(f"Enviando mensagem falsa para: {BACKEND_URL}")
    
    # Payload simulando o formato da Evolution API v2
    payload = {
        "event": "messages.upsert",
        "instance": "ia-juridica",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST_MSG_SIMULATION_001"
            },
            "pushName": "Usuário Teste",
            "message": {
                "conversation": "Qual é o prazo para contestação trabalhista?"
            },
            "messageType": "conversation"
        }
    }
    
    try:
        start = time.time()
        response = requests.post(BACKEND_URL, json=payload)
        elapsed = time.time() - start
        
        print(f"Status: {response.status_code}")
        print(f"Tempo: {elapsed:.2f}s")
        print(f"Resposta: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Sucesso! O backend aceitou a mensagem.")
            print("Verifique os logs do backend para ver se a OpenAI respondeu.")
        else:
            print("\n❌ Erro: O backend rejeitou a mensagem ou falhou.")
            
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")

if __name__ == "__main__":
    test_simulation()
