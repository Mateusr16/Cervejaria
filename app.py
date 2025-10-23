from flask import Flask, render_template, request, flash, redirect, url_for, jsonify  
from decimal import Decimal
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import os
import re

GARRAFAS_POR_LITRO = 3710 / 1000 

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_flash'

app.config['SQLALCHEMY_DATABASE_URI'] = (
    "postgresql+psycopg2://cerverja_user:NWDyp8cbprya0crqXKAyKryVApxH2KIU"
    "@dpg-d3tbaofdiees73ddeiu0-a.oregon-postgres.render.com:5432/cerverja"
    "?sslmode=require"
)

db = SQLAlchemy(app)


RECEITAS = {
    "Pilsen": {
        "Malte Pilsen": 200,
        "Lúpulo": 2.5,
        "Levedura": 1.5,
        "Água Mineral": 1000
    },
    "IPA": {
        "Malte Pale Ale": 220,
        "Malte Caramelo": 20,
        "Lúpulo": 8,
        "Levedura": 2,
        "Água Mineral": 1000
    },
    "Stout": {
        "Malte Pale Ale": 200,
        "Malte Torrado": 15,
        "Malte Caramelo": 10,
        "Cevada em Flocos": 10,
        "Lúpulo": 2.5,
        "Levedura": 2,
        "Água Mineral": 1000
    }
}


# Adicione após as definições existentes de modelos
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    custo = db.Column(db.Numeric(10,2), nullable=False)
    venda = db.Column(db.Numeric(10,2), nullable=False)

class Desconto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    valor_minimo = db.Column(db.Numeric(10,2), unique=True, nullable=False)
    percentual = db.Column(db.Numeric(5,2), nullable=False)

class TaxaEntrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estados = db.Column(db.String(50), unique=True, nullable=False)
    taxa = db.Column(db.Numeric(5,2), nullable=False)

# Definição do modelo do banco de dados para os pedidos
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_pedido = db.Column(db.String, unique=True, nullable=True)
    data = db.Column(db.String(20), nullable=False)  # Aumentado para incluir hora
    cliente = db.Column(db.String(80), nullable=False)
    vendedor = db.Column(db.String(80), nullable=False)
    cidade_estado = db.Column(db.String(100), nullable=False)
    subtotal = db.Column(db.String(20), nullable=False)
    desconto_pct = db.Column(db.String(20), nullable=False)
    desconto_val = db.Column(db.String(20), nullable=False)
    entrega_pct = db.Column(db.String(20), nullable=False)
    entrega_val = db.Column(db.String(20), nullable=False)
    valor_total = db.Column(db.String(20), nullable=False)  # Mantido para compatibilidade
    itens = db.relationship('ItemPedido', backref='pedido', lazy=True)


class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.String(20), nullable=False)
    valor_item = db.Column(db.String(20), nullable=False)
    custo_unitario = db.Column(db.String(20), nullable=True)  # Novo campo para o custo histórico
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)

class Producao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lote = db.Column(db.String(50), nullable=False)
    tipo_cerveja = db.Column(db.String(50), nullable=False)
    inicio_producao = db.Column(db.Date, nullable=False)
    fim_producao = db.Column(db.Date, nullable=False)
    maquina_utilizada = db.Column(db.String(50), nullable=False)
    quantidade_produzida_litros = db.Column(db.Integer, nullable=False, default=1000)
    entrada_confirmada = db.Column(db.Boolean, default=False)

class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    produto = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    tipo_movimentacao = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.String(200), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    ultima_compra = db.Column(db.DateTime)

class MovimentoMP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nf = db.Column(db.String(50))
    data = db.Column(db.DateTime, default=datetime.now)
    produto = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    fornecedor = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Numeric(10,2), nullable=False)
    responsavel = db.Column(db.String(50), nullable=False, default='Sistema')
    tipo_movimentacao = db.Column(db.String(20), nullable=False, default='entrada') 

class EstoqueMinimo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(50), unique=True, nullable=False)
    minimo = db.Column(db.Float, nullable=False, default=100.0)

class RegistroFinanceiro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    total_vendas = db.Column(db.Numeric(10,2), default=0)
    custo_materia_prima = db.Column(db.Numeric(10,2), default=0)
    custo_transporte = db.Column(db.Numeric(10,2), default=0)
    litros_produzidos = db.Column(db.Integer, default=0)
    numero_entregas = db.Column(db.Integer, default=0)
    data_registro = db.Column(db.DateTime, default=datetime.now)

