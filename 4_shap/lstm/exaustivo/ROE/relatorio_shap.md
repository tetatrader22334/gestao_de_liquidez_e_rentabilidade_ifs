# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/exaustivo/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/exaustivo/ROE/preprocessadores_ROE.joblib`
- Target: `ROE`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `8`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 503
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                                                 feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                                       pib_indice_sa_log                0.010090                        0.003778                 0.003778
    2                                           pib_indice_sa                0.009018                        0.002953                 0.002907
    3                                             crise_covid                0.005547                        0.002420                -0.000996
    4  receitas_de_intermediacao_financeira_sobre_ativo_total                0.004009                        0.002933                -0.000374
    5           rendas_de_operacoes_com_TVM_sobre_ativo_total                0.003827                        0.002839                -0.000154
    6                                         hhi_periodo_dec                0.003671                        0.003660                 0.003660
    7                           multiplicador_capital_proprio                0.003424                        0.003350                 0.000945
    8                                               trimestre                0.003156                        0.001196                 0.000201
    9       rendas_de_prestacao_de_servicos_sobre_ativo_total                0.002190                        0.000814                -0.000178
   10        rendas_de_operacoes_de_credito_sobre_ativo_total                0.002073                        0.001239                -0.000055
   11                     despesas_de_captacao_sobre_receitas                0.001999                        0.001877                -0.001157
   12 resultado_de_intermediacao_financeira_sobre_ativo_total                0.001885                        0.000951                -0.000299
   13                                  indice_de_basileia_dec                0.001855                        0.001460                -0.000540
   14                      despesas_de_pessoal_sobre_receitas                0.001833                        0.001735                -0.001488
   15           rendas_de_tarifas_bancarias_sobre_ativo_total                0.001827                        0.001211                 0.000561
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.030295                0.008910
    2 t-1                    0.014809               -0.002800
    3 t-2                    0.012483                0.002584
    4 t-7                    0.011176               -0.000260
    5 t-6                    0.009020                0.000021
    6 t-3                    0.008601               -0.000332
    7 t-5                    0.008041               -0.000203
    8 t-4                    0.007771                0.000353
```

## Arquivos gerados
- `shap_values_flat.npy`
- `shap_values_3d.npy`
- `shap_base_values.npy`
- `metadados_amostras_shap.csv`
- `shap_importance_lag_feature.csv`
- `shap_importance_feature_aggregated.csv`
- `shap_importance_by_lag.csv`
- `shap_bar_flat_top.png`
- `shap_beeswarm_flat_top.png`
- `shap_bar_feature_aggregated_top.png`
- `shap_heatmap_feature_lag_top.png`

Tempo total de execução: 631.39 segundos.