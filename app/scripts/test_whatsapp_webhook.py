import requests
import json
import sys

def test_webhook():
    # Usar porta 80 (Nginx) pois a 8000 não está exposta no host
    url = "http://localhost/api/whatsapp/webhook"
    
    payload = {
        "event": "messages.upsert",
        "instance": "ia-juridica",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "1234567890"
            },
            "message": {
                "conversation": "Comprei uma geladeira e ela parou de funcionar em 3 dias. A loja não quer trocar. Quais meus direitos?"
            },
            "pushName": "Teste User"
        },
        "sender": "5511999999999@s.whatsapp.net"
    }

    print(f"Enviando payload para {url}...")
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Webhook recebeu a mensagem com sucesso!")
            print("Verifique os logs do backend para ver a resposta gerada pelo LLM.")
        else:
            print("\n❌ Falha no webhook.")
            
    except Exception as e:
        print(f"\n❌ Erro ao conectar: {e}")
        print("Certifique-se que o Nginx está rodando em localhost:80")

if __name__ == "__main__":
    test_webhook()