#!/bin/bash
# Script para executar a aplicação Streamlit

cd "$(dirname "$0")"

# Verificar se o arquivo de dados existe
if [ ! -f "data/aws_finops_data.json" ]; then
    echo "⚠️  Arquivo de dados não encontrado!"
    echo "📋 Execute primeiro o playbook para coletar os dados:"
    echo "   ansible-playbook playbooks/finops_collect.yml"
    exit 1
fi

# Executar Streamlit
echo "🚀 Iniciando AWS FinOps Dashboard..."
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
