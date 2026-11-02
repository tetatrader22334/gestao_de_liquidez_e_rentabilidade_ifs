# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_contabil/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_contabil/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
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
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                          crise_covid                0.001595                        0.001164                 0.001060
    2  depositos_a_prazo_sobre_ativo_total                0.001001                        0.000437                -0.000086
    3                              estatal                0.000899                        0.000884                -0.000119
    4                    liquidez_imediata                0.000792                        0.000429                 0.000259
    5          captacoes_sobre_ativo_total                0.000635                        0.000623                -0.000310
    6 operacoes_de_credito_sobre_captacoes                0.000592                        0.000384                -0.000192
    7               indice_de_imobilizacao                0.000422                        0.000301                -0.000019
    8                            crise_nme                0.000404                        0.000228                 0.000194
    9     disponibilidades_sobre_depositos                0.000375                        0.000254                -0.000029
   10  depositos_a_vista_sobre_ativo_total                0.000353                        0.000272                -0.000123
   11                 controle_estrangeiro                0.000221                        0.000201                 0.000134
   12               ativos_sobre_depositos                0.000216                        0.000147                -0.000089
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.002446               -0.000173
    2 t-1                    0.000953               -0.000077
    3 t-3                    0.000764                0.000171
    4 t-2                    0.000758                0.000058
    5 t-4                    0.000714                0.000193
    6 t-5                    0.000676                0.000202
    7 t-6                    0.000639                0.000169
    8 t-7                    0.000556                0.000136
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

Tempo total de execução: 91.68 segundos.