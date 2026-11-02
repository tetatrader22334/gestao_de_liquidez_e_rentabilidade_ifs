# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_concentracao/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
    1                    liquidez_imediata                0.004720                        0.004632                -0.000427
    2 operacoes_de_credito_sobre_captacoes                0.003902                        0.003465                -0.001634
    3          captacoes_sobre_ativo_total                0.002491                        0.002390                -0.001509
    4                     market_share_dec                0.002344                        0.002241                -0.000925
    5                              estatal                0.001886                        0.001848                -0.000557
    6                             nsfr_dec                0.001835                        0.001667                -0.000197
    7     disponibilidades_sobre_depositos                0.001645                        0.001509                 0.000548
    8                      hhi_periodo_dec                0.001627                        0.001332                -0.001016
    9  depositos_a_vista_sobre_ativo_total                0.001612                        0.001301                -0.000317
   10               indice_de_imobilizacao                0.001309                        0.001171                -0.000078
   11               ativos_sobre_depositos                0.001096                        0.001003                 0.000388
   12                          crise_covid                0.000995                        0.000738                -0.000702
   13  depositos_a_prazo_sobre_ativo_total                0.000825                        0.000766                -0.000092
   14                              lcr_dec                0.000684                        0.000572                -0.000268
   15                 controle_estrangeiro                0.000333                        0.000309                -0.000222
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.006704               -0.001581
    2 t-6                    0.005331               -0.001213
    3 t-5                    0.004134               -0.001069
    4 t-4                    0.003403               -0.001127
    5 t-3                    0.002808               -0.001003
    6 t-2                    0.002183               -0.000472
    7 t-1                    0.001728               -0.000272
    8   t                    0.001269               -0.000167
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

Tempo total de execução: 137.17 segundos.