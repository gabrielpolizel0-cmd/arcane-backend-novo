import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
import bcrypt
import anthropic

app = Flask(__name__)

# Config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///arcane.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, origins='*')
db = SQLAlchemy(app)
jwt = JWTManager(app)

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
PLAN_LIMITS = {'free': 5, 'starter': 150, 'business': 500, 'unlimited': 999999}

# Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='free')
    generations_used = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(50))

with app.app_context():
    db.create_all()

# Auth
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': 'Email e senha obrigatorios'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email ja cadastrado'}), 409

    # 1 conta por IP
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if User.query.filter_by(ip_address=ip).first():
        return jsonify({'error': 'Ja existe uma conta cadastrada neste dispositivo'}), 409

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password=hashed, ip_address=ip)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({'access_token': token, 'user': {'email': user.email, 'plan': user.plan}}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password.encode()):
        return jsonify({'error': 'Email ou senha incorretos'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'access_token': token, 'user': {'email': user.email, 'plan': user.plan}}), 200

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Usuario nao encontrado'}), 404
    limit = PLAN_LIMITS.get(user.plan, 5)
    return jsonify({'email': user.email, 'plan': user.plan, 'used': user.generations_used, 'limit': limit}), 200

# AI
TOOL_PROMPTS = {
    'contrato': 'Você é um especialista jurídico. Gere um contrato profissional completo baseado na descrição do usuário. Seja detalhado e formal.',
    'proposta': 'Você é um especialista em vendas. Gere uma proposta comercial profissional baseada na descrição do usuário.',
    'relatorio': 'Você é um analista de negócios. Gere um relatório profissional completo baseado nas informações fornecidas.',
    'email_corp': 'Você é um especialista em comunicação corporativa. Gere um email profissional baseado na descrição do usuário.',
    'analise': 'Você é um analista de dados. Faça uma análise detalhada baseada nas informações fornecidas.',
    'dashboard_text': 'Você é um analista. Gere um resumo executivo para dashboard baseado nos dados fornecidos.',
    'sql': 'Você é um especialista em SQL. Gere queries SQL otimizadas baseado na descrição do usuário.',
    'previsao': 'Você é um analista preditivo. Faça previsões e análises baseadas nos dados fornecidos.',
    'ata': 'Você é um secretário executivo. Gere uma ata de reunião profissional baseada nas informações fornecidas.',
    'resumo_reuniao': 'Você é um especialista em produtividade. Gere um resumo executivo de reunião baseado nas informações fornecidas.',
    'onboarding': 'Você é um especialista em RH. Gere um plano de onboarding completo baseado nas informações fornecidas.',
    'knowledge': 'Você é um especialista em gestão do conhecimento. Gere documentação clara e organizada baseada nas informações fornecidas.',
    'post_social': 'Você é um especialista em marketing digital. Gere posts para redes sociais criativos e engajantes baseado na descrição.',
    'blog': 'Você é um redator profissional. Gere um artigo de blog completo e otimizado para SEO baseado no tema fornecido.',
    'email_mkt': 'Você é um especialista em email marketing. Gere um email de marketing persuasivo baseado na descrição.',
    'descricao': 'Você é um copywriter profissional. Gere descrições persuasivas de produtos ou serviços baseado nas informações fornecidas.',
}

@app.route('/api/ai/generate', methods=['POST'])
@jwt_required()
def generate():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Usuario nao encontrado'}), 404

    limit = PLAN_LIMITS.get(user.plan, 5)
    if user.generations_used >= limit:
        return jsonify({'error': 'Limite de geracoes atingido. Faca upgrade do plano!'}), 403

    data = request.get_json()
    tool = data.get('tool', '').strip()
    user_input = data.get('input', '').strip()

    if not tool or tool not in TOOL_PROMPTS:
        return jsonify({'error': 'Ferramenta invalida'}), 400
    if not user_input:
        return jsonify({'error': 'Input obrigatorio'}), 400

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=2048,
            messages=[{'role': 'user', 'content': f'{TOOL_PROMPTS[tool]}\n\n{user_input}'}]
        )
        output = message.content[0].text
    except Exception as e:
        return jsonify({'error': f'Erro na IA: {str(e)}'}), 500

    user.generations_used += 1
    db.session.commit()

    return jsonify({
        'output': output,
        'used': user.generations_used,
        'limit': limit
    }), 200

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'arcane-api'}), 200

if __name__ == '__main__':
    app.run(debug=True)
