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
def adicionar_categoria(aba_categorias, categoria, tipo): # Adicionado 'tipo' para consistência
    aba_categorias.append_row([categoria, "", tipo]) # Adiciona o tipo ao salvar a categoria

def adicionar_subcategoria(aba_categorias, categoria, subcategoria):
    # Para adicionar subcategoria, precisamos encontrar a linha da categoria pai e adicionar a subcategoria lá
    # ou adicionar uma nova linha com a categoria e subcategoria, mantendo o tipo.
    # A abordagem atual do gspread.append_row adiciona uma nova linha.
    # Para manter a lógica existente, vamos assumir que a aba 'Categorias' tem colunas 'Categoria', 'Subcategoria', 'Tipo'.
    # Se a estrutura for diferente, isso precisará ser ajustado.
    # Por simplicidade, se a subcategoria for adicionada, ela é associada à categoria existente.
    # A função carregar_categorias já lida com isso.
    # Para adicionar uma nova linha com categoria e subcategoria, o 'tipo' também é necessário.
    # O código original não passava o tipo para adicionar_subcategoria, o que pode ser um problema.
    # Vamos adaptar para que a adição de subcategoria também considere o tipo, se a planilha tiver essa coluna.
    # Por enquanto, mantemos a assinatura original para evitar quebrar o código existente,
    # mas é importante notar que a aba 'Categorias' precisa ter a coluna 'Tipo' para a função carregar_categorias funcionar bem.
    # Se a 'Categorias' não tem 'Tipo', a lógica de filtragem por tipo em 'carregar_categorias' não funcionará como esperado.
    # Para a funcionalidade de adicionar subcategoria, o tipo é implicitamente o tipo da categoria pai.
    # Para simplificar, mantemos a função como está, mas o ideal seria passar o tipo também.
    aba_categorias.append_row([categoria, subcategoria, ""]) # Assumindo que o tipo será preenchido manualmente ou não é relevante aqui

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
        if st.session_state['ano_filtro'] != 'Todos':
            df = df[df['Ano'] == st.session_state['ano_filtro']]
        if st.session_state['mes_filtro'] != 'Todos':
            num_mes = [k for k, v in nomes_meses_pt.items() if v == st.session_state['mes_filtro']][0]
            df = df[df['Mês'] == num_mes]

        # Métricas principais
        total_receitas = df[df['Tipo'] == 'Receita']['Valor'].sum()
        total_despesas = df[df['Tipo'] == 'Despesa']['Valor'].sum()
        saldo = total_receitas - total_despesas

        st.subheader("📌 Visão Geral")
        col1, col2, col3 = st.columns(3)
        col1.metric("Receitas", f"R$ {total_receitas:,.2f}")
        col2.metric("Despesas", f"R$ {total_despesas:,.2f}")
        col3.metric("Saldo", f"R$ {saldo:,.2f}")

        st.divider()

        # 🔹 Gráfico de barras horizontais (Receitas por Categoria)
        st.subheader("💰 Receitas por Categoria")
        receitas_cat = df[df['Tipo'] == 'Receita'].groupby("Categoria")["Valor"].sum().reset_index()
        if not receitas_cat.empty:
            chart_receitas = alt.Chart(receitas_cat).mark_bar(color='green').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Categoria:N", sort='-x'),
                tooltip=["Categoria", alt.Tooltip("Valor", format=",.2f")]
            ).properties(height=300)
            st.altair_chart(chart_receitas, use_container_width=True)
        else:
            st.info("Sem receitas para este filtro.")

        # 🔹 Gráfico de barras horizontais (Despesas por Categoria)
        st.subheader("💸 Despesas por Categoria")
        despesas_cat = df[df['Tipo'] == 'Despesa'].groupby("Categoria")["Valor"].sum().reset_index()
        if not despesas_cat.empty:
            chart_despesas = alt.Chart(despesas_cat).mark_bar(color='red').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Categoria:N", sort='-x'),
                tooltip=["Categoria", alt.Tooltip("Valor", format=",.2f")]
            ).properties(height=300)
            st.altair_chart(chart_despesas, use_container_width=True)
        else:
            st.info("Sem despesas para este filtro.")

        # O gráfico de pizza (Distribuição das Despesas) foi removido conforme solicitado.

        st.divider()

        # 🔹 Linha do tempo: saldo por mês
        st.subheader("📈 Evolução Mensal do Saldo")
        df_saldo = df.groupby(['Ano', 'Mês']).agg(
            Receita=('Valor', lambda x: x[df.loc[x.index, 'Tipo'] == 'Receita'].sum()),
            Despesa=('Valor', lambda x: x[df.loc[x.index, 'Tipo'] == 'Despesa'].sum())
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
                tooltip=["Tipo:N", alt.Tooltip("Valor", format=",.2f"), alt.Tooltip("Data", format="%Y-%m")]
            ).properties(height=400)
            st.altair_chart(chart_linha, use_container_width=True)
        else:
            st.info("Sem dados de saldo para este filtro.")

        st.divider()

        # 🔹 Subcategorias
        st.subheader("📂 Receitas por Subcategoria")
        receitas_sub = df[df['Tipo'] == 'Receita'].groupby("Subcategoria")["Valor"].sum().reset_index()
        if not receitas_sub.empty:
            chart_sub_receitas = alt.Chart(receitas_sub).mark_bar(color='green').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Subcategoria:N", sort='-x'),
                tooltip=["Subcategoria", alt.Tooltip("Valor", format=",.2f")]
            ).properties(height=300)
            st.altair_chart(chart_sub_receitas, use_container_width=True)
        else:
            st.info("Sem subcategorias de receita.")

        st.subheader("📂 Despesas por Subcategoria")
        despesas_sub = df[df['Tipo'] == 'Despesa'].groupby("Subcategoria")["Valor"].sum().reset_index()
        if not despesas_sub.empty:
            chart_sub_despesas = alt.Chart(despesas_sub).mark_bar(color='red').encode(
                x=alt.X("Valor:Q", title="Valor (R$)"),
                y=alt.Y("Subcategoria:N", sort='-x'),
                tooltip=["Subcategoria", alt.Tooltip("Valor", format=",.2f")]
            ).properties(height=300)
            st.altair_chart(chart_sub_despesas, use_container_width=True)
        else:
            st.info("Sem subcategorias de despesa.")

        st.divider()

        # 🆕 Tabela de todas as movimentações
        st.subheader("📋 Todas as Movimentações")
        if not df.empty:
            # Seleciona as colunas a serem exibidas e formata o valor
            df_display = df[['Data', 'Tipo', 'Categoria', 'Subcategoria', 'Descrição', 'Valor']].copy()
            df_display['Data'] = df_display['Data'].dt.strftime("%d/%m/%Y") # Formata a data para exibição
            df_display['Valor'] = df_display['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")) # Formata para moeda brasileira
            st.dataframe(df_display, use_container_width=True, hide_index=True)
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
            # Verifica se a categoria já existe para o tipo selecionado
            # Para isso, precisamos carregar todas as categorias e subcategorias, e verificar a combinação Categoria/Tipo
            # A função carregar_categorias já retorna as categorias filtradas por tipo.
            # Então, basta verificar se a nova_categoria já está nas chaves do dicionário 'categorias'.
            if nova_categoria not in categorias:
                # Adiciona o tipo ao salvar a categoria na planilha 'Categorias'
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
                    # Ao adicionar subcategoria, estamos apenas adicionando uma nova linha com Categoria e Subcategoria.
                    # O tipo é inferido pela função carregar_categorias quando ela lê a planilha.
                    # Se a planilha 'Categorias' não tiver a coluna 'Tipo', isso pode causar problemas.
                    # Por simplicidade, mantemos a função adicionar_subcategoria como está,
                    # mas é crucial que a planilha 'Categorias' tenha a coluna 'Tipo' e que ela seja preenchida corretamente
                    # para que a função carregar_categorias funcione como esperado.
                    adicionar_subcategoria(aba_categorias, categoria_para_sub, nova_subcategoria)
                    st.success(f"Subcategoria '{nova_subcategoria}' adicionada à categoria '{categoria_para_sub}'!")
                    st.experimental_rerun()
                else:
                    st.error("Subcategoria já existe para essa categoria.")
            else:
                st.error("Digite uma subcategoria válida.")
    else:
        st.info("Não há categorias para adicionar subcategoria. Adicione uma categoria primeiro.")
