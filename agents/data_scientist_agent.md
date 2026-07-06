# Data Scientist Agent — Interpretação dos resultados do dataset e do site

## Objetivo do agente
Atuar como um cientista de dados para interpretar criticamente os resultados do projeto, explicando o que os números do dataset e os gráficos do site indicam sobre intoxicação exógena em idosos, com foco em tendência temporal, diferenças por sexo, concentração geográfica e perfil dos agentes tóxicos.

## Escopo de análise
- **Fonte principal**: `dashboard/data/dashboard_data.json`
- **Recorte analítico**: 2007–2025, 5 estados (Acre, Distrito Federal, Paraíba, Santa Catarina e São Paulo), ambos os sexos.
- **Componentes do site avaliados**: métricas principais, série anual, heatmap estado-ano, distribuição territorial, perfil tóxico, tabela por estado e insights dinâmicos.

## Leitura técnica dos resultados

### 1) Panorama geral
- Total acumulado no recorte: **10.400 notificações**.
- Distribuição por sexo: **64,5% feminino (6.704)** e **35,5% masculino (3.696)**.
- Interpretação: há predominância consistente de notificações femininas no recorte selecionado.

### 2) Concentração territorial
- **São Paulo** concentra **7.577 casos (72,9%)** do total.
- Santa Catarina aparece em segundo plano com 1.882 casos; os demais estados têm volume bem menor.
- Interpretação: o padrão agregado é fortemente influenciado por São Paulo, o que pode mascarar dinâmicas locais dos estados de menor volume.

### 3) Tendência temporal
- O último ano do recorte (2025) registra o maior volume observado: **1.387 casos** (950 feminino, 437 masculino).
- Em ambos os sexos, o pico também ocorre em 2025.
- Interpretação: há crescimento no fim da série; contudo, sem normalização por população idosa e sem ajuste para qualidade de notificação, isso deve ser tratado como sinal descritivo e não causal.

### 4) Perfil dos agentes tóxicos
- Grupo dominante: **Medicamento** com 7.209 registros no total.
- Entre mulheres, medicamento representa o principal grupo com folga.
- Entre homens, medicamento também lidera, com participação relativamente maior de raticida e agrotóxico agrícola em comparação ao perfil feminino.
- Interpretação: o padrão sugere perfil de exposição/uso distinto por sexo, útil para orientar políticas de prevenção segmentadas.

### 5) Cobertura e qualidade do dado
- Há preenchimento de anos ausentes com zero em alguns pares estado-sexo (principalmente Acre).
- Interpretação: isso preserva continuidade visual das séries, mas pode reduzir médias e alterar percepção de tendência quando comparado a estados com série mais completa.

## Como interpretar os blocos do site sob visão de ciência de dados
- **Métricas do topo**: dão leitura rápida do recorte ativo, mas devem sempre ser lidas junto ao filtro aplicado.
- **Série anual**: melhor para detectar aceleração/desaceleração; evitar inferência causal sem variáveis de contexto.
- **Heatmap estado-ano**: útil para identificar concentração e lacunas de observação.
- **Pizzas por estado**: evidenciam concentração territorial e dependência de poucos estados no total.
- **Gráfico de grupos tóxicos**: mostra prioridade de intervenção (medicamentos como principal eixo).
- **Insights dinâmicos**: são narrativas automáticas descritivas; devem ser validadas com análise estatística adicional quando usadas para decisão.

## Recomendações analíticas do agente
1. Calcular taxas por 100 mil idosos para reduzir viés de tamanho populacional entre estados.
2. Separar variação real de possível melhora de notificação (efeito vigilância).
3. Medir tendência por estado com modelos simples de série temporal (incluindo sensibilidade para anos preenchidos com zero).
4. Monitorar perfil tóxico por sexo e estado para apoiar prevenção focalizada.
5. Produzir alertas quando o recorte selecionado estiver excessivamente concentrado em um único estado.

## Conclusão
Do ponto de vista de ciência de dados, o painel apresenta sinais claros de **predomínio feminino**, **forte concentração em São Paulo**, **pico recente em 2025** e **liderança de medicamentos como agente tóxico**. Os resultados são úteis para vigilância descritiva e priorização inicial, mas decisões de política pública exigem complementação com taxas padronizadas, contexto demográfico e avaliação de qualidade de notificação.
