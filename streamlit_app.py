import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import calendar

# -------------------------------
# Conectar ao Google Sheets
# -------------------------------
@st.cache_resource
def conectar_planilha():
    escopo = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

    credenciais_original = st.secrets["gcp_service_account"]
    # Faz uma cópia do dicionário para modificar
    credenciais_dict = dict(credenciais_original)

    # Agora pode substituir os \n na private_key sem erro
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
def adicionar_categoria(aba_categorias, categoria):
    aba_categorias.append_row([categoria, ""])

def adicionar_subcategoria(aba_categorias, categoria, subcategoria):
    aba_categorias.append_row([categoria, subcategoria])

# -------------------------------
# App Streamlit
# -------------------------------
st.set_page_config(page_title="Controle Financeiro Familiar", layout="centered")
st.title("💸 Controle Financeiro Familiar")

planilha = conectar_planilha()
aba_transacoes = planilha.sheet1
# Note que aba_categorias só será usada para operações de escrita, pode ser obtida aqui
aba_categorias = planilha.worksheet("Categorias")

# Menu lateral
aba_atual = st.sidebar.radio("Escolha uma opção", ["Registrar", "Dashboard", "Gerenciar categorias"])

if aba_atual == "Registrar":
    st.header("📌 Adicionar transação")

    data = st.date_input("Data", value=date.today())
    st.write("Data selecionada:", data.strftime("%d/%m/%Y"))

    tipo = st.radio("Tipo", ["Receita", "Despesa"])

    # Agora carrega as categorias com base no tipo
    categorias = carregar_categorias(aba_categorias, tipo)

    # Adicionando opção vazia no selectbox de categoria
    lista_categorias = [""] + list(categorias.keys())
    categoria = st.selectbox("Categoria", lista_categorias, index=0)

    # Se categoria estiver vazia, subcategoria também fica vazia
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
        df['Valor'] = pd.to_numeric(df['Valor'])
        df['Data'] = pd.to_datetime(df['Data'])

        df['Ano'] = df['Data'].dt.year
        df['Mês'] = df['Data'].dt.month
        df['Nome_Mês'] = df['Data'].dt.month.apply(lambda m: calendar.month_name[m])

        anos_disponiveis = sorted(df['Ano'].unique(), reverse=True)
        meses_disponiveis = sorted(df['Mês'].unique())
        nomes_meses = ['Todos os meses'] + [calendar.month_name[m] for m in meses_disponiveis]

        st.subheader("🎯 Filtros")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            ano_selecionado = st.selectbox("Ano", anos_disponiveis, key="filtro_ano")
        with col2:
            mes_nome_selecionado = st.selectbox("Mês", nomes_meses, index=0, key="filtro_mes")

        with col3:
            if st.button("🔄 Limpar Filtros"):
                st.experimental_rerun()

        # Aplicar filtro
        if mes_nome_selecionado != "Todos os meses":
            mes_num = list(calendar.month_name).index(mes_nome_selecionado)
            df_filtrado = df[(df['Ano'] == ano_selecionado) & (df['Mês'] == mes_num)]
        else:
            df_filtrado = df[df['Ano'] == ano_selecionado]

        if df_filtrado.empty:
            st.warning("Não há transações para os filtros selecionados.")
        else:
            total_receitas = df_filtrado[df_filtrado['Tipo'] == 'Receita']['Valor'].sum()
            total_despesas = df_filtrado[df_filtrado['Tipo'] == 'Despesa']['Valor'].sum()
            saldo = total_receitas - total_despesas

            st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}")
            st.metric("Total de Despesas", f"R$ {total_despesas:,.2f}")
            st.metric("Saldo no Período", f"R$ {saldo:,.2f}")

            st.markdown("### 📈 Gráficos de Receitas e Despesas")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("💰 Receitas por Categoria")
                receitas_cat = df_filtrado[df_filtrado['Tipo'] == 'Receita'].groupby("Categoria")["Valor"].sum()
                st.bar_chart(receitas_cat)

            with col2:
                st.subheader("💸 Despesas por Categoria")
                despesas_cat = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby("Categoria")["Valor"].sum()
                st.bar_chart(despesas_cat)

            st.subheader("🔍 Despesas por Subcategoria")
            despesas_sub = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby("Subcategoria")["Valor"].sum()
            st.bar_chart(despesas_sub)

elif aba_atual == "Gerenciar categorias":
    st.header("🛠 Gerenciar Categorias e Subcategorias")

    tipo_categoria = st.radio("Tipo de categoria", ["Receita", "Despesa"], horizontal=True)

    # Carrega as categorias com base no tipo selecionado
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
                st.error("Categoria já existe.")
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
                    adicionar_subcategoria(aba_categorias, categoria_para_sub, nova_subcategoria)
                    st.success(f"Subcategoria '{nova_subcategoria}' adicionada à categoria '{categoria_para_sub}'!")
                    st.experimental_rerun()
                else:
                    st.error("Subcategoria já existe para essa categoria.")
            else:
                st.error("Digite uma subcategoria válida.")
    else:
        st.info("Não há categorias para adicionar subcategoria. Adicione uma categoria primeiro.")