def calcular_valor_total(quantidades, estado):
    produtos = {p.nome: p for p in Produto.query.all()}
    descontos_db = {d.valor_minimo: d.percentual for d in Desconto.query.order_by(Desconto.valor_minimo).all()}
    taxas = {t.estados: t.taxa for t in TaxaEntrega.query.all()}
    estoque_atual = {
        'pilsen': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                     for e in Estoque.query.filter_by(produto='pilsen').all()]),
        'ipa': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                  for e in Estoque.query.filter_by(produto='ipa').all()]),
        'stout': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                    for e in Estoque.query.filter_by(produto='stout').all()])
    }

    for tipo, quantidade_str in quantidades.items():
        if quantidade_str:
            quantidade = int(quantidade_str)
            if quantidade > estoque_atual[tipo]:
                flash(f"Estoque insuficiente de {tipo.capitalize()}. Disponível: {estoque_atual[tipo]}", 'error')
                return None
    
    total_sem_desconto = Decimal('0.00')
    for tipo, quantidade_str in quantidades.items():
        if quantidade_str and produtos.get(tipo):
            try:
                quantidade = int(quantidade_str)
                total_sem_desconto += quantidade * produtos[tipo].venda
            except ValueError:
                flash(f"Quantidade inválida para {tipo}.", 'error')
                return None

    desconto_percentual = 0
    for limite in sorted(descontos_db.keys(), reverse=True):
        if total_sem_desconto > limite:
            desconto_percentual = descontos_db[limite]
            break

    valor_desconto = total_sem_desconto * (Decimal(desconto_percentual) / 100)
    valor_com_desconto = total_sem_desconto - valor_desconto

    adicional_percentual = 0
    estado_uf = estado.strip().upper()
    for estados, taxa in taxas.items():
        # Permitir múltiplos estados separados por vírgula
        estados_lista = [e.strip().upper() for e in estados.split(',')]
        if estado_uf in estados_lista:
            adicional_percentual = taxa
            break

    valor_adicional = valor_com_desconto * (Decimal(adicional_percentual) / 100)
    valor_final = valor_com_desconto + valor_adicional
    
    return (
        total_sem_desconto,
        desconto_percentual,
        valor_desconto,
        adicional_percentual,
        valor_adicional,
        valor_final
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    total_vendas, porcentagem = calcular_vendas_mensais()
    clientes_ativos, variacao_clientes, porcent_clientes = calcular_clientes_ativos()
    top_cervejas = calcular_vendas_mensais_cervejas()
    if request.method == 'POST':
        nome = request.form['nome']
        cidade = request.form['cidade']
        estado = request.form['estado']
        vendedor = request.form['vendedor']
        quantidades = {
            "pilsen": request.form['pilsen'],
            "ipa": request.form['ipa'],
            "stout": request.form['stout']
        }

        if not nome or not cidade or not estado or not vendedor:
            flash("Por favor, preencha todos os campos.", 'warning')
            return render_template('formulario.html')

        resultado_calculo = calcular_valor_total(quantidades, estado)

        if resultado_calculo:
            subtotal, desconto_pct, desconto_val, entrega_pct, entrega_val, valor_final = resultado_calculo
            return render_template('orcamento.html',
                                   nome=nome,
                                   cidade=cidade,
                                   estado=estado,
                                   vendedor=vendedor,
                                   quantidades=quantidades,
                                   subtotal=f'R$ {subtotal:.2f}',
                                   desconto_pct=f'{desconto_pct}%',
                                   desconto_val=f'R$ {desconto_val:.2f}',
                                   entrega_pct=f'{entrega_pct}%',
                                   entrega_val=f'R$ {entrega_val:.2f}',
                                   valor_final=f'R$ {valor_final:.2f}',
                                   valores_cervejas={p.nome: {"venda": p.venda} for p in Produto.query.all()}
)
 # Passa valores_cervejas para o template
        else:
            return render_template('formulario.html')
        
    pedidos_recentes = Pedido.query.order_by(Pedido.id.desc()).limit(4).all()

    estoque_valor_total = Decimal('0.00')
    produtos = {p.nome: p for p in Produto.query.all()}
    
    for tipo in ['pilsen', 'ipa', 'stout']:
        # Calcular quantidade em estoque
        quantidade = sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                        for e in Estoque.query.filter_by(produto=tipo).all()])
        
        # Multiplicar pela venda e somar ao total
        if quantidade > 0 and produtos.get(tipo):
            estoque_valor_total += quantidade * produtos[tipo].venda

        vendas_por_mes_uf = obter_vendas_por_uf_mes()

    hoje = datetime.now()
    primeiro_dia_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    perdas = []
    for mov in Estoque.query.filter_by(tipo_movimentacao='perca').all():
        try:
            data_mov = mov.data
            if data_mov >= primeiro_dia_mes:
                perdas.append(mov)
        except Exception as e:
            app.logger.error(f"Erro ao processar data do estoque: {str(e)}")
    custo_perdas = Decimal('0.00')
    perdas_count = len(perdas)  # Nova variável para contagem
    produtos = {p.nome: p for p in Produto.query.all()}

    atividades_recentes = obter_atividades_recentes(5)
    
    for perda in perdas:
        if perda.produto in produtos:
            custo_perdas += Decimal(perda.quantidade) * produtos[perda.produto].custo

        # Calcular produções pendentes de confirmação
    hoje = datetime.now().date()
    producoes_pendentes = Producao.query.filter(
        Producao.fim_producao <= hoje,
        Producao.entrada_confirmada == False
    ).all()
    
    producoes_pendentes_count = len(producoes_pendentes)

    return render_template('index.html',
                            total_vendas=total_vendas,
                            porcentagem_vendas=porcentagem,
                            clientes_ativos=clientes_ativos,
                            variacao_clientes=variacao_clientes,
                            porcent_clientes=porcent_clientes,
                            top_cervejas=top_cervejas,
                            pedidos_recentes=pedidos_recentes,
                            estoque_valor_total=estoque_valor_total,
                            custo_perdas=custo_perdas,
                            perdas_count=perdas_count,
                            atividades_recentes=atividades_recentes,
                            vendas_por_mes_uf=vendas_por_mes_uf,
                            producoes_pendentes=producoes_pendentes,
                            producoes_pendentes_count=producoes_pendentes_count
                            )

