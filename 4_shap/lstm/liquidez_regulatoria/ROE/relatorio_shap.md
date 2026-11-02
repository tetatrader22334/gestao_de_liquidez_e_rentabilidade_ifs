# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/ROE/lstm_automl_ROE.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/ROE/preprocessadores_ROE.joblib`
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
 rank              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1             nsfr_dec                0.012429                        0.009669                -0.002632
    2              estatal                0.010757                        0.010653                -0.001700
    3              lcr_dec                0.008426                        0.005467                -0.000805
    4            crise_nme                0.005406                        0.004072                 0.004072
    5          crise_covid                0.004774                        0.002561                 0.000327
    6 controle_estrangeiro                0.001874                        0.001700                 0.000427
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1   t                    0.010385               -0.003339
    2 t-7                    0.007670                0.000823
    3 t-1                    0.006393               -0.001231
    4 t-6                    0.004853                0.001132
    5 t-2                    0.004233               -0.000134
    6 t-5                    0.003642                0.001177
    7 t-3                    0.003280                0.000418
    8 t-4                    0.003209                0.000844
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

Tempo total de execução: 115.13 segundos.