# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `6`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 531
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                    liquidez_imediata                0.004513                        0.004512                -0.000912
    2 operacoes_de_credito_sobre_captacoes                0.002537                        0.002285                -0.000616
    3          captacoes_sobre_ativo_total                0.002096                        0.002042                -0.000817
    4                             nsfr_dec                0.001562                        0.001515                 0.000384
    5  depositos_a_vista_sobre_ativo_total                0.001470                        0.001427                 0.000212
    6     disponibilidades_sobre_depositos                0.001348                        0.001294                 0.000823
    7  depositos_a_prazo_sobre_ativo_total                0.001187                        0.001176                -0.000361
    8                              estatal                0.001116                        0.001101                -0.000001
    9                              lcr_dec                0.001098                        0.000961                -0.000403
   10               indice_de_basileia_dec                0.001045                        0.000915                 0.000108
   11               indice_de_imobilizacao                0.001032                        0.000978                 0.000362
   12               ativos_sobre_depositos                0.000988                        0.000983                 0.000501
   13        multiplicador_capital_proprio                0.000852                        0.000829                -0.000092
   14                          crise_covid                0.000705                        0.000490                 0.000052
   15                            crise_nme                0.000326                        0.000315                 0.000070
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.005132                0.000223
    2 t-1                    0.004253               -0.000187
    3 t-2                    0.003728               -0.000280
    4 t-3                    0.003284               -0.000270
    5 t-4                    0.002934               -0.000223
    6 t-5                    0.002668                0.000032
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

Tempo total de execução: 75.10 segundos.