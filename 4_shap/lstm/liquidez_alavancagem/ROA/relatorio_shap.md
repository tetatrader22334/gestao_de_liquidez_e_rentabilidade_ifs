# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_alavancagem/ROA/preprocessadores_ROA.joblib`
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
    1                          crise_covid                0.001926                        0.001381                 0.001343
    2  depositos_a_prazo_sobre_ativo_total                0.000850                        0.000268                -0.000021
    3        multiplicador_capital_proprio                0.000746                        0.000335                -0.000030
    4                    liquidez_imediata                0.000703                        0.000225                 0.000115
    5                            crise_nme                0.000646                        0.000507                 0.000507
    6               indice_de_basileia_dec                0.000622                        0.000400                -0.000093
    7               indice_de_imobilizacao                0.000493                        0.000210                -0.000002
    8                              estatal                0.000387                        0.000367                -0.000038
    9                             nsfr_dec                0.000368                        0.000197                 0.000030
   10          captacoes_sobre_ativo_total                0.000349                        0.000296                -0.000166
   11 operacoes_de_credito_sobre_captacoes                0.000256                        0.000189                -0.000063
   12     disponibilidades_sobre_depositos                0.000244                        0.000159                -0.000002
   13  depositos_a_vista_sobre_ativo_total                0.000243                        0.000122                 0.000021
   14               ativos_sobre_depositos                0.000170                        0.000080                 0.000016
   15                              lcr_dec                0.000143                        0.000103                -0.000042
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.002499               -0.000104
    2 t-1                    0.001086                0.000036
    3 t-4                    0.000872                0.000364
    4 t-3                    0.000854                0.000302
    5 t-5                    0.000814                0.000321
    6 t-2                    0.000788                0.000211
    7 t-6                    0.000739                0.000268
    8 t-7                    0.000628                0.000216
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

Tempo total de execução: 228.35 segundos.