# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_complementar/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_complementar/ROE/preprocessadores_ROE.joblib`
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
    1                              estatal                0.009203                        0.009203                -0.000802
    2                          crise_covid                0.006310                        0.004698                 0.004608
    3               indice_de_imobilizacao                0.004704                        0.004274                 0.000342
    4                            crise_nme                0.004081                        0.004081                 0.004081
    5  depositos_a_prazo_sobre_ativo_total                0.003260                        0.003202                -0.000858
    6                    liquidez_imediata                0.002929                        0.002615                 0.001880
    7  depositos_a_vista_sobre_ativo_total                0.002728                        0.002506                -0.000051
    8                 controle_estrangeiro                0.002398                        0.002396                 0.001772
    9     disponibilidades_sobre_depositos                0.002336                        0.002184                -0.000979
   10 operacoes_de_credito_sobre_captacoes                0.001984                        0.001482                -0.000095
   11          captacoes_sobre_ativo_total                0.001882                        0.001225                -0.000271
   12                             nsfr_dec                0.001862                        0.001489                -0.000327
   13                              lcr_dec                0.001376                        0.001183                -0.000360
   14               ativos_sobre_depositos                0.001350                        0.001308                -0.000891
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.008545                0.000306
    2 t-2                    0.005882                0.000674
    3 t-1                    0.005818                0.000522
    4 t-3                    0.005818                0.001119
    5 t-4                    0.005577                0.001272
    6 t-5                    0.005272                0.001508
    7 t-6                    0.005022                0.001318
    8 t-7                    0.004467                0.001330
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

Tempo total de execução: 86.18 segundos.