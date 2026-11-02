# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_contabil/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_contabil/ROE/preprocessadores_ROE.joblib`
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
 rank                              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1                              estatal                0.009465                        0.009409                -0.000596
    2                          crise_covid                0.006715                        0.004587                 0.000979
    3          captacoes_sobre_ativo_total                0.006489                        0.006386                -0.002939
    4               indice_de_imobilizacao                0.005166                        0.005058                 0.001560
    5  depositos_a_prazo_sobre_ativo_total                0.004038                        0.003811                -0.000294
    6  depositos_a_vista_sobre_ativo_total                0.003599                        0.003277                -0.001732
    7                            crise_nme                0.003436                        0.003285                 0.003265
    8                 controle_estrangeiro                0.002973                        0.002960                 0.002236
    9                    liquidez_imediata                0.002935                        0.002582                 0.000106
   10 operacoes_de_credito_sobre_captacoes                0.002745                        0.002542                -0.000143
   11               ativos_sobre_depositos                0.002519                        0.002393                -0.001339
   12     disponibilidades_sobre_depositos                0.002069                        0.001867                 0.000188
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.012025               -0.000293
    2 t-1                    0.008292                0.000080
    3 t-2                    0.007301               -0.000015
    4 t-3                    0.006319                0.000344
    5 t-4                    0.005487                0.000409
    6 t-5                    0.004795                0.000361
    7 t-6                    0.004267                0.000219
    8 t-7                    0.003662                0.000188
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

Tempo total de execução: 82.92 segundos.