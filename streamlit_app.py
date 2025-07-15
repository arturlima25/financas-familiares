import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

# -------------------------------
# Conectar ao Google Sheets
# -------------------------------
@st.cache_resource
def conectar_sheets():
    escopo = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', escopo)
    cliente = gspread.authorize(creds)
    planilha = cliente.open("FinancasDomesticas")
    aba = planilha.sheet1
    return aba

# -------------------------------
# Carregar dados da planilha
# -------------------------------
def carregar_dados(aba):
    dados = aba.get_all_records()
    return pd.DataFrame(dados)

# -------------------------------
# Salvar nova transação
# -------------------------------
def salvar_transacao(aba, data, tipo, categoria, subcategoria, descricao, valor):
    aba.append_row([str(data), tipo, categoria, subcategoria, descricao, float(valor)])

# -------------------------------
# App Streamlit
# -------------------------------
st.set_page_config(page_title="Controle Financeiro Familiar", layout="centered")
st.title("💸 Controle Financeiro Familiar")

aba_atual = st.sidebar.radio("Escolha uma opção", ["Registrar", "Dashboard"])
sheet = conectar_sheets()

# Categorias e Subcategorias
categorias = {
    "Alimentação": ["Supermercado", "Restaurante", "Delivery"],
    "Transporte": ["Combustível", "Uber", "Manutenção"],
    "Moradia": ["Aluguel", "Energia", "Internet"],
    "Salário": ["Mensal", "Freelance"],
    "Lazer": ["Cinema", "Viagem", "Assinaturas"],
    "Outros": ["Farmácia", "Presentes", "Vestuário"]
}

if aba_atual == "Registrar":
    st.header("📌 Adicionar transação")

    data = st.date_input("Data", value=date.today())
    tipo = st.radio("Tipo", ["Receita", "Despesa"])
    categoria = st.selectbox("Categoria", list(categorias.keys()))
    subcategoria = st.selectbox("Subcategoria", categorias[categoria])
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", min_value=0.0, format="%.2f")

    if st.button("Salvar"):
        if descricao and valor > 0:
            salvar_transacao(sheet, data, tipo, categoria, subcategoria, descricao, valor)
            st.success("Transação registrada com sucesso!")
        else:
            st.error("Preencha todos os campos antes de salvar.")

elif aba_atual == "Dashboard":
    st.header("📊 Visão Geral")
    df = carregar_dados(sheet)

    if df.empty:
        st.warning("Nenhuma transação registrada ainda.")
    else:
        df['Valor'] = pd.to_numeric(df['Valor'])
        total_receitas = df[df['Tipo'] == 'Receita']['Valor'].sum()
        total_despesas = df[df['Tipo'] == 'Despesa']['Valor'].sum()
        saldo = total_receitas - total_despesas

        st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}")
        st.metric("Total de Despesas", f"R$ {total_despesas:,.2f}")
        st.metric("Saldo Atual", f"R$ {saldo:,.2f}")

        st.subheader("💡 Despesas por Categoria")
        despesas_cat = df[df['Tipo'] == 'Despesa'].groupby("Categoria")["Valor"].sum()
        st.bar_chart(despesas_cat)

        st.subheader("📂 Despesas por Subcategoria")
        despesas_sub = df[df['Tipo'] == 'Despesa'].groupby("Subcategoria")["Valor"].sum()
        st.bar_chart(despesas_sub)
