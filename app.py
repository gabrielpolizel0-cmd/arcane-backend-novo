# -*- coding: utf-8 -*-
import os
import jwt
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic

app = Flask(__name__)
CORS(app, origins='*')

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET', '')

TOOL_PROMPTS = {
  'contrato': 'Voce e especialista em direito empresarial brasileiro. Gere um contrato profissional e completo.',
  'proposta': 'Voce e especialista em vendas B2B. Crie uma proposta comercial persuasiva e profissional.',
  'relatorio': 'Voce e especialista em comunicacao executiva. Crie um relatorio executivo claro e impactante.',
  'email_corp': 'Voce e especialista em comunicacao corporativa. Escreva um e-mail profissional.',
  'analise': 'Voce e analista de dados senior. Analise os dados e gere insights estrategicos.',
  'query': 'Voce e especialista em banco de dados. Gere uma query SQL otimizada.',
  'previsao': 'Voce e especialista em business intelligence. Projete tendencias e cenarios.',
  'kpis': 'Voce e especialista em gestao por indicadores. Sugira KPIs relevantes.',
  'ata': 'Voce e especialista em comunicacao empresarial. Gere uma ata de reuniao profissional.',
  'resumo': 'Voce e especialista em sintese. Resuma o conteudo destacando pontos-chave.',
  'onboarding': 'Voce e especialista em gestao de pessoas. Crie um plano de onboarding completo.',
  'base_conhecimento': 'Voce e especialista em gestao do conhecimento. Estruture as informacoes.',
  'post_social': 'Voce e especialista em marketing digital. Crie posts envolventes com hashtags e CTA.',
  'blog': 'Voce e especialista em content marketing e SEO. Escreva artigo completo e otimizado.',
  'email_mkt': 'Voce e especialista em e-mail marketing. Escreva campanha persuasiva.',
  'descricao': 'Voce e especialista em copywriting. Escreva descricao de produto irresistivel.',
  'orcamento': 'Voce e especialista financeiro. Gere um orcamento profissional detalhado.',
  'fluxo_caixa': 'Voce e especialista em financas. Crie modelo de fluxo de caixa mensal.',
  'precificacao': 'Voce e especialista em precificacao. Calcule e justifique o preco ideal.',
  'nf_descritiva': 'Voce e especialista fiscal. Escreva descricao para nota fiscal de servico.',
  'lgpd': 'Voce e especialista em LGPD. Gere politica de privacidade completa.',
  'termos_uso': 'Voce e especialista em direito digital. Escreva termos de uso claros.',
  'nda': 'Voce e especialista em contratos. Gere um acordo de confidencialidade profissional.',
  'distrato': 'Voce e especialista em contratos. Gere um distrato comercial formal.',
  'descricao_vaga': 'Voce e especialista em recrutamento. Escreva descricao de vaga atrativa.',
  'avaliacao_desemp': 'Voce e especialista em RH. Crie formulario de avaliacao de desempenho.',
  'politica_interna': 'Voce e especialista em gestao de pessoas. Escreva politica interna clara.',
  'roteiro_entrevista': 'Voce e especialista em selecao. Crie roteiro de entrevista estruturado.',
  'cold_call': 'Voce e especialista em vendas. Crie script de cold call eficaz.',
  'proposta_parc': 'Voce e especialista em parcerias. Crie proposta de parceria convincente.',
  'followup': 'Voce e especialista em CRM. Escreva mensagem de follow-up eficaz.',
  'analise_conc': 'Voce e especialista em inteligencia competitiva. Analise o concorrente.',
  'briefing': 'Voce e especialista em projetos. Crie briefing completo alinhando expectativas.',
  'proposta_free': 'Voce e especialista em freelance. Escreva proposta profissional.',
  'contrato_free': 'Voce e especialista em contratos. Gere contrato simples para freelancers.',
  'bio_prof': 'Voce e especialista em personal branding. Escreva bio profissional impactante.',
  'roteiro_suporte': 'Voce e especialista em customer success. Crie roteiro de atendimento.',
  'resp_reclamacao': 'Voce e especialista em gestao de conflitos. Escreva resposta para reclamacao.',
  'pesq_satisfacao': 'Voce e especialista em NPS. Crie pesquisa de satisfacao estrategica.',
  'faq_produto': 'Voce e especialista em produto. Crie FAQ completo do produto.',
  'planilha_orcamento': 'Voce e especialista financeiro. Crie orcamento detalhado em formato CSV para Excel.',
  'planilha_fluxo': 'Voce e especialista financeiro. Crie fluxo de caixa mensal em CSV. NUNCA use markdown. Sem simbolos de moeda. Use formulas Excel em ingles.',
  'apresentacao_ppt': 'Voce e especialista em apresentacoes. Crie roteiro de slides profissional.',
  'relatorio_pdf': 'Voce e especialista em comunicacao executiva. Gere relatorio executivo completo.',
}

def verify_supabase_token(token):
    try:
        from supabase import create_client
        url = os.getenv('SUPABASE_URL', '')
        key = os.getenv('SUPABASE_SERVICE_KEY', '')
        client = create_client(url, key)
        user = client.auth.get_user(token)
        return user.user.id if user and user.user else None
    except Exception as e:
        print(f"Token error: {e}")
        return None

@app.route('/api/ai/generate', methods=['POST'])
def generate():
    auth = request.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '')
    
    user_id = verify_supabase_token(token)
    if not user_id:
        return jsonify({'error': 'Nao autorizado'}), 401

    data = request.get_json()
    tool = data.get('tool', '').strip()
    user_input = data.get('input', '').strip()
    system_prompt = data.get('system_prompt', TOOL_PROMPTS.get(tool, ''))

    if not user_input:
        return jsonify({'error': 'Input obrigatorio'}), 400

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=2048,
            messages=[{'role': 'user', 'content': system_prompt + '\n\n' + user_input}]
        )
        output = message.content[0].text
    except Exception as e:
        return jsonify({'error': 'Erro na IA: ' + str(e)}), 500

    return jsonify({'output': output}), 200

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=True)