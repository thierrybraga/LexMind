import requests
import time
import sys

BASE_URL = "http://localhost:8000/api/whatsapp"

def create_instance():
    print("Criando instância 'ia-juridica'...")
    try:
        response = requests.post(f"{BASE_URL}/create")
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.json()}")
        return response.status_code == 200 or response.status_code == 201
    except Exception as e:
        print(f"Erro ao criar instância: {e}")
        return False

def get_status():
    print("\nVerificando status da conexão...")
    try:
        response = requests.get(f"{BASE_URL}/status")
        data = response.json()
        print(f"Status: {data}")
        return data
    except Exception as e:
        print(f"Erro ao verificar status: {e}")
        return None

def get_qrcode():
    print("\nObtendo QR Code para conexão...")
    try:
        response = requests.get(f"{BASE_URL}/connect")
        data = response.json()
        
        if "base64" in data:
            print("\n✅ QR Code gerado com sucesso!")
            print("Abra o navegador e cole o base64 em um visualizador ou acesse a interface do Evolution API.")
            print(f"Alternativa: Acesse http://localhost:8000/api/whatsapp/connect para ver o JSON completo.")
        elif "qrcode" in data:
             print("\n✅ QR Code gerado com sucesso!")
             print(f"QR Code: {data['qrcode']}")
        else:
            print(f"Resposta inesperada: {data}")
            
    except Exception as e:
        print(f"Erro ao obter QR Code: {e}")

if __name__ == "__main__":
    print("=== Configuração WhatsApp IA Jurídica ===")
    
    # 1. Criar Instância
    if create_instance():
        time.sleep(2) # Esperar propagação
        
        # 2. Verificar Status
        status = get_status()
        
        # 3. Se não conectado, pedir QR Code
        state = status.get("instance", {}).get("state") if status else "unknown"
        if state != "open":
            get_qrcode()
        else:
            print("\n✅ WhatsApp já está CONECTADO!")
    else:
        print("\n❌ Falha ao inicializar. Verifique se o backend e a Evolution API estão rodando.")