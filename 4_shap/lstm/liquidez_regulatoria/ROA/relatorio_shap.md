# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/ROA/lstm_automl_ROA.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/ROA/preprocessadores_ROA.joblib`
- Target: `ROA`
- Instituição: `id_entidade`
- Tempo: `AnoMes_ord`
- Horizonte: `1`
- Comprimento da sequência: `12`
- Explainer: `permutation`
- Escala do output: `original do target`

## Amostras
- Dimensão da base: 615 linhas x 82 colunas
- Sequências reconstruídas: 447
- Sequências de background: 40
- Sequências explicadas: 80

## Top 15 variáveis agregadas
```
 rank              feature  mean_abs_shap_sum_lags  mean_abs_of_total_shap_feature  mean_total_shap_feature
    1              lcr_dec                0.001171                        0.001032                -0.000282
    2             nsfr_dec                0.000928                        0.000667                -0.000181
    3            crise_nme                0.000875                        0.000875                 0.000875
    4              estatal                0.000688                        0.000663                -0.000122
    5          crise_covid                0.000524                        0.000475                -0.000249
    6 controle_estrangeiro                0.000129                        0.000119                -0.000059
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-10                    0.000527                0.000038
    2 t-11                    0.000505                0.000054
    3  t-9                    0.000474                0.000030
    4  t-8                    0.000454                0.000022
    5  t-7                    0.000451                0.000002
    6  t-6                    0.000407               -0.000025
    7  t-5                    0.000382               -0.000019
    8  t-4                    0.000339               -0.000025
    9  t-3                    0.000301               -0.000034
   10  t-2                    0.000236               -0.000025
   11  t-1                    0.000149               -0.000022
   12    t                    0.000089               -0.000015
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

Tempo total de execução: 96.22 segundos.