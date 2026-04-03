"""
IA Jurídica - Frontend Flask
Aplicação web para sistema de IA jurídica brasileira
"""
import os
import requests
import io
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'ia-juridica-secret-key-dev-2024')
app.config['SESSION_TYPE'] = 'filesystem'

# Configurações
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000/api')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'odt', 'rtf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# =====================
# HELPERS
# =====================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_auth_headers():
    """Retorna headers de autenticação"""
    token = session.get('access_token')
    if token:
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    return {'Content-Type': 'application/json'}

def api_request(method, endpoint, data=None, files=None):
    """Faz requisição para a API FastAPI"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = get_auth_headers() if not files else {'Authorization': f'Bearer {session.get("access_token", "")}'}
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=data, timeout=60)
        elif method == 'POST':
            if files:
                response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=120)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data, timeout=60)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=60)
        else:
            return None, "Método não suportado"
        
        if response.status_code == 401:
            session.clear()
            return None, "Sessão expirada. Faça login novamente."
        
        if response.status_code >= 400:
            error_msg = response.json().get('detail', 'Erro na requisição')
            return None, error_msg
            
        return response.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Não foi possível conectar ao servidor. Verifique se a API está rodando."
    except requests.exceptions.Timeout:
        return None, "Tempo limite excedido. Tente novamente."
    except Exception as e:
        return None, str(e)

def login_required(f):
    """Decorator para rotas que requerem autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para rotas que requerem admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        if session.get('user_role') != 'admin':
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# =====================
# CONTEXTO GLOBAL
# =====================

@app.context_processor
def inject_globals():
    """Injeta variáveis globais em todos os templates"""
    return {
        'current_year': datetime.now().year,
        'user': session.get('user'),
        'user_role': session.get('user_role'),
        'app_name': 'IA Jurídica',
        'version': '1.0.0'
    }

# =====================
# FILTROS
# =====================

@app.template_filter('datetime')
def format_datetime(value, format='%d/%m/%Y %H:%M'):
    """Formata datetime para string"""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            # Tenta converter string ISO para datetime
            if 'T' in value:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                return value
        except ValueError:
            return value
    return value.strftime(format)

# =====================
# ROTAS PÚBLICAS
# =====================

@app.route('/')
def index():
    """Página inicial"""
    if 'access_token' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        if not email or not senha:
            flash('Preencha todos os campos.', 'danger')
            return render_template('login.html')
        
        data, error = api_request('POST', '/auth/login', {
            'email': email,
            'senha': senha
        })
        
        if error:
            flash(error, 'danger')
            return render_template('login.html')
        
        # Salvar dados na sessão
        session['access_token'] = data['access_token']
        session['user'] = data['usuario']
        session['user_role'] = data['usuario'].get('role', 'advogado')
        
        flash(f'Bem-vindo(a), {data["usuario"]["nome"]}!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout — registra na auditoria antes de limpar sessão"""
    if 'access_token' in session:
        api_request('POST', '/auth/logout')
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    """Página de registro"""
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome'),
            'email': request.form.get('email'),
            'senha': request.form.get('senha'),
            'oab': request.form.get('oab'),
            'telefone': request.form.get('telefone')
        }
        
        # Validações
        if not all([data['nome'], data['email'], data['senha']]):
            flash('Preencha os campos obrigatórios.', 'danger')
            return render_template('registro.html')
        
        if request.form.get('senha') != request.form.get('confirmar_senha'):
            flash('As senhas não coincidem.', 'danger')
            return render_template('registro.html')
        
        result, error = api_request('POST', '/auth/register', data)
        
        if error:
            flash(error, 'danger')
            return render_template('registro.html')
        
        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    """Recuperação de senha"""
    if request.method == 'POST':
        email = request.form.get('email')
        # TODO: Implementar envio de email
        flash('Se o email existir em nossa base, você receberá instruções de recuperação.', 'info')
        return redirect(url_for('login'))
    return render_template('recuperar_senha.html')

