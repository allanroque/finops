import streamlit as st
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(
    page_title="AWS FinOps Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos customizados
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF9900;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #1f1f1f;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #FF9900;
    }
    .warning-box {
        background-color: #ff4444;
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #4444ff;
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Carregar dados
@st.cache_data(ttl=300)
def load_data():
    """Carrega os dados do arquivo JSON"""
    # Tenta primeiro o caminho relativo (quando o app está em /opt/finops/)
    data_file = Path(__file__).parent / "data" / "aws_finops_data.json"
    
    # Se não encontrar, tenta o caminho absoluto de produção
    if not data_file.exists():
        data_file = Path("/opt/finops/data/aws_finops_data.json")
    
    if not data_file.exists():
        st.error(f"Arquivo de dados não encontrado em: {data_file}")
        st.info("Execute o playbook finops_collect.yml primeiro para coletar os dados.")
        return None
    
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None

def main():
    st.markdown('<div class="main-header">📊 AWS FinOps Audit Report</div>', unsafe_allow_html=True)
    
    data = load_data()
    if data is None:
        return
    
    # Sidebar com informações da conta
    with st.sidebar:
        st.header("📋 Account Information")
        st.write(f"**Account ID:** {data.get('account_id', 'N/A')}")
        st.write(f"**Account Alias:** {data.get('account_alias', 'N/A')}")
        st.write(f"**User:** {data.get('user_arn', 'N/A').split('/')[-1]}")
        
        if 'collection_timestamp' in data:
            timestamp = datetime.fromisoformat(data['collection_timestamp'].replace('Z', '+00:00'))
            st.write(f"**Última atualização:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("---")
        st.markdown("### 🔄 Atualizar Dados")
        if st.button("Executar Coleta"):
            st.info("Execute: ansible-playbook playbooks/finops_collect.yml")
    
    # Preparar dados agregados
    all_instances = []
    all_untagged = []
    all_stopped = []
    all_unused_volumes = []
    all_unused_eips = []
    
    for region_data in data.get('regions', []):
        region = region_data.get('region', 'unknown')
        
        # Instâncias
        for instance in region_data.get('instances', {}).get('details', []):
            instance['region'] = region
            all_instances.append(instance)
        
        # Recursos não taggeados
        for instance in region_data.get('untagged_resources', {}).get('instances', []):
            instance['region'] = region
            all_untagged.append(instance)
        
        # Instâncias paradas
        for instance in region_data.get('stopped_instances', {}).get('details', []):
            instance['region'] = region
            all_stopped.append(instance)
        
        # Volumes não utilizados
        for volume in region_data.get('unused_volumes', {}).get('details', []):
            volume['region'] = region
            all_unused_volumes.append(volume)
        
        # EIPs não utilizados
        for eip in region_data.get('unused_eips', {}).get('details', []):
            eip['region'] = region
            all_unused_eips.append(eip)
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    total_instances = len(all_instances)
    running_instances = len([i for i in all_instances if i.get('state') == 'running'])
    stopped_instances = len(all_stopped)
    untagged_count = len(all_untagged)
    
    with col1:
        st.metric("Total de Instâncias", total_instances)
    with col2:
        st.metric("Instâncias em Execução", running_instances, delta=f"-{stopped_instances} paradas")
    with col3:
        st.metric("Recursos Não Taggeados", untagged_count, 
                 delta="Crítico" if untagged_count > 0 else "OK", delta_color="inverse")
    with col4:
        unused_volumes_count = len(all_unused_volumes)
        unused_eips_count = len(all_unused_eips)
        total_cost_risks = stopped_instances + unused_volumes_count + unused_eips_count
        st.metric("Riscos de Custo", total_cost_risks)
    
    st.markdown("---")
    
    # Tabs para diferentes seções
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Overview", 
        "🏷️ Tagging Compliance",
        "💰 Cost Optimization",
        "🖥️ Instâncias",
        "📊 Análise por Tags",
        "📈 Relatórios"
    ])
    
    # TAB 1: Overview
    with tab1:
        st.header("Visão Geral")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Instâncias por Região")
            region_stats = {}
            for region_data in data.get('regions', []):
                region = region_data.get('region', 'unknown')
                instances = region_data.get('instances', {})
                region_stats[region] = {
                    'running': instances.get('running', 0),
                    'stopped': instances.get('stopped', 0),
                    'total': instances.get('total', 0)
                }
            
            if region_stats:
                # Criar DataFrame corretamente
                df_regions = pd.DataFrame([
                    {
                        'Região': region,
                        'Em Execução': stats['running'],
                        'Paradas': stats['stopped'],
                        'Total': stats['total']
                    }
                    for region, stats in region_stats.items()
                ])
                
                # Ordenar por total para melhor visualização
                df_regions = df_regions.sort_values('Total', ascending=False)
                
                fig = px.bar(
                    df_regions, 
                    x='Região', 
                    y=['Em Execução', 'Paradas'],
                    title="Distribuição de Instâncias por Região",
                    barmode='stack',
                    color_discrete_map={'Em Execução': '#00cc00', 'Paradas': '#ff4444'},
                    labels={'value': 'Quantidade', 'Região': 'Região AWS'}
                )
                # Rotacionar labels do eixo X para melhor visualização
                fig.update_xaxes(tickangle=-45)
                fig.update_layout(
                    xaxis_title="Região AWS",
                    yaxis_title="Quantidade de Instâncias",
                    legend_title="Status"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhuma região encontrada com instâncias.")
        
        with col2:
            st.subheader("Tipos de Instâncias")
            instance_types = {}
            for instance in all_instances:
                itype = instance.get('instance_type', 'unknown')
                instance_types[itype] = instance_types.get(itype, 0) + 1
            
            if instance_types:
                df_types = pd.DataFrame(list(instance_types.items()), columns=['Tipo', 'Quantidade'])
                df_types = df_types.sort_values('Quantidade', ascending=False).head(10)
                
                fig = px.pie(
                    df_types, 
                    values='Quantidade', 
                    names='Tipo',
                    title="Top 10 Tipos de Instâncias"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # TAB 2: Tagging Compliance
    with tab2:
        st.header("🏷️ Tagging Compliance")
        
        if all_untagged:
            st.markdown('<div class="warning-box">⚠️ Existem recursos sem tags obrigatórias!</div>', unsafe_allow_html=True)
            
            # Análise de tags ausentes
            missing_tags_analysis = {
                'Sem Name': [],
                'Sem Owner': [],
                'Sem CostCenter': [],
                'Sem Environment': []
            }
            
            for instance in all_instances:
                tags = instance.get('tags', {})
                if 'Name' not in tags or tags.get('Name') == 'N/A':
                    missing_tags_analysis['Sem Name'].append(instance)
                if 'owner' not in tags or tags.get('owner') == 'N/A':
                    missing_tags_analysis['Sem Owner'].append(instance)
                if 'CostCenter' not in tags or tags.get('CostCenter') == 'N/A':
                    missing_tags_analysis['Sem CostCenter'].append(instance)
                if 'Environment' not in tags or tags.get('Environment') == 'N/A':
                    missing_tags_analysis['Sem Environment'].append(instance)
            
            cols = st.columns(4)
            for idx, (tag_type, instances) in enumerate(missing_tags_analysis.items()):
                with cols[idx]:
                    st.metric(tag_type, len(instances))
            
            # Tabela de recursos não taggeados
            st.subheader("Recursos Sem Tags Obrigatórias")
            df_untagged = pd.DataFrame([
                {
                    'Instance ID': inst.get('instance_id', 'N/A'),
                    'Nome': inst.get('name', 'N/A'),
                    'Região': inst.get('region', 'N/A'),
                    'Estado': inst.get('state', 'N/A'),
                    'Tipo': inst.get('instance_type', 'N/A'),
                    'Name Tag': '❌' if inst.get('name') == 'N/A' else '✅',
                    'Owner Tag': '❌' if inst.get('owner') == 'N/A' else '✅',
                    'CostCenter Tag': '❌' if inst.get('cost_center') == 'N/A' else '✅',
                    'Environment Tag': '❌' if inst.get('environment') == 'N/A' else '✅'
                }
                for inst in all_untagged
            ])
            st.dataframe(df_untagged, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Todos os recursos estão devidamente taggeados!")
    
    # TAB 3: Cost Optimization
    with tab3:
        st.header("💰 Cost Optimization Opportunities")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🛑 Instâncias Paradas")
            if all_stopped:
                st.warning(f"⚠️ {len(all_stopped)} instâncias paradas encontradas")
                df_stopped = pd.DataFrame([
                    {
                        'Instance ID': inst.get('instance_id', 'N/A'),
                        'Nome': inst.get('name', 'N/A'),
                        'Região': inst.get('region', 'N/A'),
                        'Tipo': inst.get('instance_type', 'N/A'),
                        'Owner': inst.get('owner', 'N/A'),
                        'CostCenter': inst.get('cost_center', 'N/A'),
                        'Environment': inst.get('environment', 'N/A')
                    }
                    for inst in all_stopped
                ])
                st.dataframe(df_stopped, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Nenhuma instância parada encontrada")
        
        with col2:
            st.subheader("💾 Volumes Não Utilizados")
            if all_unused_volumes:
                total_size = sum(v.get('size', 0) for v in all_unused_volumes)
                st.warning(f"⚠️ {len(all_unused_volumes)} volumes não utilizados ({total_size} GB)")
                df_volumes = pd.DataFrame([
                    {
                        'Volume ID': vol.get('volume_id', 'N/A'),
                        'Região': vol.get('region', 'N/A'),
                        'Tamanho (GB)': vol.get('size', 0),
                        'Tipo': vol.get('volume_type', 'N/A')
                    }
                    for vol in all_unused_volumes
                ])
                st.dataframe(df_volumes, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Nenhum volume não utilizado encontrado")
        
        st.subheader("🌐 Elastic IPs Não Utilizados")
        if all_unused_eips:
            st.warning(f"⚠️ {len(all_unused_eips)} EIPs não utilizados")
            df_eips = pd.DataFrame([
                {
                    'Allocation ID': eip.get('allocation_id', 'N/A'),
                    'Public IP': eip.get('public_ip', 'N/A'),
                    'Região': eip.get('region', 'N/A')
                }
                for eip in all_unused_eips
            ])
            st.dataframe(df_eips, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Nenhum EIP não utilizado encontrado")
    
    # TAB 4: Instâncias
    with tab4:
        st.header("🖥️ Detalhes das Instâncias")
        
        # Filtros
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            selected_region = st.selectbox(
                "Filtrar por Região",
                ['Todas'] + list(set(inst.get('region') for inst in all_instances))
            )
        
        with col2:
            selected_state = st.selectbox(
                "Filtrar por Estado",
                ['Todos', 'running', 'stopped', 'terminated']
            )
        
        with col3:
            selected_environment = st.selectbox(
                "Filtrar por Environment",
                ['Todos'] + list(set(inst.get('environment') for inst in all_instances if inst.get('environment') != 'N/A'))
            )
        
        with col4:
            selected_owner = st.selectbox(
                "Filtrar por Owner",
                ['Todos'] + list(set(inst.get('owner') for inst in all_instances if inst.get('owner') != 'N/A'))
            )
        
        # Aplicar filtros
        filtered_instances = all_instances
        if selected_region != 'Todas':
            filtered_instances = [i for i in filtered_instances if i.get('region') == selected_region]
        if selected_state != 'Todos':
            filtered_instances = [i for i in filtered_instances if i.get('state') == selected_state]
        if selected_environment != 'Todos':
            filtered_instances = [i for i in filtered_instances if i.get('environment') == selected_environment]
        if selected_owner != 'Todos':
            filtered_instances = [i for i in filtered_instances if i.get('owner') == selected_owner]
        
        # Tabela de instâncias
        df_instances = pd.DataFrame([
            {
                'Instance ID': inst.get('instance_id', 'N/A'),
                'Nome': inst.get('name', 'N/A'),
                'Região': inst.get('region', 'N/A'),
                'Estado': inst.get('state', 'N/A'),
                'Tipo': inst.get('instance_type', 'N/A'),
                'OS': inst.get('os', inst.get('platform', 'N/A')),
                'Owner': inst.get('owner', 'N/A'),
                'CostCenter': inst.get('cost_center', 'N/A'),
                'Environment': inst.get('environment', 'N/A'),
                'VPC ID': inst.get('vpc_id', 'N/A'),
                'IP Privado': inst.get('private_ip', 'N/A'),
                'IP Público': inst.get('public_ip', 'N/A')
            }
            for inst in filtered_instances
        ])
        
        st.dataframe(df_instances, use_container_width=True, hide_index=True)
    
    # TAB 5: Análise por Tags
    with tab5:
        st.header("📊 Análise por Tags")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Distribuição por Environment")
            env_counts = {}
            for inst in all_instances:
                env = inst.get('environment', 'N/A')
                env_counts[env] = env_counts.get(env, 0) + 1
            
            if env_counts:
                df_env = pd.DataFrame(list(env_counts.items()), columns=['Environment', 'Quantidade'])
                fig = px.bar(df_env, x='Environment', y='Quantidade', 
                           title="Instâncias por Environment")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Distribuição por CostCenter")
            cc_counts = {}
            for inst in all_instances:
                cc = inst.get('cost_center', 'N/A')
                if cc == 'N/A' or cc == '':
                    cc = 'N/A'
                cc_counts[cc] = cc_counts.get(cc, 0) + 1
            
            if cc_counts:
                df_cc = pd.DataFrame(list(cc_counts.items()), columns=['CostCenter', 'Quantidade'])
                # Ordenar por quantidade de forma decrescente
                df_cc = df_cc.sort_values('Quantidade', ascending=False).head(10)
                # Converter CostCenter para string para garantir que os labels sejam exibidos corretamente
                df_cc['CostCenter'] = df_cc['CostCenter'].astype(str)
                fig = px.bar(
                    df_cc, 
                    x='CostCenter', 
                    y='Quantidade',
                    title="Top 10 CostCenters",
                    labels={'CostCenter': 'Cost Center', 'Quantidade': 'Quantidade de Instâncias'}
                )
                fig.update_xaxes(tickangle=-45)
                fig.update_layout(
                    xaxis_title="Cost Center",
                    yaxis_title="Quantidade de Instâncias"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhum CostCenter encontrado.")
        
        st.subheader("Distribuição por Owner")
        owner_counts = {}
        for inst in all_instances:
            owner = inst.get('owner', 'N/A')
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
        
        if owner_counts:
            df_owner = pd.DataFrame(list(owner_counts.items()), columns=['Owner', 'Quantidade'])
            df_owner = df_owner.sort_values('Quantidade', ascending=False)
            fig = px.pie(df_owner, values='Quantidade', names='Owner',
                        title="Instâncias por Owner")
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 6: Relatórios
    with tab6:
        st.header("📈 Relatórios e Exportação")
        
        # Resumo executivo
        st.subheader("Resumo Executivo")
        
        summary = {
            'Total de Instâncias': total_instances,
            'Instâncias em Execução': running_instances,
            'Instâncias Paradas': stopped_instances,
            'Recursos Não Taggeados': untagged_count,
            'Volumes Não Utilizados': len(all_unused_volumes),
            'EIPs Não Utilizados': len(all_unused_eips),
            'Total de Regiões': len(data.get('regions', []))
        }
        
        st.json(summary)
        
        # Exportar dados
        st.subheader("Exportar Dados")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Exportar CSV de Instâncias"):
                df_export = pd.DataFrame(all_instances)
                csv = df_export.to_csv(index=False)
                st.download_button(
                    label="Baixar CSV",
                    data=csv,
                    file_name=f"aws_instances_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📥 Exportar JSON Completo"):
                json_str = json.dumps(data, indent=2, default=str)
                st.download_button(
                    label="Baixar JSON",
                    data=json_str,
                    file_name=f"aws_finops_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main()