@app.route('/confirmar_venda', methods=['POST'])
def confirmar_venda():
    try:
        produtos_db = {p.nome: p for p in Produto.query.all()}
        nome = request.form['nome'].strip()  # Captura e sanitiza o nome
        cidade = request.form['cidade']
        estado = request.form['estado']
        vendedor = request.form['vendedor']
        quantidades = {
            "pilsen": request.form['pilsen_qty'],
            "ipa": request.form['ipa_qty'],
            "stout": request.form['stout_qty']
        }
        valor_final = Decimal(request.form['valor_final'].replace('R$', '').strip())

        # ========== NOVO CÓDIGO ========== #
        # Registrar/Atualizar cliente
        cliente_existente = Cliente.query.filter(
            func.lower(Cliente.nome) == func.lower(nome)  # Busca case-insensitive
        ).first()

        if cliente_existente:
            cliente_existente.ultima_compra = datetime.now()  # Atualiza última compra
        else:
            novo_cliente = Cliente(
                nome=nome.title(),  # Padroniza formato do nome
                data_cadastro=datetime.now(),
                ultima_compra=datetime.now()
            )
            db.session.add(novo_cliente)
            flash(f"Novo cliente cadastrado: {nome.title()}", 'info')
        # ================================ #

        # Criar novo pedido (código existente)
        data_pedido = datetime.now().strftime("%d/%m/%Y %H:%M")
        ultimo_pedido = Pedido.query.order_by(Pedido.id.desc()).first()
        proximo_numero_pedido = f"#MB-{ultimo_pedido.id + 1000}" if ultimo_pedido else "#MB-1000"

        novo_pedido = Pedido(
            numero_pedido=proximo_numero_pedido,
            data=data_pedido,
            cliente=nome,
            vendedor=vendedor,
            cidade_estado=f"{cidade.strip().capitalize()} - {estado.strip().upper()}",
            subtotal=request.form['subtotal'],
            desconto_pct=request.form['desconto_pct'],
            desconto_val=request.form['desconto_val'],
            entrega_pct=request.form['entrega_pct'],
            entrega_val=request.form['entrega_val'],
            valor_total=request.form['valor_final']
        )

        db.session.add(novo_pedido)
        db.session.flush()  # Gera o ID sem commit

        # Criar motivo para estoque
        motivo = f"Venda - {novo_pedido.numero_pedido} - {nome} - {cidade.strip().capitalize()}-{estado.strip().upper()}"

        # Registrar itens e movimentações de estoque
        for tipo, quantidade_str in quantidades.items():
            if quantidade_str and int(quantidade_str) > 0:
                quantidade = int(quantidade_str)
                
                # Item do pedido
                item = ItemPedido(
                    tipo=tipo.capitalize(),
                    quantidade=quantidade,
                    valor_unitario=f'{produtos_db[tipo].venda:.2f}',
                    valor_item=f'{quantidade * produtos_db[tipo].venda:.2f}',
                    custo_unitario=f'{produtos_db[tipo].custo:.2f}',
                    pedido_id=novo_pedido.id
                )
                db.session.add(item)
                
                # Movimentação de estoque
                movimento = Estoque(
                    produto=tipo,
                    quantidade=quantidade,
                    tipo_movimentacao='saida',
                    motivo=motivo
                )
                db.session.add(movimento)

        db.session.commit()  # Confirma tudo em uma única transação
        
        # Limpar registro financeiro do mês para forçar recálculo
        hoje = datetime.now()
        RegistroFinanceiro.query.filter(
            RegistroFinanceiro.mes == hoje.month,
            RegistroFinanceiro.ano == hoje.year
        ).delete()
        
        db.session.commit()
        
        flash("Venda confirmada e estoque atualizado com sucesso!", 'success')
        return redirect(url_for('venda_concluida'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao confirmar venda: {str(e)}", 'error')
        return redirect(url_for('index'))

@app.route('/vendas')
def lista_vendas():
    vendas = Pedido.query.all()
    return render_template('lista_vendas.html', vendas=vendas)

# Rota para a página de tipos de cerveja
@app.route('/cervejas')
def tipos_cerveja():
    return render_template('cervejas.html')

# Mantenha a rota lista_pedidos original:
@app.route('/pedidos')
def lista_pedidos():
    pedidos = Pedido.query.all()
    produtos_db = {p.nome: {"custo": p.custo} for p in Produto.query.all()}  # Adicione esta linha

    # Calcular os custos totais para cada pedido
    custos_totais = {}
    for pedido in pedidos:
        custo_total = Decimal('0.00')
        for item in pedido.itens:
            produto = Produto.query.filter_by(nome=item.tipo.lower()).first()
            if produto:
                custo_total += item.quantidade * produto.custo
        custos_totais[pedido.id] = custo_total

    return render_template(
        'lista_pedidos.html', 
        pedidos=pedidos, 
        produtos_db=produtos_db,  # Modificado aqui
        custos_totais=custos_totais
    )

@app.route('/Formulario')
def venda_sucesso():
    produtos_db = {p.nome: {"venda": p.venda} for p in Produto.query.all()}
    estoque = {
        'pilsen': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                      for e in Estoque.query.filter_by(produto='pilsen').all()]),
        'ipa': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                   for e in Estoque.query.filter_by(produto='ipa').all()]),
        'stout': sum([e.quantidade if e.tipo_movimentacao == 'entrada' else -e.quantidade 
                     for e in Estoque.query.filter_by(produto='stout').all()])
    }
    return render_template('formulario.html', valores_cervejas=produtos_db, estoque=estoque)

@app.route('/venda_concluida')
def venda_concluida():
    return render_template('sucesso_venda.html')

@app.route('/detalhes_produto')
def detalhes_produto():
    produtos = {p.nome: p for p in Produto.query.all()}
    descontos = {d.valor_minimo: d.percentual for d in Desconto.query.order_by(Desconto.valor_minimo).all()}
    taxas = {t.estados: t.taxa for t in TaxaEntrega.query.all()}
    
    return render_template(
        'detalhes_produto.html',
        pilsen_custo=produtos['pilsen'].custo,
        pilsen_venda=produtos['pilsen'].venda,
        ipa_custo=produtos['ipa'].custo,
        ipa_venda=produtos['ipa'].venda,
        stout_custo=produtos['stout'].custo,
        stout_venda=produtos['stout'].venda,
        desconto_4000=descontos.get(4000, 0),
        desconto_5000=descontos.get(5000, 0),
        desconto_6000=descontos.get(6000, 0),
        entrega_rj_sp=taxas.get('RJ,SP', 0),
        entrega_ba=taxas.get('BA', 0),
        entrega_mg=taxas.get('MG', 0)
    )

@app.route('/salvar_configuracao', methods=['POST'])
def salvar_configuracao():
    try:
        # Atualizar produtos
        produtos = {
            'pilsen': Produto.query.filter_by(nome='pilsen').first(),
            'ipa': Produto.query.filter_by(nome='ipa').first(),
            'stout': Produto.query.filter_by(nome='stout').first()
        }
        
        for nome, produto in produtos.items():
            produto.custo = Decimal(request.form[f'{nome}_custo'])
            produto.venda = Decimal(request.form[f'{nome}_venda'])
        
        # Atualizar descontos
        descontos = {
            4000: Desconto.query.filter_by(valor_minimo=4000).first(),
            5000: Desconto.query.filter_by(valor_minimo=5000).first(),
            6000: Desconto.query.filter_by(valor_minimo=6000).first()
        }
        
        for valor, desconto in descontos.items():
            desconto.percentual = Decimal(request.form[f'desconto_{valor}'])
        
        # Atualizar taxas de entrega
        TaxaEntrega.query.filter_by(estados='RJ,SP').update({'taxa': Decimal(request.form['entrega_rj_sp'])})
        TaxaEntrega.query.filter_by(estados='BA').update({'taxa': Decimal(request.form['entrega_ba'])})
        TaxaEntrega.query.filter_by(estados='MG').update({'taxa': Decimal(request.form['entrega_mg'])}) 
        
        db.session.commit()
        flash("Configurações salvas com sucesso!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar configurações: {str(e)}", 'error')
    
    return redirect(url_for('detalhes_produto'))

@app.route('/gantt')
def diagrama_gantt():
    producoes = Producao.query.all()
    eventos = [
        {
            "title": f"{p.maquina_utilizada} - {p.tipo_cerveja}",
            "start": p.inicio_producao.isoformat(),
            "end": p.fim_producao.isoformat(),
            "color": "#4CAF50" if "1" in p.maquina_utilizada else 
                    "#2196F3" if "2" in p.maquina_utilizada else 
                    "#9C27B0"
        } 
        for p in producoes
    ]
    return render_template('gantt.html', eventos=eventos)

