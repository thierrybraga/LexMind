import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"
EMAIL = "advogado@iajuridica.com.br"
PASSWORD = "senha123"

def test_auth():
    print(f"\n--- Testing Authentication ---")
    url = f"{BASE_URL}/auth/token"
    payload = {
        "username": EMAIL,
        "password": PASSWORD
    }
    try:
        response = requests.post(url, data=payload) # OAuth2 uses form data
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ Login successful")
            return token
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def test_search(token):
    print(f"\n--- Testing Unified Search ---")
    url = f"{BASE_URL}/pesquisa/"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "query": "dano moral extravio bagagem",
        "limit": 5,
        "deep_research": False
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            results = data.get("resultados", [])
            print(f"✅ Search successful. Found {len(results)} results.")
            
            mock_found = False
            for r in results:
                print(f"  - [{r.get('fonte')}] {r.get('titulo')[:50]}...")
                if "mock" in str(r.get("id", "")).lower() or "simulado" in r.get("titulo", "").lower():
                    mock_found = True
            
            if mock_found:
                print("⚠️  WARNING: Mock results detected!")
            else:
                print("✅ No mock results detected.")
                
            return results
        else:
            print(f"❌ Search failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Search connection failed: {e}")
        return None

def test_rag(token):
    print(f"\n--- Testing RAG Direct Endpoint ---")
    url = f"{BASE_URL}/rag/search"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "query": "prisão preventiva requisitos",
        "top_k": 3
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", []) # Note: Endpoint returns 'results' inside RAGSearchResponse
            if not results and 'resultados' in data: # Fallback check
                results = data['resultados']
                
            print(f"✅ RAG Search successful. Found {len(results)} results.")
            
            mock_found = False
            for r in results:
                print(f"  - [RAG] {r.get('conteudo')[:50]}...")
                if "mock" in str(r.get("id", "")).lower() or "simulado" in str(r.get("ementa", "")).lower():
                    mock_found = True
            
            if mock_found:
                print("⚠️  WARNING: Mock results detected in RAG!")
            else:
                print("✅ No mock results detected in RAG.")
        else:
            print(f"❌ RAG Search failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ RAG connection failed: {e}")

if __name__ == "__main__":
    token = test_auth()
    if token:
        test_search(token)
        test_rag(token)