import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import calendar
import altair as alt

# -------------------------------
# Conectar ao Google Sheets
# -------------------------------
@st.cache_resource
def conectar_planilha():
    escopo = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credenciais_original = st.secrets["gcp_service_account"]
    credenciais_dict = dict(credenciais_original)
    credenciais_dict["private_key"] = credenciais_dict["private_key"].replace('\\n', '\n')
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, escopo)
    cliente = gspread.authorize(creds)
    planilha = cliente.open("FinancasDomesticas")
    return planilha

# -------------------------------
# Carregar dados da planilha
# -------------------------------
def carregar_dados(aba):
    dados = aba.get_all_records()
    return pd.DataFrame(dados)

# -------------------------------
# Carregar categorias e subcategorias da aba 'Categorias'
# -------------------------------
@st.cache_data(ttl=60)
def carregar_categorias(_aba_categorias, tipo):
    dados = _aba_categorias.get_all_records()
    categorias_dict = {}
    for linha in dados:
        if linha.get('Tipo', '').strip().lower() == tipo.lower():
            cat = linha['Categoria'].strip()
            subcat = linha['Subcategoria'].strip() if linha['Subcategoria'] else ""
            if cat not in categorias_dict:
                categorias_dict[cat] = []
            if subcat and subcat not in categorias_dict[cat]:
                categorias_dict[cat].append(subcat)
    return categorias_dict

# -------------------------------
# Salvar nova transação
# -------------------------------
def salvar_transacao(aba, data, tipo, categoria, subcategoria, descricao, valor):
    aba.append_row([str(data), tipo, categoria, subcategoria, descricao, float(valor)])

# -------------------------------
# Adicionar categoria ou subcategoria na aba Categorias
# -------------------------------
def adicionar_categoria(aba_categorias, categoria, tipo_categoria):
    aba_categorias.append_row([categoria, "", tipo_categoria])

def adicionar_subcategoria(aba_categorias, categoria, subcategoria, tipo_categoria):
    aba_categorias.append_row([categoria, subcategoria, tipo_categoria])


# -------------------------------
# App Streamlit
# -------------------------------
st.set_page_config(page_title="Controle Financeiro Familiar", layout="centered")
st.title("💸 Controle Financeiro Familiar")

planilha = conectar_planilha()
aba_transacoes = planilha.sheet1
aba_categorias = planilha.worksheet("Categorias")

# Menu lateral
aba_atual = st.sidebar.radio("Escolha uma opção", ["Registrar", "Dashboard", "Gerenciar categorias"])

if aba_atual == "Registrar":
    st.header("📌 Adicionar transação")

    data = st.date_input("Data", value=date.today())
    st.write("Data selecionada:", data.strftime("%d/%m/%Y"))

    tipo = st.radio("Tipo", ["Receita", "Despesa"])

    categorias = carregar_categorias(aba_categorias, tipo)

    lista_categorias = [""] + list(categorias.keys())
    categoria = st.selectbox("Categoria", lista_categorias, index=0)

    if categoria:
        lista_subcategorias = [""] + categorias.get(categoria, [])
    else:
        lista_subcategorias = [""]

    subcategoria = st.selectbox("Subcategoria", lista_subcategorias, index=0)

    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", min_value=0.0, format="%.2f", value=0.0)

    if st.button("Salvar"):
        if descricao and valor > 0 and categoria and subcategoria:
            salvar_transacao(aba_transacoes, data, tipo, categoria, subcategoria, descricao, valor)
            st.success("Transação registrada com sucesso!")
        else:
            st.error("Preencha todos os campos antes de salvar.")