@app.route('/producao', methods=['GET', 'POST'])
def producao():
    if request.method == 'POST':
        inicio_producao_str = request.form['inicioProducao']
        tipo_cerveja = request.form['tipoCerveja']
        maquina_utilizada = request.form['maquinaUtilizada']

        try:
            inicio_producao = datetime.strptime(inicio_producao_str, '%Y-%m-%d').date()
            hoje = datetime.now().date()
            fim_producao = inicio_producao + timedelta(days=21)
            maquina = maquina_utilizada

            app.logger.debug(f"Data de início: {inicio_producao}, Tipo: {tipo_cerveja}, Máquina: {maquina_utilizada}")
            # if inicio_producao == hoje:
            #     app.logger.debug("Erro: Data de início inválida")
            #     flash("A data de início deve ser posterior ao dia atual!", 'error')
            #     return render_template('inicio_processo.html')

            # Verificar conflitos de agendamento
            producoes_na_maquina = Producao.query.filter_by(maquina_utilizada=maquina).all()
            
            for producao_existente in producoes_na_maquina:
                if (inicio_producao <= producao_existente.fim_producao and 
                    fim_producao >= producao_existente.inicio_producao):
                    flash(f"Máquina {maquina} já está em uso até {producao_existente.fim_producao.strftime('%d/%m/%Y')}. Escolha outra máquina ou datas.", 'error')
                    return render_template('inicio_processo.html')

            # Determinar próximo número de lote
            ultimo_lote = db.session.query(db.func.max(Producao.lote)).scalar()
            proximo_lote = 100 if ultimo_lote is None else int(ultimo_lote) + 1

            nova_producao = Producao(
                lote=str(proximo_lote),
                tipo_cerveja=tipo_cerveja,
                inicio_producao=inicio_producao,
                fim_producao=fim_producao,
                maquina_utilizada=maquina_utilizada,
                quantidade_produzida_litros=1000
            )

            db.session.add(nova_producao)
            db.session.flush()  # Gera o ID sem commit

            # Verificar e consumir matérias-primas
            receita = RECEITAS.get(tipo_cerveja, {})
            if not receita:
                flash("Receita não encontrada para este tipo de cerveja", 'error')
                return redirect(url_for('producao'))

            motivo = f"Produção {nova_producao.lote} - {tipo_cerveja}"
            produtos_mp = receita.items()

            for produto, quantidade in produtos_mp:
                # Calcular estoque atual
                entradas = MovimentoMP.query.filter_by(produto=produto, tipo_movimentacao='entrada').all()
                saidas = MovimentoMP.query.filter_by(produto=produto, tipo_movimentacao='saida').all()
                estoque_atual = sum(e.quantidade for e in entradas) - sum(s.quantidade for s in saidas)

                    # Log para depuração:
                app.logger.debug(f"Estoque de {produto}: {estoque_atual} kg/L (Necessário: {quantidade} kg/L)")
                
                if estoque_atual < quantidade:
                    flash(f"Estoque insuficiente de {produto} (Necessário: {quantidade} kg/L, Disponível: {estoque_atual} kg/L)", 'error')
                    db.session.rollback()
                    return redirect(url_for('producao'))

                # Registrar saída
                saida = MovimentoMP(
                    produto=produto,
                    quantidade=quantidade,
                    tipo_movimentacao='saida',
                    fornecedor='Consumo interno - ' + motivo,  # Incorpora o motivo no fornecedor se necessário
                    valor=0.00,
                    responsavel='Sistema',
                )
                db.session.add(saida)

            db.session.commit()
            quantidade_produzida = 1000  # Litros
                
            db.session.commit()
            flash("Produção registrada e estoque atualizado com sucesso!", 'success')
            return redirect(url_for('lista_producao'))
        
        except ValueError:
            flash("Data de início inválida. Use o formato AAAA-MM-DD.", 'error')
            return render_template('inicio_processo.html')
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar produção: {str(e)}", 'error')
            return redirect(url_for('producao'))
    else:
        # CARREGAR PRODUÇÕES EXISTENTES PARA O HISTÓRICO
        producoes = Producao.query.all()
        return render_template('inicio_processo.html', producoes=producoes)


@app.route('/lista_producao')
def lista_producao():
    producoes = Producao.query.all()
    return render_template('lista_producao.html', 
                          producoes=producoes,
                          datetime=datetime)

@app.route('/excluir_producao/<int:id>', methods=['POST'])
def excluir_producao(id):
    producao = Producao.query.get_or_404(id)
    db.session.delete(producao)
    db.session.commit()
    flash("Ordem de produção excluída com sucesso!", 'success')
    return redirect(url_for('lista_producao'))

@app.route('/estoque')
def estoque():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Itens por página

    historico = Estoque.query.order_by(Estoque.data.desc()).paginate(page=page, per_page=per_page)
    
    # Calcular estoque atual
    estoque = {'pilsen': 0, 'ipa': 0, 'stout': 0}
    for mov in Estoque.query.all():
        if mov.tipo_movimentacao == 'entrada':
            estoque[mov.produto] += mov.quantidade
        else:  # Considera 'saida' e 'perca' como subtração
            estoque[mov.produto] -= mov.quantidade

    return render_template(
        'estoque.html',
        historico=historico,
        estoque_pilsen=estoque['pilsen'],
        estoque_ipa=estoque['ipa'],
        estoque_stout=estoque['stout']
    )


@app.route('/adicionar_movimentacao', methods=['POST'])
def adicionar_movimentacao():
    try:
        nova_movimentacao = Estoque(
            produto=request.form['produto'],
            quantidade=int(request.form['quantidade']),
            tipo_movimentacao=request.form['tipo_movimentacao'],
            motivo=request.form['motivo']
        )
        db.session.add(nova_movimentacao)
        db.session.commit()
        flash("Movimentação registrada com sucesso!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao registrar movimentação: {str(e)}", 'error')
    return redirect(url_for('estoque'))

def calcular_vendas_mensais():
    hoje = datetime.now()
    mes_atual = hoje.month
    ano_atual = hoje.year
    
    # Total do mês atual (usando análise de datas)
    total_atual = Decimal('0.00')
    pedidos = Pedido.query.all()
    
    for pedido in pedidos:
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            if data_pedido.month == mes_atual and data_pedido.year == ano_atual:
                total_atual += Decimal(pedido.valor_total.replace('R$', '').strip())
        except:
            continue

    # Total do mês anterior (mesma lógica de análise)
    mes_anterior = hoje.replace(day=1) - timedelta(days=1)
    total_anterior = Decimal('0.00')
    
    for pedido in pedidos:
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            if data_pedido.month == mes_anterior.month and data_pedido.year == mes_anterior.year:
                total_anterior += Decimal(pedido.valor_total.replace('R$', '').strip())
        except:
            continue

    # Calcular porcentagem
    porcentagem = Decimal('0.00')
    if total_anterior > 0:
        porcentagem = ((total_atual - total_anterior) / total_anterior * 100).quantize(Decimal('0.00'))

    return total_atual, round(porcentagem, 2)

