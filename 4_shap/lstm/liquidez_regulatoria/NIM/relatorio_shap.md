# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_regulatoria/NIM/preprocessadores_NIM.joblib`
- Target: `NIM`
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
    1             nsfr_dec                0.010738                        0.010489                 0.000080
    2              estatal                0.007000                        0.006942                -0.000903
    3              lcr_dec                0.004444                        0.003737                -0.000854
    4          crise_covid                0.003113                        0.002651                -0.002177
    5            crise_nme                0.000861                        0.000840                -0.000203
    6 controle_estrangeiro                0.000818                        0.000812                 0.000184
```

## Importância por defasagem
```
 rank  lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-11                    0.003261               -0.000319
    2 t-10                    0.003223               -0.000414
    3  t-9                    0.003021               -0.000420
    4  t-8                    0.002928               -0.000565
    5  t-7                    0.002781               -0.000386
    6  t-6                    0.002622               -0.000455
    7  t-5                    0.002368               -0.000387
    8  t-4                    0.001969               -0.000364
    9  t-3                    0.001730               -0.000236
   10  t-2                    0.001385               -0.000219
   11  t-1                    0.001048               -0.000057
   12    t                    0.000640               -0.000051
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

Tempo total de execução: 110.85 segundos.