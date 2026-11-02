# Relatório SHAP — LSTM AutoML ROA

## Configuração
- Base: `bases/base_final_winsorizada.xlsx`
- Modelo: `outputs/modelos/AM2 - LSTM/liquidez_porte/NIM/lstm_automl_NIM.keras`
- Preprocessadores: `outputs/modelos/AM2 - LSTM/liquidez_porte/NIM/preprocessadores_NIM.joblib`
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
    1 operacoes_de_credito_sobre_captacoes                0.004933                        0.004767                -0.000468
    2                    liquidez_imediata                0.004731                        0.004653                -0.001166
    3                              estatal                0.004277                        0.004274                -0.001080
    4                          crise_covid                0.004012                        0.002458                 0.000489
    5          captacoes_sobre_ativo_total                0.003158                        0.003154                -0.001801
    6  depositos_a_vista_sobre_ativo_total                0.003127                        0.003036                -0.000340
    7               indice_de_imobilizacao                0.002788                        0.002679                 0.001105
    8  depositos_a_prazo_sobre_ativo_total                0.002172                        0.002003                -0.000646
    9                              lcr_dec                0.001492                        0.001385                -0.000673
   10     disponibilidades_sobre_depositos                0.001002                        0.000955                -0.000430
   11                             nsfr_dec                0.000967                        0.000885                -0.000002
   12               patrimonio_liquido_log                0.000946                        0.000911                -0.000066
   13 operacoes_de_credito_sobre_depositos                0.000793                        0.000746                 0.000598
   14               ativos_sobre_depositos                0.000790                        0.000712                -0.000091
   15                            crise_nme                0.000769                        0.000608                -0.000509
```

## Importância por defasagem
```
 rank lag  mean_abs_shap_sum_features  mean_shap_sum_features
    1 t-7                    0.006433               -0.001194
    2 t-6                    0.006094               -0.000754
    3 t-5                    0.005357               -0.000605
    4 t-4                    0.005133               -0.000907
    5 t-3                    0.004409               -0.000819
    6 t-2                    0.003831               -0.000593
    7 t-1                    0.003037               -0.000337
    8   t                    0.002185               -0.000318
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

Tempo total de execução: 142.13 segundos.