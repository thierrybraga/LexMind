#!/bin/bash
# ===================================
# IA Jurídica - Setup Script
# ===================================
# 
# Este script configura o ambiente de desenvolvimento
# para o sistema IA Jurídica.
#
# Uso: ./setup.sh [dev|prod]

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções auxiliares
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════╗"
echo "║           IA JURÍDICA - SETUP             ║"
echo "║       Sistema de IA para Advocacia        ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar modo
MODE=${1:-dev}
log_info "Modo de instalação: $MODE"

# Verificar pré-requisitos
log_info "Verificando pré-requisitos..."

# Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker não encontrado. Instale o Docker primeiro."
    exit 1
fi
log_success "Docker encontrado"

# Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log_error "Docker Compose não encontrado. Instale o Docker Compose primeiro."
    exit 1
fi
log_success "Docker Compose encontrado"

# Criar diretórios necessários
log_info "Criando diretórios..."
mkdir -p app/data/uploads app/data/vectordb app/logs app/nginx/ssl
log_success "Diretórios criados"

# Criar arquivo .env se não existir
if [ ! -f app/.env ]; then
    log_info "Criando arquivo .env..."
    cp app/.env.example app/.env
    
    # Gerar SECRET_KEY aleatória
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" app/.env
    
    log_success "Arquivo .env criado com SECRET_KEY gerada"
    log_warn "Revise o arquivo .env e configure as variáveis necessárias"
else
    log_info "Arquivo .env já existe, mantendo configurações existentes"
fi

# Modo de instalação
if [ "$MODE" == "prod" ]; then
    log_info "Configurando ambiente de PRODUÇÃO..."
    
    # Verificar certificados SSL
    if [ ! -f nginx/ssl/fullchain.pem ] || [ ! -f nginx/ssl/privkey.pem ]; then
        log_warn "Certificados SSL não encontrados em nginx/ssl/"
        log_warn "Para produção, configure os certificados SSL:"
        log_warn "  - nginx/ssl/fullchain.pem"
        log_warn "  - nginx/ssl/privkey.pem"
        log_warn ""
        log_info "Você pode usar Let's Encrypt:"
        log_info "  certbot certonly --webroot -w /var/www/certbot -d seudominio.com"
    fi
    
    # Build e start com profile production
    log_info "Iniciando containers de produção..."
    docker-compose --profile production up -d --build
    
else
    log_info "Configurando ambiente de DESENVOLVIMENTO..."
    
    # Build e start apenas serviços básicos
    log_info "Iniciando containers de desenvolvimento..."
    docker-compose up -d --build
fi

# Aguardar serviços iniciarem
log_info "Aguardando serviços iniciarem..."
sleep 10

# Verificar saúde dos serviços
log_info "Verificando status dos serviços..."

# Backend
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_success "Backend FastAPI está funcionando"
else
    log_warn "Backend ainda está inicializando..."
fi

# Frontend
if curl -s http://localhost:5000 > /dev/null 2>&1; then
    log_success "Frontend Flask está funcionando"
else
    log_warn "Frontend ainda está inicializando..."
fi

# Popular dados de exemplo
if [ "$MODE" == "dev" ]; then
    log_info "Populando dados de exemplo..."
    docker exec ia-juridica-backend python app/scripts/seed_data.py 2>/dev/null || {
        log_warn "Não foi possível popular dados de exemplo (pode ser que já existam)"
    }
fi

# Resumo final
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════╗"
echo "║         INSTALAÇÃO CONCLUÍDA!             ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
log_info "URLs de acesso:"
echo "  • Frontend: http://localhost:5000"
echo "  • Backend API: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo ""
log_info "Credenciais padrão (desenvolvimento):"
echo "  • Email: admin@iajuridica.com.br"
echo "  • Senha: admin123"
echo ""
log_info "Comandos úteis:"
echo "  • Logs: docker-compose logs -f"
echo "  • Parar: docker-compose down"
echo "  • Reiniciar: docker-compose restart"
echo ""
if [ "$MODE" == "dev" ]; then
    log_warn "Este é um ambiente de DESENVOLVIMENTO."
    log_warn "NÃO use em produção sem configurar SSL e variáveis seguras!"
fi