def calcular_clientes_ativos():
    hoje = datetime.now()
    
    # Últimos 30 dias
    inicio_periodo_atual = hoje - timedelta(days=30)
    clientes_ativos = Cliente.query.filter(
        Cliente.ultima_compra >= inicio_periodo_atual
    ).count()

    # Período anterior (31-60 dias atrás)
    inicio_periodo_anterior = hoje - timedelta(days=60)
    fim_periodo_anterior = hoje - timedelta(days=31)
    clientes_periodo_anterior = Cliente.query.filter(
        Cliente.ultima_compra.between(inicio_periodo_anterior, fim_periodo_anterior)
    ).count()

    variacao = clientes_ativos - clientes_periodo_anterior
    porcent_clientes = 0.0
    if clientes_periodo_anterior > 0:
        porcent_clientes = round((variacao / clientes_periodo_anterior) * 100, 2)
    
    return clientes_ativos, variacao, porcent_clientes

@app.route('/mp', methods=['GET', 'POST'])
def gestao_mp():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Processar novo registro
    if request.method == 'POST':
        try:
            nf = request.form['nf']
            data = datetime.now()
            fornecedor = request.form['fornecedor']
            
            for produto, quantidade, valor_por_kg in zip(
                request.form.getlist('produto[]'),
                request.form.getlist('quantidade[]'),
                request.form.getlist('valor_por_kg[]')
            ):
                # Calcular valor total com base no valor por kg
                valor_total = float(quantidade) * float(valor_por_kg)
                
                movimento = MovimentoMP(
                    nf=nf,
                    data=data,
                    produto=produto,
                    quantidade=float(quantidade),
                    fornecedor=fornecedor,
                    valor=Decimal(valor_total),  # Armazena o total calculado
                    tipo_movimentacao='entrada'
                )
                db.session.add(movimento)
            
            db.session.commit()
            flash('Entrada registrada com sucesso!', 'success')
            return redirect(url_for('gestao_mp'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'error')
            return redirect(url_for('gestao_mp'))

    # Definições iniciais
    produtos_mp = [
        'Malte Pilsen', 'Malte Pale Ale', 'Malte Caramelo',
        'Malte Torrado', 'Cevada em Flocos', 'Lúpulo', 
        'Levedura', 'Água Mineral'
    ]

    for produto in produtos_mp:
        if not EstoqueMinimo.query.filter_by(produto=produto).first():
            db.session.add(EstoqueMinimo(produto=produto, minimo=100.0))
    
    db.session.commit()

    minimos = {}
    for produto in produtos_mp:
        registro = EstoqueMinimo.query.filter_by(produto=produto).first()
        minimos[produto] = registro.minimo if registro else 100.0
    
    # Cálculo de estoque e últimas movimentações
    estoque_mp = {}
    ultimas_entradas = {}
    ultimas_saidas = {}

    for produto in produtos_mp:
        entradas = MovimentoMP.query.filter_by(produto=produto, tipo_movimentacao='entrada').all()
        saidas = MovimentoMP.query.filter_by(produto=produto, tipo_movimentacao='saida').all()
        
        estoque_mp[produto] = sum(e.quantidade for e in entradas) - sum(s.quantidade for s in saidas)
        
        ultima_entrada = MovimentoMP.query.filter_by(
            produto=produto, tipo_movimentacao='entrada'
        ).order_by(MovimentoMP.data.desc()).first()
        ultimas_entradas[produto] = {
            'data': ultima_entrada.data if ultima_entrada else None,
            'quantidade': ultima_entrada.quantidade if ultima_entrada else 0
        }

        ultima_saida = MovimentoMP.query.filter_by(
            produto=produto, tipo_movimentacao='saida'
        ).order_by(MovimentoMP.data.desc()).first()
        ultimas_saidas[produto] = {
            'data': ultima_saida.data if ultima_saida else None,
            'quantidade': ultima_saida.quantidade if ultima_saida else 0
        }

    # Paginação do histórico
    historico = MovimentoMP.query.order_by(
        MovimentoMP.data.desc()
    ).paginate(page=page, per_page=per_page)

    # CORREÇÃO: Cálculo do estoque acumulado para o gráfico
    hoje = datetime.now()
    trinta_dias_atras = hoje - timedelta(days=30)
    
    # Calcular estoque inicial antes do período
    estoque_inicial = {}
    for produto in produtos_mp:
        entradas_anteriores = MovimentoMP.query.filter(
            MovimentoMP.produto == produto,
            MovimentoMP.tipo_movimentacao == 'entrada',
            MovimentoMP.data < trinta_dias_atras
        ).all()
        saidas_anteriores = MovimentoMP.query.filter(
            MovimentoMP.produto == produto,
            MovimentoMP.tipo_movimentacao == 'saida',
            MovimentoMP.data < trinta_dias_atras
        ).all()
        estoque_inicial[produto] = sum(e.quantidade for e in entradas_anteriores) - sum(s.quantidade for s in saidas_anteriores)

    # Preparar dados para o gráfico
    dados_graficos = {}
    # Lista de datas para os últimos 31 dias (de 30 dias atrás até hoje)
    datas_periodo = [trinta_dias_atras.date() + timedelta(days=i) for i in range(31)]
    labels_30_dias = [d.strftime('%d/%m') for d in datas_periodo]

    for produto in produtos_mp:
        # Array para armazenar a variação líquida de cada dia
        variacao_diaria = [0.0] * 31

        # Buscar todas as movimentações do produto no período
        movimentacoes = MovimentoMP.query.filter(
            MovimentoMP.produto == produto,
            MovimentoMP.data >= trinta_dias_atras,
            MovimentoMP.data <= hoje
        ).all()

        # Calcular variação diária
        for mov in movimentacoes:
            data_mov = mov.data.date()
            indice_dia = (data_mov - trinta_dias_atras.date()).days
            if 0 <= indice_dia < 31:
                if mov.tipo_movimentacao == 'entrada':
                    variacao_diaria[indice_dia] += mov.quantidade
                else:
                    variacao_diaria[indice_dia] -= mov.quantidade

        # Calcular estoque acumulado
        estoque_acumulado = estoque_inicial[produto]
        valores_estoque = [estoque_acumulado]
        
        for i in range(31):
            estoque_acumulado += variacao_diaria[i]
            valores_estoque.append(estoque_acumulado)

        dados_graficos[produto] = {
            'datas': labels_30_dias,
            'valores': valores_estoque[1:]  # Mostrar estoque no final de cada dia
        }

    return render_template(
        'mp.html',
        produtos_mp=produtos_mp,
        estoque_mp=estoque_mp,
        ultimas_entradas=ultimas_entradas,
        ultimas_saidas=ultimas_saidas,
        minimos=minimos,
        historico=historico,
        dados_graficos=dados_graficos
    )

@app.route('/atualizar_minimos', methods=['POST'])
def atualizar_minimos():
    try:
        for key, value in request.form.items():
            if key.startswith('minimo_'):
                produto = key.replace('minimo_', '')
                estoque_minimo = EstoqueMinimo.query.filter_by(produto=produto).first()
                if estoque_minimo:
                    estoque_minimo.minimo = float(value)
                else:
                    novo_minimo = EstoqueMinimo(produto=produto, minimo=float(value))
                    db.session.add(novo_minimo)
        db.session.commit()
        flash('Estoques mínimos atualizados!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'error')
    return redirect(url_for('gestao_mp'))

def calcular_vendas_mensais_cervejas():
    hoje = datetime.now()
    current_month = hoje.month
    current_year = hoje.year
    
    vendas_cervejas = defaultdict(int)
    
    # Busca todos os pedidos do mês atual
    pedidos = Pedido.query.all()
    for pedido in pedidos:
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            if data_pedido.month == current_month and data_pedido.year == current_year:
                for item in pedido.itens:
                    tipo = item.tipo.lower()  # Normaliza para minúsculas
                    vendas_cervejas[tipo] += item.quantidade
        except:
            continue
    
    # Ordena do maior para o menor
    return sorted(vendas_cervejas.items(), key=lambda x: x[1], reverse=True)

def obter_atividades_recentes(limite=5):
    atividades = []

    # Produções
    producoes = Producao.query.order_by(Producao.id.desc()).limit(limite).all()
    for p in producoes:
        atividades.append({
            'tipo': 'producao',
            'data': datetime.combine(p.inicio_producao, datetime.min.time()),  # Converte date para datetime
            'mensagem': f"Novo lote {p.lote} de {p.tipo_cerveja} produzido",
            'icone': 'fa-beer',
            'cor': 'bg-orange-100 text-orange-500'
        })

    # Pedidos
    pedidos = Pedido.query.order_by(Pedido.id.desc()).limit(limite).all()
    for ped in pedidos:
        atividades.append({
            'tipo': 'venda',
            'data': datetime.strptime(ped.data, "%d/%m/%Y %H:%M"),  # Formato corrigido
            'mensagem': f"Pedido {ped.numero_pedido} realizado por {ped.cliente}",
            'icone': 'fa-shopping-cart',
            'cor': 'bg-blue-100 text-blue-500'
        })

    # Clientes
    clientes = Cliente.query.order_by(Cliente.id.desc()).limit(limite).all()
    for cli in clientes:
        atividades.append({
            'tipo': 'cliente',
            'data': cli.data_cadastro,
            'mensagem': f"Novo cliente cadastrado: {cli.nome}",
            'icone': 'fa-user-plus',
            'cor': 'bg-green-100 text-green-500'
        })

    # Estoque
    estoques = Estoque.query.order_by(Estoque.id.desc()).limit(limite).all()
    for est in estoques:
        tipo = 'Entrada' if est.tipo_movimentacao == 'entrada' else 'Saída'
        atividades.append({
            'tipo': 'estoque',
            'data': est.data,
            'mensagem': f"{tipo} de {est.quantidade} unidades de {est.produto}",
            'icone': 'fa-warehouse',
            'cor': 'bg-purple-100 text-purple-500'
        })

    # Matéria-prima
    movimentos = MovimentoMP.query.order_by(MovimentoMP.id.desc()).limit(limite).all()
    for mov in movimentos:
        tipo = 'Entrada' if mov.tipo_movimentacao == 'entrada' else 'Saída'
        atividades.append({
            'tipo': 'mp',
            'data': mov.data,
            'mensagem': f"{tipo} de {mov.quantidade}kg de {mov.produto}",
            'icone': 'fa-box-open',
            'cor': 'bg-yellow-100 text-yellow-500'
        })

    # Ordenar todas as atividades por data e pegar as mais recentes
    atividades.sort(key=lambda x: x['data'], reverse=True)
    return atividades[:limite]

def obter_vendas_por_uf_mes():
    hoje = datetime.now()
    seis_meses_atras = hoje - relativedelta(months=5)  # Ajustado para 5 meses para pegar 6 meses no total

    pedidos = Pedido.query.all()
    
    vendas = defaultdict(lambda: defaultdict(int))
    
    for pedido in pedidos:
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            if data_pedido < seis_meses_atras:
                continue
            
            mes_ano = data_pedido.strftime("%Y-%m")
            uf = pedido.cidade_estado.split(" - ")[-1].strip().upper()
            
            total_itens = sum(item.quantidade for item in pedido.itens)
            vendas[mes_ano][uf] += total_itens
        
        except:
            continue

    meses_ordenados = []
    for i in range(5, -1, -1):  # Últimos 6 meses em ordem decrescente
        data = hoje - relativedelta(months=i)
        chave = data.strftime("%Y-%m")
        nome_mes = data.strftime("%b").upper()  # Formato JAN, FEV, etc
        
        ufs = vendas.get(chave, {})
        
        detalhes_ufs = []
        for uf, qtd in ufs.items():
            detalhes_ufs.append({'uf': uf, 'qtd': qtd})
        
        meses_ordenados.append({
            'nome': nome_mes,
            'ufs': detalhes_ufs
        })

    return meses_ordenados

@app.route('/clientes')
def lista_clientes():
    # Obter todos os clientes
    clientes = Cliente.query.all()
    
    # Calcular informações de compras
    clientes_com_info = []
    for cliente in clientes:
        # Buscar todos os pedidos do cliente
        pedidos = Pedido.query.filter(func.lower(Pedido.cliente) == func.lower(cliente.nome)).all()
        
        # Calcular total gasto e última compra
        total_gasto = sum(Decimal(p.valor_total.replace('R$', '').strip()) for p in pedidos)
        ultima_compra = max([datetime.strptime(p.data, "%d/%m/%Y %H:%M") for p in pedidos]) if pedidos else None
        
        clientes_com_info.append({
            'cliente': cliente,
            'total_gasto': total_gasto,
            'ultima_compra': ultima_compra.strftime("%d/%m/%Y %H:%M") if ultima_compra else "Nunca comprou",
            'total_pedidos': len(pedidos)
        })
    
    # Ordenar por último mais recente
    clientes_com_info.sort(key=lambda x: x['cliente'].ultima_compra or datetime.min, reverse=True)
    
    return render_template('clientes.html', clientes=clientes_com_info)

@app.route('/financeiro')
def financeiro():
    # Buscar todos os meses distintos que possuem pedidos
    meses_com_pedidos = set()
    for pedido in Pedido.query.all():
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            meses_com_pedidos.add((data_pedido.month, data_pedido.year))
        except Exception as e:
            app.logger.error(f"Erro ao processar data do pedido {pedido.id}: {e}")
            continue

    # Preparar lista de períodos disponíveis
    periodos_disponiveis = []
    for mes, ano in meses_com_pedidos:
        data_ref = datetime(ano, mes, 1)
        label = f"{data_ref.strftime('%b/%Y').upper()}"  # Formato: JAN/2023
        
        # Adicionar "(Atual)" se for o mês corrente
        hoje = datetime.now()
        if mes == hoje.month and ano == hoje.year:
            label += " (Atual)"
            
        periodos_disponiveis.append({
            'mes': mes,
            'ano': ano,
            'label': label
        })

    # Ordenar por ano e mês (mais recente primeiro)
    periodos_disponiveis.sort(key=lambda p: (p['ano'], p['mes']), reverse=True)

    # Obter mês/ano selecionado (padrão: mês atual)
    hoje = datetime.now()
    mes_selecionado = request.args.get('mes', type=int, default=hoje.month)
    ano_selecionado = request.args.get('ano', type=int, default=hoje.year)

    # Calcular dados para o período selecionado
    primeiro_dia_mes = datetime(ano_selecionado, mes_selecionado, 1)
    ultimo_dia_mes = datetime(ano_selecionado, mes_selecionado+1, 1) - timedelta(days=1) if mes_selecionado < 12 else datetime(ano_selecionado, 12, 31)
    
    # Calcular vendas totais
    total_vendas = Decimal('0.00')
    pedidos_mes = []
    for pedido in Pedido.query.all():
        try:
            data_pedido = datetime.strptime(pedido.data, "%d/%m/%Y %H:%M")
            if data_pedido >= primeiro_dia_mes and data_pedido <= ultimo_dia_mes:
                pedidos_mes.append(pedido)
                
                # Converter valor total
                valor_str = pedido.valor_total.replace('R$', '').replace(' ', '')
                if '.' in valor_str and ',' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')
                total_vendas += Decimal(valor_str)
        except Exception as e:
            app.logger.error(f"Erro ao processar pedido {pedido.id}: {e}")
            continue

    # Calcular transporte e número de entregas
    total_transporte = Decimal('0.00')
    numero_entregas = 0
    for pedido in pedidos_mes:
        if pedido.entrega_val:
            try:
                # Converter valor de entrega
                valor_str = pedido.entrega_val.replace('R$', '').replace(' ', '')
                if '.' in valor_str and ',' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')
                entrega_val = Decimal(valor_str)
                total_transporte += entrega_val
                if entrega_val > 0:
                    numero_entregas += 1
            except Exception as e:
                app.logger.error(f"Erro ao converter valor de entrega: {e}")
                continue

    # Calcular matéria prima
    custo_materia_prima = db.session.query(func.sum(MovimentoMP.valor)).filter(
        MovimentoMP.tipo_movimentacao == 'entrada',
        MovimentoMP.data >= primeiro_dia_mes,
        MovimentoMP.data <= ultimo_dia_mes
    ).scalar() or Decimal('0.00')

    # Calcular produções
    producoes_mes = Producao.query.filter(
        Producao.inicio_producao >= primeiro_dia_mes,
        Producao.inicio_producao <= ultimo_dia_mes
    ).all()
    litros_produzidos = sum(p.quantidade_produzida_litros for p in producoes_mes)

    # Calcular lucros
    custo_total = custo_materia_prima + total_transporte
    lucro_bruto = total_vendas - custo_total
    lucro_liquido = lucro_bruto - Decimal(15000)  # Custos fixos

    # Buscar ou criar registro financeiro
    registro_existente = RegistroFinanceiro.query.filter(
        RegistroFinanceiro.mes == mes_selecionado,
        RegistroFinanceiro.ano == ano_selecionado
    ).first()

    # Atualizar dados
    if registro_existente:
        registro_existente.total_vendas = total_vendas
        registro_existente.custo_materia_prima = custo_materia_prima
        registro_existente.custo_transporte = total_transporte
        registro_existente.litros_produzidos = litros_produzidos
        registro_existente.numero_entregas = numero_entregas
    else:
        novo_registro = RegistroFinanceiro(
            mes=mes_selecionado,
            ano=ano_selecionado,
            total_vendas=total_vendas,
            custo_materia_prima=custo_materia_prima,
            custo_transporte=total_transporte,
            litros_produzidos=litros_produzidos,
            numero_entregas=numero_entregas
        )
        db.session.add(novo_registro)
    
    db.session.commit()

    # Buscar dados atualizados para o template
    registro_atual = RegistroFinanceiro.query.filter(
        RegistroFinanceiro.mes == mes_selecionado,
        RegistroFinanceiro.ano == ano_selecionado
    ).first()

    return render_template('financeiro.html',
                         total_vendas=registro_atual.total_vendas,
                         numero_entregas=registro_atual.numero_entregas,
                         litros_produzidos=registro_atual.litros_produzidos,
                         custo_materia_prima=registro_atual.custo_materia_prima,
                         total_transporte=registro_atual.custo_transporte,
                         custos_fixos=15000.00,
                         lucro_bruto=lucro_bruto,
                         lucro_liquido=lucro_liquido,
                         periodos_disponiveis=periodos_disponiveis,
                         periodo_selecionado=f"{mes_selecionado},{ano_selecionado}")

# app.py - Modificações na rota financeiro/dados
@app.route('/financeiro/dados')
def financeiro_dados():
    mes = request.args.get('mes', type=int)
    ano = request.args.get('ano', type=int)
    
    registro = RegistroFinanceiro.query.filter_by(mes=mes, ano=ano).first()
    
    if registro:
        # Dados já existem no banco
        custo_total = registro.custo_materia_prima + registro.custo_transporte
        lucro_bruto = registro.total_vendas - custo_total
        lucro_liquido = lucro_bruto - Decimal(15000)  # Custos fixos
        
        return jsonify({
            'total_vendas': float(registro.total_vendas),
            'custo_materia_prima': float(registro.custo_materia_prima),
            'custo_transporte': float(registro.custo_transporte),
            'litros_produzidos': registro.litros_produzidos,
            'numero_entregas': registro.numero_entregas,
            'custos_fixos': 15000.00,
            'lucro_bruto': float(lucro_bruto),
            'lucro_liquido': float(lucro_liquido)
        })
    else:
        # CALCULAR DADOS PARA MESES ANTIGOS QUE NÃO ESTÃO NO BANCO
        return calcular_e_retornar_dados(mes, ano)

# Nova função para calcular dados históricos
def calcular_e_retornar_dados(mes, ano):
    primeiro_dia_mes = datetime(ano, mes, 1)
    ultimo_dia_mes = datetime(ano, mes+1, 1) - timedelta(days=1) if mes < 12 else datetime(ano, 12, 31)
    
    # 1. Calcular vendas totais
    total_vendas = Decimal('0.00')
    pedidos_mes = Pedido.query.filter(
        Pedido.data.between(primeiro_dia_mes.strftime("%d/%m/%Y"), ultimo_dia_mes.strftime("%d/%m/%Y"))
    ).all()
    
    for pedido in pedidos_mes:
        try:
            valor_str = pedido.valor_total.replace('R$', '').replace(' ', '')
            if '.' in valor_str and ',' in valor_str:
                valor_str = valor_str.replace('.', '').replace(',', '.')
            elif ',' in valor_str:
                valor_str = valor_str.replace(',', '.')
            total_vendas += Decimal(valor_str)
        except:
            continue

    # 2. Calcular transporte
    total_transporte = Decimal('0.00')
    numero_entregas = 0
    for pedido in pedidos_mes:
        if pedido.entrega_val:
            try:
                valor_str = pedido.entrega_val.replace('R$', '').replace(' ', '')
                if '.' in valor_str and ',' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')
                entrega_val = Decimal(valor_str)
                total_transporte += entrega_val
                if entrega_val > 0:
                    numero_entregas += 1
            except:
                continue

    # 3. Calcular matéria prima
    custo_materia_prima = db.session.query(func.sum(MovimentoMP.valor)).filter(
        MovimentoMP.tipo_movimentacao == 'entrada',
        MovimentoMP.data >= primeiro_dia_mes,
        MovimentoMP.data <= ultimo_dia_mes
    ).scalar() or Decimal('0.00')

    # 4. Calcular produções
    producoes_mes = Producao.query.filter(
        Producao.inicio_producao >= primeiro_dia_mes,
        Producao.inicio_producao <= ultimo_dia_mes
    ).all()
    litros_produzidos = sum(p.quantidade_produzida_litros for p in producoes_mes)

    # 5. Calcular lucros
    custo_total = custo_materia_prima + total_transporte
    lucro_bruto = total_vendas - custo_total
    lucro_liquido = lucro_bruto - Decimal(15000)  # Custos fixos
    
    # Salvar no banco para consultas futuras
    novo_registro = RegistroFinanceiro(
        mes=mes,
        ano=ano,
        total_vendas=total_vendas,
        custo_materia_prima=custo_materia_prima,
        custo_transporte=total_transporte,
        litros_produzidos=litros_produzidos,
        numero_entregas=numero_entregas
    )
    db.session.add(novo_registro)
    db.session.commit()

    return jsonify({
        'total_vendas': float(total_vendas),
        'custo_materia_prima': float(custo_materia_prima),
        'custo_transporte': float(total_transporte),
        'litros_produzidos': litros_produzidos,
        'numero_entregas': numero_entregas,
        'custos_fixos': 15000.00,
        'lucro_bruto': float(lucro_bruto),
        'lucro_liquido': float(lucro_liquido)
    })


@app.route('/confirmar_entrada/<int:id>', methods=['POST'])
def confirmar_entrada(id):
    producao = Producao.query.get_or_404(id)
    
    # Registrar entrada no estoque
    movimento_estoque = Estoque(
        produto=producao.tipo_cerveja.lower(),
        quantidade=3710,
        tipo_movimentacao='entrada',
        motivo=f"Produção lote {producao.lote} - {producao.tipo_cerveja} (confirmada)"
    )
    db.session.add(movimento_estoque)
    
    # Marcar como confirmada
    producao.entrada_confirmada = True
    db.session.commit()
    
    flash("Entrada no estoque confirmada com sucesso!", 'success')
    return redirect(url_for('index'))
    
# Inicialização do Banco de Dados
with app.app_context():
    db.create_all()

    try:
        db.session.execute('ALTER TABLE producao ADD COLUMN entrada_confirmada BOOLEAN DEFAULT FALSE')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Coluna já existe:", str(e))

    # Adicione estas matérias-primas
    produtos_mp = [
        'Malte Pilsen', 'Malte Pale Ale', 'Malte Caramelo',
        'Malte Torrado', 'Cevada em Flocos', 'Lúpulo',
        'Levedura', 'Água Mineral'
    ]

    for produto in produtos_mp:
        if not EstoqueMinimo.query.filter_by(produto=produto).first():
            db.session.add(EstoqueMinimo(produto=produto, minimo=100.0))

    db.session.commit()

    # Inicializar dados padrão se não existirem
    if not Produto.query.first():
        produtos_iniciais = [
            Produto(nome='pilsen', custo=4.80, venda=5.90),
            Produto(nome='ipa', custo=3.80, venda=4.50),
            Produto(nome='stout', custo=5.00, venda=7.00)
        ]
        db.session.bulk_save_objects(produtos_iniciais)

    if not Desconto.query.first():
        descontos_iniciais = [
            Desconto(valor_minimo=4000, percentual=10),
            Desconto(valor_minimo=5000, percentual=13),
            Desconto(valor_minimo=6000, percentual=15)
        ]
        db.session.bulk_save_objects(descontos_iniciais)

    if not TaxaEntrega.query.first():
        taxas_iniciais = [
            TaxaEntrega(estados='RJ,SP', taxa=5),
            TaxaEntrega(estados='BA', taxa=10),
            TaxaEntrega(estados='MG', taxa=3),
            TaxaEntrega(estados='Outros', taxa=0)
        ]
        db.session.bulk_save_objects(taxas_iniciais)


    db.session.commit()

from waitress import serve

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
