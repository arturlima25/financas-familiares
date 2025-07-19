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
        # Prepara os dados
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

        # Filtros
        anos = sorted(df['Ano'].unique())
        meses = sorted(df['Mês'].unique())
        with st.expander("🔍 Filtros"):
            col1, col2, col3 = st.columns([3, 3, 2])
            with col1:
                ano_filtro = st.selectbox("Ano", ['Todos'] + anos, index=0, key="ano_filtro")
            with col2:
                nomes_meses = ['Todos'] + [nomes_meses_pt[m] for m in meses]
                mes_filtro = st.selectbox("Mês", nomes_meses, index=0, key="mes_filtro")
            with col3:
                if st.button("❌ Limpar filtros"):
                    st.session_state['ano_filtro'] = 'Todos'
                    st.session_state['mes_filtro'] = 'Todos'
                    st.experimental_rerun()

        # Aplicar filtros
        df_filtrado = df.copy() # Criar uma cópia para aplicar filtros e manter o df original
        if st.session_state['ano_filtro'] != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Ano'] == st.session_state['ano_filtro']]
        if st.session_state['mes_filtro'] != 'Todos':
            num_mes = [k for k, v in nomes_meses_pt.items() if v == st.session_state['mes_filtro']][0]
            df_filtrado = df_filtrado[df_filtrado['Mês'] == num_mes]

        # Métricas principais
        total_receitas = df_filtrado[df_filtrado['Tipo'] == 'Receita']['Valor'].sum()
        total_despesas = df_filtrado[df_filtrado['Tipo'] == 'Despesa']['Valor'].sum()
        saldo = total_receitas - total_despesas

        st.subheader("📌 Visão Geral")
        col1, col2, col3 = st.columns(3)
        col1.metric("Receitas", f"R$ {total_receitas:,.2f}")
        col2.metric("Despesas", f"R$ {total_despesas:,.2f}")
        col3.metric("Saldo", f"R$ {saldo:,.2f}")

        st.divider()

        # 🔹 Gráfico de barras horizontais (Receitas por Categoria)
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

        # 🔹 Gráfico de barras horizontais (Despesas por Categoria)
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

        # 🔹 Linha do tempo: saldo por mês
        st.subheader("📈 Evolução Mensal do Saldo")
        df_saldo = df_filtrado.groupby(['Ano', 'Mês']).agg(
            Receita=('Valor', lambda x: x[df_filtrado.loc[x.index, 'Tipo'] == 'Receita'].sum()),
            Despesa=('Valor', lambda x: x[df_filtrado.loc[x.index, 'Tipo'] == 'Despesa'].sum())
        ).reset_index()
        df_saldo['Saldo'] = df_saldo['Receita'] - df_saldo['Despesa']
        df_saldo['Data'] = pd.to_datetime(df_saldo.rename(columns={'Ano':'year', 'Mês':'month'}).assign(day=1)[['year','month','day']])

        if not df_saldo.empty:
            chart_linha = alt.Chart(df_saldo).transform_fold(
                ['Receita', 'Despesa', 'Saldo'],
                as_=['Tipo', 'Valor']
            ).mark_line(point=True).encode(
                x=alt.X('Data:T', title='Data'),
                y=alt.Y('Valor:Q', title='Valor (R$)'),
                color='Tipo:N',
                tooltip=["Tipo:N", alt.Tooltip("Valor", format=".2f"), "Data:T"]
            ).properties(height=400)
            st.altair_chart(chart_linha, use_container_width=True)
        else:
            st.info("Sem dados de saldo para este filtro.")

        st.divider()

        # 🔹 Subcategorias
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

        # 🔹 Tabela de Todas as Movimentações
        st.subheader("📋 Todas as Movimentações")
        if not df_filtrado.empty:
            # Selecionar e reordenar as colunas para a exibição na tabela
            colunas_tabela = ['Data', 'Tipo', 'Categoria', 'Subcategoria', 'Descrição', 'Valor']
            df_exibicao = df_filtrado[colunas_tabela].copy()
            df_exibicao['Data'] = df_exibicao['Data'].dt.strftime("%d/%m/%Y")
            df_exibicao['Valor'] = df_exibicao['Valor'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_exibicao, hide_index=True)
        else:
            st.info("Nenhuma movimentação para este filtro.")


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
            # Certificar-se de que a coluna 'Tipo' existe na planilha 'Categorias'
            # Isso requer uma pequena modificação na sua planilha Google Sheets,
            # adicionando uma coluna 'Tipo' (Receita/Despesa)
            # Para o código funcionar corretamente, sua planilha 'Categorias' deve ter as colunas: Categoria, Subcategoria, Tipo
            adicionar_categoria(aba_categorias, nova_categoria, tipo_categoria)
            st.success(f"Categoria '{nova_categoria}' adicionada como {tipo_categoria}!")
            st.experimental_rerun()
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