elif aba_atual == "Dashboard":
    st.header("📊 Visão Geral")
    df = carregar_dados(aba_transacoes)

    if df.empty:
        st.warning("Nenhuma transação registrada ainda.")
    else:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Data'])
        df['Ano'] = df['Data'].dt.year
        df['Mês'] = df['Data'].dt.month

        nomes_meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        df['Nome Mês'] = df['Mês'].map(nomes_meses_pt)
        df['Valor'] = pd.to_numeric(df['Valor'])

        anos = sorted(df['Ano'].unique(), reverse=True)
        meses_disponiveis = sorted(df['Mês'].unique())
        nomes_meses_disponiveis = [nomes_meses_pt[m] for m in meses_disponiveis]

        with st.expander("🔍 Filtros"):
            col1, col2, col3 = st.columns([3, 3, 2])
            with col1:
                if 'ano_filtro' not in st.session_state:
                    st.session_state['ano_filtro'] = 'Todos'
                ano_filtro = st.selectbox("Ano", ['Todos'] + anos, index=0, key="ano_filtro")

            with col2:
                if 'mes_filtro' not in st.session_state:
                    st.session_state['mes_filtro'] = 'Todos'
                mes_filtro = st.selectbox("Mês", ['Todos'] + nomes_meses_disponiveis, index=0, key="mes_filtro")

            with col3:
                st.write("")
                if st.button("❌ Limpar filtros"):
                    st.session_state['ano_filtro'] = 'Todos'
                    st.session_state['mes_filtro'] = 'Todos'
                    st.experimental_rerun()

        df_filtrado = df.copy()
        if st.session_state['ano_filtro'] != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Ano'] == st.session_state['ano_filtro']]
        if st.session_state['mes_filtro'] != 'Todos':
            num_mes = [k for k, v in nomes_meses_pt.items() if v == st.session_state['mes_filtro']]
            if num_mes:
                df_filtrado = df_filtrado[df_filtrado['Mês'] == num_mes[0]]
            else:
                df_filtrado = pd.DataFrame(columns=df.columns)

        st.subheader("📌 Visão Geral")
        if not df_filtrado.empty:
            total_receitas = df_filtrado[df_filtrado['Tipo'] == 'Receita']['Valor'].sum()
            total_despesas = df_filtrado[df_filtrado['Tipo'] == 'Despesa']['Valor'].sum()
            saldo = total_receitas - total_despesas

            col1, col2, col3 = st.columns(3)
            col1.metric("Receitas", f"R$ {total_receitas:,.2f}")
            col2.metric("Despesas", f"R$ {total_despesas:,.2f}")
            col3.metric("Saldo", f"R$ {saldo:,.2f}")
        else:
            st.info("Sem dados para o filtro selecionado.")
            total_receitas = 0
            total_despesas = 0
            saldo = 0

        st.divider()

        st.subheader("💰 Receitas por Categoria")
        receitas_cat = df_filtrado[df_filtrado['Tipo'] == 'Receita'].groupby("Categoria")["Valor"].sum().reset_index()
        if not receitas_cat.empty:
            chart_receitas = alt.Chart(receitas_cat).mark_bar(color='green').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Categoria:N", sort='-x'),
                tooltip=["Categoria", alt.Tooltip("Valor", format=".2f")]
            ).properties(height=300)
            st.altair_chart(chart_receitas, use_container_width=True)
        else:
            st.info("Sem receitas para este filtro.")

        st.subheader("💸 Despesas por Categoria")
        despesas_cat = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby("Categoria")["Valor"].sum().reset_index()
        if not despesas_cat.empty:
            chart_despesas = alt.Chart(despesas_cat).mark_bar(color='red').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Categoria:N", sort='-x'),
                tooltip=["Categoria", alt.Tooltip("Valor", format=".2f")]
            ).properties(height=300)
            st.altair_chart(chart_despesas, use_container_width=True)
        else:
            st.info("Sem despesas para este filtro.")

        st.divider()

        st.subheader("📂 Receitas por Subcategoria")
        receitas_sub = df_filtrado[df_filtrado['Tipo'] == 'Receita'].groupby("Subcategoria")["Valor"].sum().reset_index()
        if not receitas_sub.empty:
            chart_sub_receitas = alt.Chart(receitas_sub).mark_bar(color='green').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Subcategoria:N", sort='-x'),
                tooltip=["Subcategoria", alt.Tooltip("Valor", format=".2f")]
            ).properties(height=300)
            st.altair_chart(chart_sub_receitas, use_container_width=True)
        else:
            st.info("Sem subcategorias de receita para este filtro.")

        st.subheader("📂 Despesas por Subcategoria")
        despesas_sub = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby("Subcategoria")["Valor"].sum().reset_index()
        if not despesas_sub.empty:
            chart_sub_despesas = alt.Chart(despesas_sub).mark_bar(color='red').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Subcategoria:N", sort='-x'),
                tooltip=["Subcategoria", alt.Tooltip("Valor", format=".2f")]
            ).properties(height=300)
            st.altair_chart(chart_sub_despesas, use_container_width=True)
        else:
            st.info("Sem subcategorias de despesa para este filtro.")

        st.divider()

        st.subheader("📋 Todas as Movimentações")
        if not df_filtrado.empty:
            colunas_tabela = ['Data', 'Tipo', 'Categoria', 'Subcategoria', 'Descrição', 'Valor']
            df_exibicao = df_filtrado[colunas_tabela].copy()
            df_exibicao['Data'] = df_exibicao['Data'].dt.strftime("%d/%m/%Y")
            df_exibicao['Valor'] = df_exibicao['Valor'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhuma movimentação para este filtro.")

elif aba_atual == "Gerenciar categorias":
    st.header("🛠 Gerenciar Categorias e Subcategorias")

    tipo_categoria = st.radio("Tipo de categoria", ["Receita", "Despesa"], horizontal=True)

    categorias = carregar_categorias(_aba_categorias=aba_categorias, tipo=tipo_categoria)

    st.subheader("➕ Adicionar Categoria")
    nova_categoria = st.text_input("Nova Categoria", key="cat_input")
    if st.button("Adicionar Categoria"):
        nova_categoria = nova_categoria.strip()
        if nova_categoria:
            if nova_categoria not in categorias:
                adicionar_categoria(aba_categorias, nova_categoria, tipo_categoria)
                st.success(f"Categoria '{nova_categoria}' adicionada como {tipo_categoria}!")
                st.experimental_rerun()
            else:
                st.error("Categoria já existe para este tipo.")
        else:
            st.error("Digite uma categoria válida.")

    st.markdown("---")

    st.subheader("➕ Adicionar Subcategoria")
    if categorias:
        categoria_para_sub = st.selectbox(
            "Selecione Categoria para nova Subcategoria",
            list(categorias.keys()),
            key="subcat_select"
        )
        nova_subcategoria = st.text_input("Nova Subcategoria", key="subcat_input")
        if st.button("Adicionar Subcategoria"):
            nova_subcategoria = nova_subcategoria.strip()
            if nova_subcategoria:
                if nova_subcategoria not in categorias[categoria_para_sub]:
                    adicionar_subcategoria(aba_categorias, categoria_para_sub, nova_subcategoria, tipo_categoria)
                    st.success(f"Subcategoria '{nova_subcategoria}' adicionada à categoria '{categoria_para_sub}'!")
                    st.experimental_rerun()
                else:
                    st.error("Subcategoria já existe para essa categoria.")
            else:
                st.error("Digite uma subcategoria válida.")
    else:
        st.info("Não há categorias para adicionar subcategoria. Adicione uma categoria primeiro.")