# =====================
# ROTAS AUTENTICADAS
# =====================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal"""
    return render_template('dashboard.html')

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API para buscar estatísticas do dashboard"""
    stats, _ = api_request('GET', '/audit/dashboard-stats')
    if not stats:
        stats, _ = api_request('GET', '/audit/estatisticas')
    
    return jsonify(stats or {
        'total_processos': 0,
        'total_peticoes': 0,
        'consultas_ia': 0,
        'consultas_cnj': 0,
        'atividades_recentes': [],
        'ultimas_peticoes': []
    })

# =====================
# PESQUISA RAG
# =====================

@app.route('/pesquisa', methods=['GET', 'POST'])
@login_required
def pesquisa():
    """Pesquisa jurídica RAG"""
    resultados = []
    query = ''
    
    if request.method == 'POST':
        query = request.form.get('query', '')
        tribunal = request.form.get('tribunal')
        area = request.form.get('area')
        ano_inicio = request.form.get('ano_inicio')
        ano_fim = request.form.get('ano_fim')
        
        if not query:
            flash('Digite uma pesquisa.', 'warning')
        else:
            # Mapeamento para o endpoint de Pesquisa Unificada
            data = {
                'query': query,
                'tribunal': tribunal if tribunal else None,
                'tipo': None, # O backend pode inferir ou buscar tudo
                'limit': 10,
                'fontes': None, # Todas as fontes
                # Campos extras que podem ser usados no futuro ou filtrados no backend
                # 'area_direito': area if area else None,
                # 'ano_inicio': int(ano_inicio) if ano_inicio else None,
                # 'ano_fim': int(ano_fim) if ano_fim else None,
            }
            
            # Usar o endpoint de pesquisa unificada (/pesquisa/) em vez de apenas RAG (/rag/search)
            result, error = api_request('POST', '/pesquisa/', data)
            
            if error:
                flash(error, 'danger')
            else:
                resultados = result.get('resultados', [])
                if not resultados:
                    flash('Nenhum resultado encontrado para sua pesquisa.', 'info')
    
    return render_template('pesquisa.html', 
                          resultados=resultados, 
                          query=query,
                          tribunais=['STF', 'STJ', 'TST', 'TRF1', 'TRF2', 'TRF3', 'TRF4', 'TRF5', 
                                    'TJSP', 'TJRJ', 'TJMG', 'TJRS', 'TJPR', 'TJSC'],
                          areas=['Civil', 'Penal', 'Trabalhista', 'Tributário', 'Administrativo', 
                                'Constitucional', 'Empresarial', 'Consumidor', 'Ambiental', 'Família'])

@app.route('/pesquisa/ia', methods=['POST'])
@login_required
def pesquisa_ia():
    """Consulta IA jurídica"""
    pergunta = request.form.get('pergunta')
    
    if not pergunta:
        flash('Digite sua pergunta.', 'warning')
        return redirect(url_for('pesquisa'))
    
    data = {'pergunta': pergunta, 'usar_rag': True}
    result, error = api_request('POST', '/rag/consulta-ia', data)
    
    if error:
        flash(error, 'danger')
        return redirect(url_for('pesquisa'))
    
    return render_template('resultado_ia.html', resultado=result, pergunta=pergunta)

# =====================
# CONSULTA CNJ
# =====================

@app.route('/cnj', methods=['GET', 'POST'])
@login_required
def cnj():
    """Consulta CNJ"""
    processo = None
    
    if request.method == 'POST':
        numero = request.form.get('numero_processo')
        
        if not numero:
            flash('Digite o número do processo.', 'warning')
        else:
            result, error = api_request('POST', '/cnj/processo', {'numero_processo': numero})
            
            if error:
                flash(error, 'danger')
            else:
                processo = result
    
    return render_template('cnj.html', processo=processo)

@app.route('/cnj/salvar', methods=['POST'])
@login_required
def cnj_salvar():
    """Salvar processo do CNJ"""
    data = request.get_json()
    
    # Extract sync_cnj to pass as query param
    sync_cnj = data.pop('sync_cnj', True)
    
    # Use lowercase 'true'/'false' for query string if it's a boolean
    sync_str = 'true' if sync_cnj else 'false'
    
    result, error = api_request('POST', f'/cnj/processo/salvar?sync_cnj={sync_str}', data)
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify(result)

@app.route('/cnj/sync/<numero>')
@login_required
def cnj_sync(numero):
    """Sincronizar movimentações"""
    result, error = api_request('POST', f'/cnj/processo/{numero}/sync')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        if error:
            return jsonify({'error': error}), 400
        return jsonify({'success': True, 'message': 'Processo sincronizado com sucesso!'})

    if error:
        flash(error, 'danger')
    else:
        flash('Processo sincronizado com sucesso!', 'success')
    
    return redirect(request.referrer or url_for('cnj'))

# =====================
# PETIÇÕES
# =====================

@app.route('/peticoes')
@login_required
def peticoes():
    """Lista de petições"""
    # Passar parâmetros de filtro da URL para a API
    params = request.args.to_dict()
    
    # Se não tiver página/limit, define padrões
    if 'page' not in params:
        params['page'] = 1
    if 'limit' not in params:
        params['limit'] = 9  # 9 cards por página (grid 3x3)
        
    result, error = api_request('GET', '/peticoes', params)
    
    peticoes_lista = result.get('peticoes', []) if result else []
    total = result.get('total', 0) if result else 0
    page = int(params.get('page', 1))
    limit = int(params.get('limit', 9))
    
    # Se for uma requisição AJAX/Fetch pedindo JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({
            'peticoes': peticoes_lista,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit if limit > 0 else 1
        })
        
    return render_template('peticoes/lista.html', 
                          peticoes=peticoes_lista, 
                          total=total, 
                          page=page, 
                          limit=limit,
                          total_pages=(total + limit - 1) // limit if limit > 0 else 1)

@app.route('/peticoes/nova', methods=['GET', 'POST'])
@login_required
def peticao_nova():
    """Criar nova petição"""
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes
        
        tipo = request.form.get('tipo') or request.json.get('tipo')
        objetivo = request.form.get('objetivo') or request.json.get('objetivo')
        numero_processo = request.form.get('numero_processo') or request.json.get('numero_processo') or request.json.get('processo', {}).get('numero')
        fatos = request.form.get('fatos') or request.json.get('fatos')
        fundamentacao = request.form.get('fundamentacao') or request.json.get('fundamentos')
        pedidos = request.form.get('pedidos') or request.json.get('pedidos')
        jurisprudencia_ids = request.form.getlist('jurisprudencia_ids') or request.json.get('jurisprudencia_ids', [])
        
        # Gerar via IA
        if request.form.get('usar_ia') == 'true' or request.json.get('usar_rag') is not None:
            data = {
                'tipo_peticao': tipo,
                'objetivo': objetivo or fatos, # Fallback
                'numero_processo': numero_processo,
                'fatos': fatos,
                'pedidos': pedidos if isinstance(pedidos, list) else (pedidos.split('\n') if pedidos else []),
                'jurisprudencia_ids': [int(id) for id in jurisprudencia_ids if id],
                'usar_rag': request.json.get('usar_rag', True) if request.is_json else True
            }
            
            result, error = api_request('POST', '/peticoes/gerar', data)
            
            if is_ajax:
                if error:
                    return jsonify({'error': error}), 400
                return jsonify(result)
            
            if error:
                flash(error, 'danger')
                return render_template('peticoes/nova.html', tipos=get_tipos_peticao())
            
            # Redirecionar para editor com conteúdo gerado
            return render_template('peticoes/editor.html', 
                                  peticao=result, 
                                  modo='nova',
                                  tipos=get_tipos_peticao())
        else:
            # Criar manualmente
            conteudo = request.form.get('conteudo') or request.json.get('conteudo')
            if not conteudo:
                # Se não tem conteúdo pronto, monta um básico
                pedidos_str = '\n'.join(pedidos) if isinstance(pedidos, list) else pedidos
                conteudo = f"""
                    <h2>DOS FATOS</h2>
                    <p>{fatos}</p>
                    
                    <h2>DO DIREITO</h2>
                    <p>{fundamentacao}</p>
                    
                    <h2>DOS PEDIDOS</h2>
                    <p>{pedidos_str}</p>
                """

            data = {
                'titulo': request.form.get('titulo') or request.json.get('titulo') or f'{tipo.upper()} - {objetivo[:50] if objetivo else "Nova Petição"}',
                'tipo': tipo,
                'conteudo': conteudo,
                'numero_processo': numero_processo
            }
            
            result, error = api_request('POST', '/peticoes', data)
            
            if is_ajax:
                if error:
                    return jsonify({'error': error}), 400
                return jsonify({'success': True, 'id': result['id'], 'redirect_url': url_for('peticao_editar', id=result['id'])})
            
            if error:
                flash(error, 'danger')
                return render_template('peticoes/nova.html', tipos=get_tipos_peticao())
            
            flash('Petição criada com sucesso!', 'success')
            return redirect(url_for('peticao_editar', id=result['id']))
    
    return render_template('peticoes/nova.html', tipos=get_tipos_peticao())

# =====================
# API PROXIES FOR AJAX
# =====================

@app.route('/api/pesquisa', methods=['POST'])
@login_required
def api_pesquisa_proxy():
    """Proxy para pesquisa de jurisprudência (JSON)"""
    data = request.get_json()
    # Ajuste de chaves se necessário
    payload = {
        'query': data.get('query'),
        'top_k': data.get('top_k', 10),
        'tribunal': data.get('tribunal'),
        'area_direito': data.get('area_direito')
    }
    result, error = api_request('POST', '/rag/search', payload)
    
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/api/ia/sugerir', methods=['POST'])
@login_required
def api_ia_sugerir_proxy():
    """Proxy para sugestão de IA (JSON)"""
    data = request.get_json()
    
    payload = {
        'pergunta': f"Atue como assistente jurídico. Contexto: {data.get('contexto')}. Texto atual: {data.get('conteudo_atual')}. Tarefa: {data.get('tipo')} (continuar/melhorar/fundamentar).",
        'search_query': data.get('contexto') or "Direito Processual Civil",
        'usar_rag': True
    }
    
    result, error = api_request('POST', '/rag/consulta-ia', payload)
    
    if error:
        return jsonify({'error': error}), 400
        
    # O retorno de /rag/consulta-ia é { 'content': '...', ... }
    return jsonify({'sugestao': result.get('content')})

@app.route('/api/processos/buscar', methods=['GET'])
@login_required
def api_processos_buscar_proxy():
    """Proxy para busca de processos (JSON)"""
    numero = request.args.get('numero')
    if not numero:
        return jsonify({'error': 'Número do processo é obrigatório'}), 400
        
    # Tenta buscar local primeiro ou no CNJ
    # Endpoint /cnj/processo já faz a busca
    result, error = api_request('POST', '/cnj/processo', {'numero_processo': numero})
    
    if error:
        return jsonify({'error': error}), 404
        
    # Mapear resposta para o formato esperado pelo frontend
    # CNJConsultaResponse: numero_cnj, polo_ativo (list), polo_passivo (list), tribunal, vara
    
    polo_ativo = result.get('polo_ativo', [])
    autor = polo_ativo[0] if isinstance(polo_ativo, list) and polo_ativo else str(polo_ativo)
    
    polo_passivo = result.get('polo_passivo', [])
    reu = polo_passivo[0] if isinstance(polo_passivo, list) and polo_passivo else str(polo_passivo)
    
    return jsonify({
        'id': result.get('id', 1), # Retorna ID fictício se não tiver (para passar no check do frontend)
        'numero': result.get('numero_cnj'),
        'autor': autor,
        'reu': reu,
        'tribunal': result.get('tribunal'),
        'vara': result.get('vara')
    })

@app.route('/peticoes/<int:id>')
@login_required
def peticao_ver(id):
    """Ver petição"""
    result, error = api_request('GET', f'/peticoes/{id}')
    
    if error:
        flash(error, 'danger')
        return redirect(url_for('peticoes'))
    
    return render_template('peticoes/ver.html', peticao=result)

@app.route('/peticoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def peticao_editar(id):
    """Editar petição"""
    if request.method == 'POST':
        data = {
            'titulo': request.form.get('titulo'),
            'conteudo': request.form.get('conteudo'),
            'tipo': request.form.get('tipo')
        }
        
        result, error = api_request('PUT', f'/peticoes/{id}', data)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
            if error:
                return jsonify({'error': error}), 400
            return jsonify({'success': True, 'message': 'Petição salva com sucesso!'})
        
        if error:
            flash(error, 'danger')
        else:
            flash('Petição atualizada com sucesso!', 'success')
            return redirect(url_for('peticao_ver', id=id))
    
    result, error = api_request('GET', f'/peticoes/{id}')
    
    if error:
        flash(error, 'danger')
        return redirect(url_for('peticoes'))
    
    return render_template('peticoes/editor.html', 
                          peticao=result, 
                          modo='editar',
                          tipos=get_tipos_peticao())

@app.route('/peticoes/<int:id>/autosave', methods=['POST'])
@login_required
def peticao_autosave(id):
    """Auto-salvar petição"""
    data = {
        'titulo': request.form.get('titulo'),
        'conteudo': request.form.get('conteudo'),
        'tipo': request.form.get('tipo')
    }
    
    result, error = api_request('PUT', f'/peticoes/{id}', data)
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return jsonify({'success': True})

@app.route('/peticoes/exportar', methods=['POST'])
@login_required
def peticao_exportar_conteudo():
    """Exportar conteúdo de petição (sem salvar)"""
    data = request.get_json()
    formato = data.get('formato', 'docx')
    
    if formato not in ['docx', 'pdf']:
        return jsonify({'error': 'Formato inválido'}), 400
        
    # Usar requests diretamente para streaming
    url = f"{API_BASE_URL}/peticoes/exportar/{formato}"
    headers = get_auth_headers()
    
    try:
        # Request com stream=True
        response = requests.post(url, headers=headers, json=data, stream=True, timeout=120)
        
        if response.status_code != 200:
            try:
                error_msg = response.json().get('detail', 'Erro ao exportar')
            except:
                error_msg = 'Erro ao exportar arquivo'
            return jsonify({'error': error_msg}), 400
            
        # Retorna o arquivo (Blob para o frontend)
        # O frontend espera um blob, então retornamos o arquivo binary
        return send_file(
            io.BytesIO(response.content),
            mimetype=response.headers.get('Content-Type'),
            as_attachment=True,
            download_name=f"{data.get('titulo', 'peticao')}.{formato}"
        )
        
    except Exception as e:
        return jsonify({'error': f'Erro de conexão: {str(e)}'}), 500

@app.route('/peticoes/<int:id>/exportar/<formato>')
@login_required
def peticao_exportar(id, formato):
    """Exportar petição"""
    if formato not in ['docx', 'pdf']:
        flash('Formato inválido.', 'danger')
        return redirect(url_for('peticao_ver', id=id))
    
    # Usar requests diretamente para streaming
    url = f"{API_BASE_URL}/peticoes/{id}/exportar/{formato}"
    headers = get_auth_headers()
    
    try:
        # Request com stream=True para não carregar tudo em memória
        response = requests.post(url, headers=headers, stream=True, timeout=120)
        
        if response.status_code != 200:
            try:
                error_msg = response.json().get('detail', 'Erro ao exportar')
            except:
                error_msg = 'Erro ao exportar arquivo'
            flash(error_msg, 'danger')
            return redirect(url_for('peticao_ver', id=id))
            
        # Retorna o arquivo como anexo
        return send_file(
            io.BytesIO(response.content),
            mimetype=response.headers.get('Content-Type'),
            as_attachment=True,
            download_name=f"peticao_{id}.{formato}"
        )
        
    except Exception as e:
        flash(f'Erro de conexão: {str(e)}', 'danger')
        return redirect(url_for('peticao_ver', id=id))

@app.route('/peticoes/<int:id>/deletar', methods=['POST'])
@login_required
def peticao_deletar(id):
    """Deletar petição (soft delete)"""
    result, error = api_request('DELETE', f'/peticoes/{id}')

    if error:
        flash(error, 'danger')
    else:
        flash('Petição removida com sucesso.', 'success')

    return redirect(url_for('peticoes'))

def get_tipos_peticao():
    """Retorna tipos de petição disponíveis"""
    return [
        {'valor': 'inicial', 'nome': 'Petição Inicial'},
        {'valor': 'contestacao', 'nome': 'Contestação'},
        {'valor': 'recurso', 'nome': 'Recurso'},
        {'valor': 'apelacao', 'nome': 'Apelação'},
        {'valor': 'agravo', 'nome': 'Agravo de Instrumento'},
        {'valor': 'embargos', 'nome': 'Embargos de Declaração'},
        {'valor': 'habeas_corpus', 'nome': 'Habeas Corpus'},
        {'valor': 'mandado_seguranca', 'nome': 'Mandado de Segurança'},
        {'valor': 'manifestacao', 'nome': 'Manifestação'},
        {'valor': 'replica', 'nome': 'Réplica'},
        {'valor': 'contrarrazoes', 'nome': 'Contrarrazões'},
        {'valor': 'memoriais', 'nome': 'Memoriais'}
    ]

# =====================
# PROCESSOS
# =====================

@app.route('/processos')
@login_required
def processos():
    """Lista de processos"""
    # Passar parâmetros de filtro da URL para a API
    params = request.args.to_dict()
    result, error = api_request('GET', '/cnj/processos', params)
    processos_lista = result.get('processos', []) if result else []
    total = result.get('total', 0) if result else 0
    page = int(params.get('page', 1))
    limit = int(params.get('limit', 10))
    
    # Se for uma requisição AJAX/Fetch pedindo JSON (para filtros dinâmicos sem recarregar)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({
            'processos': processos_lista,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit if limit > 0 else 1
        })
        
    return render_template('processos/lista.html', processos=processos_lista, total=total, page=page, limit=limit)

@app.route('/processos/<int:id>')
@login_required
def processo_ver(id):
    """Ver processo por ID"""
    result, error = api_request('GET', f'/cnj/processo-by-id/{id}')

    if error:
        flash(error, 'danger')
        return redirect(url_for('processos'))

    # Renderizar apenas com dados básicos
    # Movimentações, petições e documentos serão carregados via AJAX
    return render_template('processos/ver.html', processo=result)

@app.route('/api/processos/<int:id>/movimentacoes')
@login_required
def api_processo_movimentacoes(id):
    """API para buscar movimentações de um processo"""
    # Primeiro busca o número do processo pelo ID
    proc, error = api_request('GET', f'/cnj/processo-by-id/{id}')
    if error:
        return jsonify({'error': error}), 404
        
    numero_cnj = proc.get('numero_cnj')
    if not numero_cnj:
        return jsonify({'movimentacoes': []})
        
    movs, error = api_request('GET', f'/cnj/processo/{numero_cnj}/movimentacoes')
    if error:
        return jsonify({'error': error}), 400
        
    return jsonify({'movimentacoes': movs})

@app.route('/api/processos/<int:id>/peticoes')
@login_required
def api_processo_peticoes(id):
    """API para buscar petições de um processo"""
    # Busca petições filtrando pelo processo_id
    result, error = api_request('GET', '/peticoes', {'processo_id': id, 'limit': 100})
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'peticoes': result.get('peticoes', [])})

@app.route('/api/processos/<int:id>/documentos')
@login_required
def api_processo_documentos(id):
    """API para buscar documentos de um processo"""
    # Busca documentos filtrando pelo processo_id
    result, error = api_request('GET', '/documentos', {'processo_id': id, 'limit': 100})
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'documentos': result.get('documentos', [])})

# =====================
# HISTÓRICO IA
# =====================

@app.route('/ia/historico')
@login_required
def ia_historico():
    """Histórico de consultas IA"""
    page = request.args.get('page', 1, type=int)
    
    result, error = api_request('GET', '/audit/ia-historico', {'page': page, 'limit': 20})
    
    historico = result.get('logs', []) if result else []
    total = result.get('total', 0) if result else 0
    
    return render_template('ia_historico.html', 
                          historico=historico, 
                          page=page, 
                          total=total,
                          total_pages=(total + 19) // 20)

# =====================
# DOCUMENTOS
# =====================

@app.route('/documentos')
@login_required
def documentos():
    """Lista de documentos"""
    # Passar parâmetros de filtro da URL para a API
    params = request.args.to_dict()
    result, error = api_request('GET', '/documentos', params)
    docs = result.get('documentos', []) if result else []
    
    # Se for uma requisição AJAX/Fetch pedindo JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify(result or {'documentos': []})
        
    return render_template('documentos/lista.html', documentos=docs)

@app.route('/documentos/upload', methods=['POST'])
@login_required
def documento_upload():
    """Upload de documento"""
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('documentos'))
    
    arquivo = request.files['arquivo']
    
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('documentos'))
    
    if arquivo and allowed_file(arquivo.filename):
        filename = secure_filename(arquivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        arquivo.save(filepath)
        
        # Enviar para API
        with open(filepath, 'rb') as f:
            files = {'arquivo': (filename, f, arquivo.content_type)}
            data = {
                'nome': request.form.get('nome', filename),
                'descricao': request.form.get('descricao', ''),
                'processo_id': request.form.get('processo_id')
            }
            
            result, error = api_request('POST', '/documentos/upload', data, files)
        
        # Limpar arquivo temporário
        os.remove(filepath)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
            if error:
                return jsonify({'error': error}), 400
            return jsonify({'success': True, 'message': 'Documento enviado com sucesso!'})

        if error:
            flash(error, 'danger')
        else:
            flash('Documento enviado com sucesso!', 'success')
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
            return jsonify({'error': 'Tipo de arquivo não permitido.'}), 400
        flash('Tipo de arquivo não permitido.', 'danger')
    
    return redirect(url_for('documentos'))

# =====================
# ADMINISTRAÇÃO
# =====================

@app.route('/admin')
@admin_required
def admin():
    """Painel de administração"""
    return render_template('admin/index.html')

@app.route('/admin/usuarios')
@admin_required
def admin_usuarios():
    """Gerenciar usuários"""
    result, error = api_request('GET', '/admin/usuarios')
    usuarios = result.get('usuarios', []) if result else []
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'usuarios': usuarios})
        
    return render_template('admin/usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios', methods=['POST'])
@admin_required
def admin_usuario_criar():
    """Criar novo usuário"""
    data = request.get_json()
    result, error = api_request('POST', '/admin/usuarios', data)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/admin/usuarios/<int:user_id>', methods=['PUT'])
@admin_required
def admin_usuario_atualizar(user_id):
    """Atualizar usuário existente"""
    data = request.get_json()
    result, error = api_request('PUT', f'/admin/usuarios/{user_id}', data)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/admin/usuarios/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_usuario_excluir(user_id):
    """Excluir usuário"""
    result, error = api_request('DELETE', f'/admin/usuarios/{user_id}')
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/admin/logs')
@admin_required
def admin_logs():
    """Ver logs de auditoria"""
    page = request.args.get('page', 1, type=int)
    modulo = request.args.get('modulo')
    acao = request.args.get('acao')
    
    params = {'page': page, 'limit': 50}
    if modulo:
        params['modulo'] = modulo
    if acao:
        params['acao'] = acao
    
    result, error = api_request('GET', '/audit/logs', params)
    
    logs = result.get('logs', []) if result else []
    total = result.get('total', 0) if result else 0
    
    return render_template('admin/logs.html', 
                          logs=logs, 
                          page=page, 
                          total=total,
                          total_pages=(total + 49) // 50)

@app.route('/admin/logs/limpar', methods=['POST'])
@admin_required
def admin_logs_limpar():
    """Limpar logs de auditoria (LGPD)"""
    data = request.get_json()
    dias = data.get('dias', 90)
    
    # Validação de segurança: mínimo 30 dias (LGPD)
    try:
        if int(dias) < 30:
            return jsonify({'error': 'O período mínimo para retenção de logs é de 30 dias (LGPD).'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Valor de dias inválido.'}), 400
        
    result, error = api_request('DELETE', f'/audit/limpar?dias={dias}')
    
    if error:
        return jsonify({'error': error}), 400
        
    return jsonify(result)

@app.route('/admin/logs/exportar')
@admin_required
def admin_logs_exportar():
    """Exportar logs de auditoria (CSV/JSON)"""
    formato = request.args.get('formato', 'csv')
    
    # Repassar filtros
    params = request.args.to_dict()
    params['limit'] = 10000 # Limite alto para exportação
    
    result, error = api_request('GET', '/audit/logs', params)
    
    if error:
        flash(f"Erro ao exportar: {error}", 'danger')
        return redirect(url_for('admin_logs'))
        
    logs = result.get('logs', [])
    
    if formato == 'json':
        return jsonify(logs)
        
    # Exportar como CSV
    import csv
    import io
    from datetime import datetime
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho
    writer.writerow(['Data/Hora', 'Usuário', 'Ação', 'Módulo', 'Detalhes', 'IP'])
    
    for log in logs:
        writer.writerow([
            log.get('timestamp'),
            log.get('usuario_email'),
            log.get('acao'),
            log.get('modulo'),
            log.get('detalhes'),
            log.get('usuario_ip')
        ])
        
    output.seek(0)
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=logs_auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )


@app.route('/admin/configuracoes', methods=['GET', 'POST'])
@admin_required
def admin_configuracoes():
    """Configurações do sistema"""
    if request.method == 'POST':
        # Receber dados do formulário
        config_data = request.form.to_dict()
        
        # Processar checkboxes não enviados
        checkboxes = ['usar_rag', 'usar_2fa', 'cadastro_publico', 'force_https', 'antivirus_scan']
        for chk in checkboxes:
            if chk not in config_data:
                config_data[chk] = 'false'
            else:
                config_data[chk] = 'true'
                
        errors = []
        success_count = 0
        
        # Salvar cada configuração
        for chave, valor in config_data.items():
            payload = {'valor': str(valor)}
            # Tentar salvar
            res, err = api_request('PUT', f'/config/{chave}', payload)
            if err:
                errors.append(f"{chave}: {err}")
            else:
                success_count += 1
        
        if errors:
            flash(f'Erros ao salvar: {"; ".join(errors[:3])}...', 'warning')
        else:
            flash('Configurações salvas com sucesso!', 'success')
            
        return redirect(url_for('admin_configuracoes'))
    
    # Carregar configurações
    configs, error = api_request('GET', '/config/')
    config_dict = {}
    if configs and isinstance(configs, list):
        for c in configs:
            config_dict[c.get('chave')] = c.get('valor')
    
    return render_template('admin/configuracoes.html', config=config_dict)

@app.route('/api/config/test-email', methods=['POST'])
@admin_required
def api_config_test_email():
    """Teste de email"""
    result, error = api_request('POST', '/config/test-email')
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/api/config/test-cnj', methods=['POST'])
@admin_required
def api_config_test_cnj():
    """Teste de conexão CNJ"""
    result, error = api_request('POST', '/config/test-cnj')
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/api/config/reset', methods=['POST'])
@admin_required
def api_config_reset():
    """Reset de configurações"""
    result, error = api_request('POST', '/config/reset')
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/api/config/clear-cache', methods=['POST'])
@admin_required
def api_config_clear_cache():
    """Limpar cache"""
    result, error = api_request('POST', '/config/clear-cache')
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)

@app.route('/api/config/check-updates', methods=['POST'])
@admin_required
def api_config_check_updates():
    """Verificar atualizações (Simulado)"""
    # Em um sistema real, consultaria um servidor de atualizações
    import time
    time.sleep(1) # Simula delay
    return jsonify({'success': True, 'message': 'Sistema atualizado! Versão 1.0.0', 'version': '1.0.0'})

@app.route('/admin/llm')
@admin_required
def admin_llm():
    """Gestão de Modelos LLM"""
    return render_template('admin/llm.html')

@app.route('/admin/llm/status')
@admin_required
def admin_llm_status():
    """Status do LLM"""
    result, error = api_request('GET', '/llm/status')
    if error:
        return jsonify({'error': error}), 500
    return jsonify(result)

@app.route('/admin/llm/models')
@admin_required
def admin_llm_models():
    """Modelos LLM"""
    result, error = api_request('GET', '/llm/models')
    if error:
        return jsonify({'error': error}), 500
    return jsonify(result)

@app.route('/admin/llm/active-model', methods=['PUT'])
@admin_required
def admin_llm_active_model():
    """Definir modelo ativo"""
    data = request.get_json()
    result, error = api_request('PUT', '/llm/active-model', data)
    if error:
        return jsonify({'detail': error}), 400
    return jsonify(result)

# =====================
# ERROS
# =====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

# =====================
# MAIN
# =====================

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    )
